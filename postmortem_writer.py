#!/usr/bin/env python3
"""
OBSERVER Auto-Postmortem Writer
Detecta incidentes recién resueltos y genera postmortems automáticos
que se añaden a PROJECT_STATE.md para enriquecer el contexto del LLM.
"""

import os
import json
import requests
from datetime import datetime, timezone
from psycopg import connect
from psycopg.rows import dict_row

from app.core.settings import settings
DATABASE_URL = settings.DATABASE_URL
PROJECT_STATE_PATH = "/root/observer/POSTMORTEMS.md"
MODEL_URL = "https://api.openai.com/v1/chat/completions"
MODEL_API_KEY = os.getenv("STRATEGIC_MODEL_API_KEY", "").strip()
MODEL_NAME = "gpt-4o-mini"

# Ventana: incidentes resueltos en las últimas 2 horas no procesados aún
RESOLVE_WINDOW_HOURS = 2


def fetch_unprocessed_resolved(cur):
    cur.execute("""
        SELECT
            incident_id,
            incident_key,
            incident_class,
            title,
            severity,
            entity_type,
            entity_name,
            occurrence_count,
            first_seen_at,
            resolved_at,
            resolution_type,
            resolution_notes
        FROM incident_registry
        WHERE status = 'RESOLVED'
          AND resolved_at > now() - interval '24 hours'
          AND (resolution_notes IS NULL
               OR resolution_notes NOT LIKE '%%[postmortem:%%')
        ORDER BY resolved_at DESC
        LIMIT 5
    """)
    return cur.fetchall()


def fetch_related_tasks(cur, entity_name, first_seen_at, resolved_at):
    cur.execute("""
        SELECT
            t.task_id,
            t.status,
            t.created_by,
            t.created_at,
            o.op_type
        FROM brain_tasks t
        JOIN brain_ops o ON t.org_id = o.org_id AND t.task_id = o.task_id
        WHERE t.created_at BETWEEN %s AND %s
          AND (o.op_type LIKE %s OR t.created_by = 'brain_intent_router')
        ORDER BY t.created_at ASC
        LIMIT 10
    """, (first_seen_at, resolved_at, f"%{entity_name}%"))
    return cur.fetchall()


def call_llm(prompt: str) -> str:
    if not MODEL_API_KEY:
        return "LLM no configurado — postmortem generado sin análisis automático."
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MODEL_API_KEY}",
    }
    payload = {
        "model": MODEL_NAME,
        "temperature": 0,
        "max_tokens": 600,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Eres el sistema OBSERVER, un governance runtime para acciones de agentes. "
                    "Genera postmortems concisos en español. "
                    "Máximo 200 palabras. Sin markdown. Sin títulos extra. "
                    "Solo el texto del postmortem."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    r = requests.post(MODEL_URL, headers=headers, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["choices"][0]["message"]["content"].strip()


def build_prompt(incident: dict, related_tasks: list) -> str:
    tasks_summary = ""
    if related_tasks:
        lines = []
        for t in related_tasks:
            lines.append(f"  - {t['op_type']} ({t['status']}) por {t['created_by']} a las {t['created_at']}")
        tasks_summary = "Acciones ejecutadas durante el incidente:\n" + "\n".join(lines)
    else:
        tasks_summary = "No se registraron acciones automáticas durante el incidente."

    return f"""Incidente resuelto en OBSERVER:

Título: {incident['title']}
Servicio afectado: {incident['entity_name']}
Severidad: {incident['severity']}
Clase: {incident['incident_class']}
Primera detección: {incident['first_seen_at']}
Resolución: {incident['resolved_at']}
Ocurrencias: {incident['occurrence_count']}
Tipo de resolución: {incident['resolution_type'] or 'no especificado'}
Notas: {incident['resolution_notes'] or 'ninguna'}

{tasks_summary}

Escribe un postmortem breve que incluya:
1. Qué ocurrió
2. Causa probable
3. Cómo se resolvió
4. Qué mejorar para prevenir recurrencia"""


def append_postmortem(incident: dict, postmortem_text: str):
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    incident_id_short = str(incident["incident_id"])[:8]

    entry = (
        f"\n\n## postmortem:{incident_id_short} [{now}]\n"
        f"incident: {incident['incident_key']}\n"
        f"severity: {incident['severity']}\n"
        f"resolved_at: {incident['resolved_at']}\n"
        f"occurrences: {incident['occurrence_count']}\n\n"
        f"{postmortem_text}\n"
    )

    with open(PROJECT_STATE_PATH, "a", encoding="utf-8") as f:
        f.write(entry)

    print(f"[postmortem] escrito para {incident['incident_key']}")


def mark_processed(cur, incident_id: str, incident_id_short: str):
    cur.execute("""
        UPDATE incident_registry
        SET resolution_notes = COALESCE(resolution_notes, '') || ' [postmortem:' || %s || ']'
        WHERE incident_id = %s
    """, (incident_id_short, incident_id))


def main():
    print(f"[postmortem_writer] {datetime.now(timezone.utc).isoformat()} iniciando")

    with connect(DATABASE_URL, row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            incidents = fetch_unprocessed_resolved(cur)

            if not incidents:
                print("[postmortem_writer] no hay incidentes resueltos pendientes de postmortem")
                return

            for incident in incidents:
                incident_id = str(incident["incident_id"])
                incident_id_short = incident_id[:8]

                print(f"[postmortem_writer] procesando {incident['incident_key']}")

                related_tasks = fetch_related_tasks(
                    cur,
                    incident["entity_name"],
                    incident["first_seen_at"],
                    incident["resolved_at"],
                )

                prompt = build_prompt(incident, related_tasks)

                try:
                    postmortem_text = call_llm(prompt)
                except Exception as e:
                    postmortem_text = f"Error al generar postmortem automático: {e}"

                append_postmortem(incident, postmortem_text)
                mark_processed(cur, incident_id, incident_id_short)

            conn.commit()

    print("[postmortem_writer] completado")


if __name__ == "__main__":
    main()
