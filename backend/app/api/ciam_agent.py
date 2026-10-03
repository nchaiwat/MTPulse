from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from app.api.ciam_auth import Admin, Db, audit_context
from app.services import ciam, ciam_agent

router = APIRouter(tags=["CIAM Agent"], dependencies=[Depends(audit_context)])


class AgentSettings(BaseModel):
    enabled: bool = False
    app_code: str = Field(default="mtpulse", pattern=r"^[a-z][a-z0-9_-]{0,49}$")
    api_key: str | None = Field(default=None, max_length=2000, repr=False)


@router.get("/api/settings/ciam-agent")
def get_settings(response: Response, session: Db, actor: Admin):
    response.headers["Cache-Control"] = "no-store"
    return ciam_agent.status(session)


@router.put("/api/settings/ciam-agent")
def save_settings(payload: AgentSettings, request: Request, session: Db, actor: Admin):
    ciam.same_origin(request, ciam.config(session))
    ciam_agent.save_config(session, payload.model_dump(), actor)
    return ciam_agent.status(session)


@router.post("/api/settings/ciam-agent/reveal")
def reveal_key(request: Request, response: Response, session: Db, actor: Admin):
    ciam.same_origin(request, ciam.config(session))
    response.headers["Cache-Control"] = "no-store"
    value = ciam_agent.config(session, secret=True)["api_key"]
    ciam_agent.audit(session, "secret", "success", "เปิดดู Agent API Key", {}, actor)
    session.commit()
    return {"value": value}
