from datetime import datetime
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field, HttpUrl

from .. import ratelimit
from ..audit_rules import build_report
from ..config import settings
from ..deps import AdminCtx, CtxDep, SessionDep
from ..domain import Provider
from ..models import AdAccount
from ..providers import gateway
from ..services import accounts, audit_log, connections, usage

router = APIRouter(prefix="/v1/accounts", tags=["insights"])
Days = Annotated[int, Query(ge=1, le=90)]


class KeywordIdeasRequest(BaseModel):
    seeds: list[Annotated[str, Field(min_length=2, max_length=80)]] = Field(default_factory=list, max_length=20)
    url: HttpUrl | None = None
    geo_target_ids: list[Annotated[str, Field(pattern=r"^\d+$")]] = Field(
        default_factory=lambda: ["2076"], max_length=20
    )
    language_id: str = Field(default="1014", pattern=r"^\d+$")


class OfflineConversion(BaseModel):
    conversion_action_id: str = Field(pattern=r"^\d+$")
    gclid: str = Field(min_length=10, max_length=200)
    occurred_at: datetime
    value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


def _require_google(account: AdAccount) -> None:
    if account.provider != Provider.GOOGLE_ADS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Disponível apenas para contas Google Ads.")


@router.get("/{account_id}/snapshot")
async def snapshot(account_id: str, ctx: CtxDep, session: SessionDep, days: Days = 30, refresh: bool = False):
    account = await accounts.account_for(session, ctx, account_id)
    if refresh:
        ratelimit.hit(f"refresh:{account.id}", 6, 600)
    data = await accounts.snapshot(session, account, days=days, refresh=refresh)
    return {
        **data.model_dump(mode="json"),
        "totals": data.totals().public(),
        "by_day": data.by_day(),
        "campaign_metrics": {c.campaign_id: c.metrics.public() for c in data.campaigns},
    }


@router.get("/{account_id}/audit")
async def audit(account_id: str, ctx: CtxDep, session: SessionDep, days: Days = 30):
    account = await accounts.account_for(session, ctx, account_id)
    report = build_report(await accounts.snapshot(session, account, days=days))
    return report.model_dump(mode="json")


@router.post("/{account_id}/keyword-ideas")
async def keyword_ideas(account_id: str, body: KeywordIdeasRequest, ctx: CtxDep, session: SessionDep):
    account = await accounts.account_for(session, ctx, account_id)
    _require_google(account)
    ratelimit.hit(f"ideas:{ctx.user.id}", 20, 600)
    creds = await connections.credentials(session, await accounts.connection_of(session, account))
    with usage.count_requests() as counter:
        try:
            ideas = await gateway(account.provider).keyword_ideas(
                creds,
                accounts.account_ref(account),
                seeds=body.seeds,
                url=str(body.url) if body.url else None,
                geo_ids=body.geo_target_ids,
                language_id=body.language_id,
            )
        finally:
            await usage.record(session, account.provider, counter[0])
            await session.commit()
    return {"ideas": ideas}


@router.get("/{account_id}/geo-suggest")
async def geo_suggest(
    account_id: str,
    ctx: CtxDep,
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=80)],
    country: Annotated[str, Query(pattern="^[A-Z]{2}$")] = "BR",
):
    account = await accounts.account_for(session, ctx, account_id)
    _require_google(account)
    ratelimit.hit(f"geo:{ctx.user.id}", 60, 600)
    creds = await connections.credentials(session, await accounts.connection_of(session, account))
    with usage.count_requests() as counter:
        try:
            return {"suggestions": await gateway(account.provider).geo_suggest(creds, q, country)}
        finally:
            await usage.record(session, account.provider, counter[0])
            await session.commit()


@router.post("/{account_id}/offline-conversions", status_code=status.HTTP_201_CREATED)
async def offline_conversion(account_id: str, body: OfflineConversion, ctx: AdminCtx, session: SessionDep):
    """Lead qualificado / visita agendada importados pelo GCLID salvo no formulário."""
    account = await accounts.account_for(session, ctx, account_id)
    _require_google(account)
    if not settings.mutations_enabled(account.provider):
        raise HTTPException(status.HTTP_423_LOCKED, "Envio desligado pelo kill switch ou pela flag da plataforma.")
    creds = await connections.credentials(session, await accounts.connection_of(session, account))
    with usage.count_requests() as counter:
        try:
            result = await gateway(account.provider).upload_click_conversion(
                creds,
                accounts.account_ref(account),
                conversion_action_id=body.conversion_action_id,
                gclid=body.gclid,
                occurred_at=body.occurred_at,
                value=body.value,
                currency=account.currency,
            )
        finally:
            await usage.record(session, account.provider, counter[0])
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        action="conversion.offline_uploaded",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="conversion_action",
        resource_id=body.conversion_action_id,
        result="uploaded",
    )
    await session.commit()
    return result
