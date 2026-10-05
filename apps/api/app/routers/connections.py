from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from ..config import settings
from ..deps import AdminCtx, CtxDep, SessionDep
from ..models import AdAccount, AdConnection
from ..providers import provider_catalog
from ..services import accounts, audit_log, connections, usage

router = APIRouter(prefix="/v1", tags=["connections"])


class LinkAccount(BaseModel):
    external_id: str = Field(pattern=r"^\d{1,20}$")


def account_out(account: AdAccount) -> dict[str, object]:
    return {
        "id": account.id,
        "provider": account.provider,
        "external_id": account.external_id,
        "name": account.name,
        "currency": account.currency,
        "time_zone": account.time_zone,
        "login_customer_id": account.login_customer_id,
        "is_test_account": account.is_test_account,
        "connection_id": account.connection_id,
    }


@router.get("/providers")
async def providers(ctx: CtxDep, session: SessionDep):
    return {
        "kill_switch": settings.global_kill_switch,
        "providers": provider_catalog(),
        "google_operations_today": await usage.today(session, "GOOGLE_ADS"),
        "google_daily_quota": settings.google_ads_daily_operation_quota,
    }


@router.get("/connections")
async def list_connections(ctx: CtxDep, session: SessionDep):
    items = await session.scalars(
        select(AdConnection)
        .where(
            AdConnection.organization_id == ctx.organization_id,
            AdConnection.workspace_id == ctx.workspace_id,
            AdConnection.status != "REVOKED",
        )
        .order_by(AdConnection.created_at.desc())
    )
    linked = await accounts.list_accounts(session, ctx)
    return {
        "connections": [
            {
                "id": c.id,
                "provider": c.provider,
                "status": c.status,
                "created_at": c.created_at,
                "last_error": c.last_error,
                "discovered_accounts": c.discovered_accounts or [],
            }
            for c in items
        ],
        "accounts": [account_out(a) for a in linked],
    }


@router.post("/connections/{slug}/start")
async def start(slug: str, ctx: AdminCtx, session: SessionDep):
    provider = connections.provider_from_slug(slug)
    return {"authorization_url": await connections.start(session, ctx, provider)}


@router.get("/connections/{slug}/callback", include_in_schema=False)
async def callback(
    slug: str,
    session: SessionDep,
    code: Annotated[str | None, Query(max_length=2048)] = None,
    state: Annotated[str | None, Query(max_length=256)] = None,
    error: Annotated[str | None, Query(max_length=200)] = None,
    auth_code: Annotated[str | None, Query(max_length=2048)] = None,
):
    provider = connections.provider_from_slug(slug)
    url = await connections.complete(session, provider, code=code or auth_code, state=state, error=error)
    return RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/connections/{connection_id}/discover")
async def discover(connection_id: str, ctx: AdminCtx, session: SessionDep):
    connection = await connections.get_connection(session, ctx, connection_id)
    connection = await connections.rediscover(session, ctx, connection)
    return {"discovered_accounts": connection.discovered_accounts or []}


@router.post("/connections/{connection_id}/accounts", status_code=status.HTTP_201_CREATED)
async def link(connection_id: str, body: LinkAccount, ctx: AdminCtx, session: SessionDep):
    connection = await connections.get_connection(session, ctx, connection_id)
    if connection.status != "ACTIVE":
        raise HTTPException(status.HTTP_409_CONFLICT, "Reconecte esta autorização antes de vincular contas.")
    return account_out(await connections.link_account(session, ctx, connection, body.external_id))


@router.delete("/connections/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def disconnect(connection_id: str, ctx: AdminCtx, session: SessionDep) -> None:
    connection = await connections.get_connection(session, ctx, connection_id)
    await connections.disconnect(session, ctx, connection)


@router.get("/accounts")
async def list_accounts(ctx: CtxDep, session: SessionDep):
    return [account_out(a) for a in await accounts.list_accounts(session, ctx)]


@router.delete("/accounts/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def unlink(account_id: str, ctx: AdminCtx, session: SessionDep) -> None:
    account = await accounts.account_for(session, ctx, account_id)
    await session.delete(account)
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        action="account.unlinked",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="ad_account",
        resource_id=account_id,
        result="success",
    )
    await session.commit()
