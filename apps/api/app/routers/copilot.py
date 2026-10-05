from typing import Annotated, Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import select

from .. import ai, ratelimit
from ..audit_rules import build_report
from ..config import settings
from ..deps import CtxDep, SessionDep
from ..models import AuditEvent
from ..providers import ProviderError
from ..services import accounts

router = APIRouter(prefix="/v1", tags=["copilot"])


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=8000)


class ChatRequest(BaseModel):
    account_id: str | None = Field(default=None, max_length=36)
    message: str = Field(min_length=1, max_length=4000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=20)


@router.post("/copilot/chat")
async def chat(body: ChatRequest, ctx: CtxDep, session: SessionDep):
    ratelimit.hit(f"copilot:{ctx.user.id}", 30, 600)
    snapshot = report = None
    note = None
    if body.account_id:
        account = await accounts.account_for(session, ctx, body.account_id)
        try:
            snapshot = await accounts.snapshot(session, account)
            report = build_report(snapshot)
        except ProviderError as failure:
            note = f"Não consegui ler a conta agora: {failure.message}"
    result = await ai.chat(body.message, [t.model_dump() for t in body.history], snapshot, report)
    if note:
        result["reply"] = f"{note}\n\n{result['reply']}"
    return {**result, "ai_enabled": ai.enabled(), "can_propose": ctx.can("admin")}


@router.get("/audit")
async def audit_trail(
    ctx: CtxDep,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    action: Annotated[str | None, Query(max_length=64)] = None,
):
    query = select(AuditEvent).where(
        AuditEvent.organization_id == ctx.organization_id,
        (AuditEvent.workspace_id == ctx.workspace_id) | AuditEvent.workspace_id.is_(None),
    )
    if action:
        query = query.where(AuditEvent.action.startswith(action))
    events = await session.scalars(query.order_by(AuditEvent.occurred_at.desc()).limit(limit))
    return [
        {
            "id": e.id,
            "action": e.action,
            "actor": e.actor_name,
            "resource_type": e.resource_type,
            "resource_id": e.resource_id,
            "result": e.result,
            "details": e.details,
            "occurred_at": e.occurred_at,
        }
        for e in events
    ]


@router.get("/system")
async def system(ctx: CtxDep):
    return {
        "kill_switch": settings.global_kill_switch,
        "ai_enabled": ai.enabled(),
        "google_mutations": settings.mutations_enabled("GOOGLE_ADS"),
        "tiktok_mutations": settings.mutations_enabled("TIKTOK_ADS"),
        "role": ctx.role,
        "workspace": {
            "id": ctx.workspace_id,
            "name": ctx.workspace.name,
            "daily_budget_limit": str(ctx.workspace.daily_budget_limit),
        },
    }
