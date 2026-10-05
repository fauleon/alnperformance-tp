from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import utcnow
from ..deps import Context
from ..models import AdAccount, AdConnection, ProviderCache
from ..providers import AccountRef, ProviderError, gateway
from ..snapshot import AccountSnapshot
from . import connections, usage


async def account_for(session: AsyncSession, ctx: Context, account_id: str) -> AdAccount:
    account = await session.get(AdAccount, account_id)
    if not account or account.organization_id != ctx.organization_id or account.workspace_id != ctx.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta de anúncio não encontrada neste cliente.")
    return account


async def list_accounts(session: AsyncSession, ctx: Context) -> list[AdAccount]:
    return list(
        await session.scalars(
            select(AdAccount)
            .where(AdAccount.organization_id == ctx.organization_id, AdAccount.workspace_id == ctx.workspace_id)
            .order_by(AdAccount.provider, AdAccount.name)
        )
    )


def account_ref(account: AdAccount) -> AccountRef:
    return AccountRef(
        external_id=account.external_id, login_customer_id=account.login_customer_id, currency=account.currency
    )


def period(days: int) -> tuple[date, date]:
    end = date.today() - timedelta(days=1)
    return end - timedelta(days=max(1, min(days, 365)) - 1), end


async def connection_of(session: AsyncSession, account: AdAccount) -> AdConnection:
    connection = await session.get(AdConnection, account.connection_id)
    if not connection:
        raise ProviderError("Conexão desta conta foi removida. Conecte novamente.", needs_reconnect=True)
    return connection


async def snapshot(
    session: AsyncSession, account: AdAccount, *, days: int = 30, refresh: bool = False, ttl_minutes: int | None = None
) -> AccountSnapshot:
    """Cached read. The nightly sync job refreshes with a long TTL so the panel opens instantly."""
    start, end = period(days)
    key = f"snapshot:{account.id}:{start.isoformat()}:{end.isoformat()}"
    cached = await session.get(ProviderCache, key)
    if cached and not refresh and cached.expires_at > utcnow():
        return AccountSnapshot.model_validate(cached.payload)

    connection = await connection_of(session, account)
    creds = await connections.credentials(session, connection)
    with usage.count_requests() as counter:
        try:
            result = await gateway(account.provider).snapshot(creds, account_ref(account), start, end)
        except ProviderError as failure:
            if failure.needs_reconnect:
                await connections.mark_needs_reconnect(session, connection, failure.message)
            raise
        finally:
            await usage.record(session, account.provider, counter[0])
    if not account.currency and result.currency:
        account.currency = result.currency
    payload = result.model_dump(mode="json")
    expires = utcnow() + timedelta(minutes=ttl_minutes or settings.metrics_cache_minutes)
    if cached:
        cached.payload, cached.expires_at, cached.updated_at = payload, expires, utcnow()
    else:
        session.add(
            ProviderCache(key=key, organization_id=account.organization_id, payload=payload, expires_at=expires)
        )
    await session.commit()
    return result
