import asyncio
from collections import defaultdict
from datetime import timedelta
from urllib.parse import urlencode

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import utcnow
from ..deps import Context
from ..domain import Provider
from ..models import AdAccount, AdConnection, OAuthState
from ..providers import Credentials, ProviderError, gateway
from ..security import decrypt, encrypt, new_token, pkce_pair, token_hash
from . import audit_log

OAUTH_TTL = timedelta(minutes=10)
SLUGS = {Provider.GOOGLE_ADS: "google", Provider.TIKTOK_ADS: "tiktok"}
_refresh_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)


def provider_from_slug(slug: str) -> Provider:
    for provider, value in SLUGS.items():
        if value == slug:
            return provider
    raise HTTPException(status.HTTP_404_NOT_FOUND, "Plataforma desconhecida.")


def redirect_uri(provider: Provider) -> str:
    return f"{settings.public_api_url.rstrip('/')}/v1/connections/{SLUGS[provider]}/callback"


def panel_url(**params: str) -> str:
    return f"{settings.app_url.rstrip('/')}/app/integracoes?{urlencode(params)}"


def configured(provider: Provider) -> bool:
    return settings.google_configured if provider == Provider.GOOGLE_ADS else settings.tiktok_configured


async def start(session: AsyncSession, ctx: Context, provider: Provider) -> str:
    if not configured(provider):
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "Credenciais da plataforma ainda não configuradas no servidor."
        )
    gw = gateway(provider)
    nonce = new_token()
    verifier, challenge = pkce_pair() if gw.supports_pkce else (None, None)
    session.add(
        OAuthState(
            nonce_hash=token_hash(nonce),
            provider=provider.value,
            organization_id=ctx.organization_id,
            workspace_id=ctx.workspace_id,
            user_id=ctx.user.id,
            encrypted_code_verifier=encrypt(verifier),
            expires_at=utcnow() + OAUTH_TTL,
        )
    )
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        action="connection.oauth_started",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="provider",
        resource_id=provider.value,
        result="redirect",
    )
    await session.commit()
    return gw.authorization_url(state=nonce, redirect_uri=redirect_uri(provider), code_challenge=challenge)


async def complete(
    session: AsyncSession, provider: Provider, *, code: str | None, state: str | None, error: str | None
) -> str:
    slug = SLUGS[provider]
    if not state:
        return panel_url(provider=slug, status="error", reason="state")
    stored = await session.scalar(
        select(OAuthState).where(OAuthState.nonce_hash == token_hash(state)).with_for_update()
    )
    if not stored or stored.used_at or stored.expires_at <= utcnow() or stored.provider != provider.value:
        return panel_url(provider=slug, status="error", reason="state")
    stored.used_at = utcnow()  # single use, even if everything below fails
    await session.commit()

    def audit(action: str, result: str, details: dict | None = None) -> None:
        audit_log.record(
            session,
            organization_id=stored.organization_id,
            workspace_id=stored.workspace_id,
            action=action,
            actor_id=stored.user_id,
            actor_name="oauth",
            resource_type="provider",
            resource_id=provider.value,
            result=result,
            details=details,
        )

    if error or not code:
        audit("connection.oauth_denied", "denied", {"error": (error or "missing_code")[:60]})
        await session.commit()
        return panel_url(provider=slug, status="denied")

    gw = gateway(provider)
    try:
        tokens = await gw.exchange_code(
            code=code, redirect_uri=redirect_uri(provider), code_verifier=decrypt(stored.encrypted_code_verifier)
        )
    except ProviderError as failure:
        audit("connection.oauth_failed", "error", {"message": failure.message})
        await session.commit()
        return panel_url(provider=slug, status="error", reason="exchange")
    if provider == Provider.GOOGLE_ADS and not tokens.refresh_token:
        audit("connection.oauth_failed", "no_refresh_token")
        await session.commit()
        return panel_url(provider=slug, status="error", reason="no_refresh_token")

    connection = AdConnection(
        organization_id=stored.organization_id,
        workspace_id=stored.workspace_id,
        provider=provider.value,
        status="ACTIVE",
        encrypted_access_token=encrypt(tokens.access_token),
        encrypted_refresh_token=encrypt(tokens.refresh_token),
        scopes=tokens.scopes,
        created_by=stored.user_id,
        access_token_expires_at=utcnow() + timedelta(seconds=tokens.expires_in) if tokens.expires_in else None,
    )
    session.add(connection)
    await session.flush()
    try:
        discovered = await gw.discover_accounts(Credentials(tokens.access_token, tokens.refresh_token), tokens)
        connection.discovered_accounts = [account.model_dump() for account in discovered]
    except ProviderError as failure:
        connection.last_error = failure.message[:300]
    audit(
        "connection.connected",
        "success",
        {"connection_id": connection.id, "accounts": len(connection.discovered_accounts or [])},
    )
    await session.commit()
    return panel_url(provider=slug, status="connected", connection=connection.id)


async def get_connection(session: AsyncSession, ctx: Context, connection_id: str) -> AdConnection:
    connection = await session.get(AdConnection, connection_id)
    if (
        not connection
        or connection.organization_id != ctx.organization_id
        or connection.workspace_id != ctx.workspace_id
    ):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conexão não encontrada.")
    return connection


