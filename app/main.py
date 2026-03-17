from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from app.routes.agents import router as agents_router
from app.routes.policies import router as policies_router
from app.routes.validate import router as validate_router
from app.routes.brain import router as brain_router
from app.routes.brain_intent import router as brain_intent_router
from app.routes.system_state import router as system_state_router
from app.routes.approvals_pending import router as approvals_pending_router
from app.routes.improvements import router as improvements_router
from app.routes.approvals_approve import router as approvals_approve_router
from app.routes.approvals_reject import router as approvals_reject_router
from app.routes.public_api import router as public_api_router

limiter = Limiter(key_func=get_remote_address)
app = FastAPI(
    title="OBSERVER API",
    description="""
## OBSERVER — Governance Runtime for Autonomous Agents

OBSERVER monitoriza tu infraestructura, detecta incidentes, ejecuta remediaciones y genera postmortems automáticamente.

### Autenticación
Todos los endpoints excepto `/v1/public/health` y `/v1/public/orgs` requieren:
- Header `Authorization: Bearer <api_key>`
- Header `X-Org-Id: <org_id>`

### Onboarding
1. Crea una organización con `POST /v1/public/orgs`
2. Guarda la `api_key` devuelta — no se mostrará de nuevo
3. Usa la key en todos los requests autenticados

### Rate limits
- `/health`: 60 req/min
- `/incidents`, `/services`, `/metrics`: 20-30 req/min  
- `/intent`: 10 req/min
- `/orgs`: 5 req/min
    """,
    version="1.0.0",
    contact={"name": "OBSERVER", "url": "https://github.com/observer-ai"},
    license_info={"name": "MIT"},
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/healthz")
def healthz():
    return {"ok": True}


app.include_router(agents_router)
app.include_router(policies_router)
app.include_router(validate_router)
app.include_router(brain_router)
app.include_router(brain_intent_router)
app.include_router(system_state_router)
app.include_router(approvals_pending_router)
app.include_router(improvements_router)
app.include_router(approvals_approve_router)
app.include_router(approvals_reject_router)
app.include_router(public_api_router)
