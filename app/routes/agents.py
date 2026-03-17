from fastapi import APIRouter, Depends
from pydantic import BaseModel
from app.core.auth import require_auth
from app.db.conn import get_conn

router = APIRouter()

class AgentIn(BaseModel):
    id: str
    name: str

@router.post("/agents")
def create_agent(body: AgentIn, org_id: str = Depends(require_auth)):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO agents(id, org_id, name) VALUES(%s,%s,%s)",
            (body.id, org_id, body.name)
        )
        conn.execute(
            "INSERT INTO agent_state(org_id, agent_id) VALUES(%s,%s) ON CONFLICT DO NOTHING",
            (org_id, body.id)
        )
    return {"ok": True, "agent_id": body.id}