async def mark_needs_reconnect(session: AsyncSession, connection: AdConnection, message: str) -> None:
    connection.status = "NEEDS_RECONNECT"
    connection.last_error = message[:300]
    audit_log.record(
        session,
        organization_id=connection.organization_id,
        workspace_id=connection.workspace_id,
        action="connection.needs_reconnect",
        actor_id=None,
        actor_name="sistema",
        resource_type="connection",
        resource_id=connection.id,
        result="needs_reconnect",
    )
    await session.commit()


async def credentials(session: AsyncSession, connection: AdConnection) -> Credentials:
    if connection.status != "ACTIVE":
        raise ProviderError("Esta conexão precisa ser refeita.", needs_reconnect=True)
    if connection.provider == Provider.TIKTOK_ADS:
        return Credentials(decrypt(connection.encrypted_access_token))

    def fresh(conn: AdConnection) -> bool:
        return bool(
            conn.encrypted_access_token
            and conn.access_token_expires_at
            and conn.access_token_expires_at > utcnow() + timedelta(minutes=2)
        )

    if fresh(connection):
        return Credentials(decrypt(connection.encrypted_access_token), decrypt(connection.encrypted_refresh_token))
    async with _refresh_locks[connection.id]:  # one refresh per process
        # Row lock: one refresh across processes (no-op on SQLite).
        locked = await session.scalar(
            select(AdConnection)
            .where(AdConnection.id == connection.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        connection = locked or connection
        if not fresh(connection):
            refresh_token = decrypt(connection.encrypted_refresh_token)
            if not refresh_token:
                await mark_needs_reconnect(session, connection, "Sem refresh token")
                raise ProviderError("Reconecte a conta do Google.", needs_reconnect=True)
            try:
                bundle = await gateway(connection.provider).refresh(refresh_token)
            except ProviderError as failure:
                if failure.needs_reconnect:
                    await mark_needs_reconnect(session, connection, failure.message)
                raise
            connection.encrypted_access_token = encrypt(bundle.access_token)
            connection.access_token_expires_at = utcnow() + timedelta(seconds=bundle.expires_in or 3600)
        await session.commit()
    return Credentials(decrypt(connection.encrypted_access_token), decrypt(connection.encrypted_refresh_token))


async def rediscover(session: AsyncSession, ctx: Context, connection: AdConnection) -> AdConnection:
    creds = await credentials(session, connection)
    try:
        discovered = await gateway(connection.provider).discover_accounts(creds)
    except ProviderError as failure:
        if failure.needs_reconnect:
            await mark_needs_reconnect(session, connection, failure.message)
        raise
    connection.discovered_accounts = [account.model_dump() for account in discovered]
    connection.last_error = None
    await session.commit()
    return connection


async def link_account(session: AsyncSession, ctx: Context, connection: AdConnection, external_id: str) -> AdAccount:
    match = next((a for a in connection.discovered_accounts or [] if a["external_id"] == external_id), None)
    if not match:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conta não encontrada nesta autorização.")
    if not match.get("selectable", True):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "Contas de administrador (MCC) não recebem campanhas; escolha uma subconta.",
        )
    existing = await session.scalar(
        select(AdAccount).where(
            AdAccount.workspace_id == ctx.workspace_id,
            AdAccount.provider == connection.provider,
            AdAccount.external_id == external_id,
        )
    )
    if existing:
        existing.connection_id = connection.id  # re-linking after a reconnect keeps plans and history
        existing.login_customer_id = match.get("login_customer_id")
        account = existing
    else:
        account = AdAccount(
            organization_id=ctx.organization_id,
            workspace_id=ctx.workspace_id,
            connection_id=connection.id,
            provider=connection.provider,
            external_id=external_id,
            login_customer_id=match.get("login_customer_id"),
            name=match["name"][:200],
            currency=match.get("currency"),
            time_zone=match.get("time_zone"),
            is_test_account=bool(match.get("is_test_account")),
        )
        session.add(account)
    await session.flush()
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        action="account.linked",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="ad_account",
        resource_id=account.id,
        result="success",
        details={"provider": connection.provider, "external_id": external_id},
    )
    await session.commit()
    return account


async def disconnect(session: AsyncSession, ctx: Context, connection: AdConnection) -> None:
    token = decrypt(connection.encrypted_refresh_token) or decrypt(connection.encrypted_access_token)
    revoke_error = None
    if token:
        try:
            await gateway(connection.provider).revoke(token)
        except ProviderError as failure:
            revoke_error = failure.message
    connection.encrypted_access_token = None
    connection.encrypted_refresh_token = None
    connection.status = "REVOKED"
    connection.discovered_accounts = None
    for account in await session.scalars(select(AdAccount).where(AdAccount.connection_id == connection.id)):
        await session.delete(account)
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        action="connection.disconnected",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="connection",
        resource_id=connection.id,
        result="revoked" if not revoke_error else "local_only",
        details={"revoke_error": revoke_error},
    )
    await session.commit()
