from dataclasses import dataclass
from datetime import timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import db_session, utcnow
from .models import AuthSession, Membership, User, Workspace
from .security import token_hash

SessionDep = Annotated[AsyncSession, Depends(db_session)]
ROLE_RANK = {"viewer": 0, "admin": 1, "owner": 2}


def client_ip(request: Request) -> str:
    if settings.trust_proxy_headers:
        for header in ("x-aln-client-ip", "x-real-ip", "x-forwarded-for"):
            if value := request.headers.get(header):
                return value.split(",")[0].strip()[:64]
    return request.client.host if request.client else "unknown"


async def current_user(request: Request, session: SessionDep) -> User:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Faça login para continuar.")
    auth = await session.scalar(select(AuthSession).where(AuthSession.token_hash == token_hash(token)))
    now = utcnow()
    if not auth or auth.expires_at <= now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Sessão expirada. Faça login novamente.")
    user = await session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuário inativo.")
    if now - auth.last_seen_at > timedelta(minutes=5):
        auth.last_seen_at = now
        await session.commit()
    request.state.user_id = user.id
    return user


UserDep = Annotated[User, Depends(current_user)]


@dataclass
class Context:
    user: User
    role: str
    organization_id: str
    workspace: Workspace

    @property
    def workspace_id(self) -> str:
        return self.workspace.id

    def can(self, role: str) -> bool:
        return ROLE_RANK[self.role] >= ROLE_RANK[role]


async def tenant(
    user: UserDep,
    session: SessionDep,
    x_workspace_id: Annotated[str | None, Header(max_length=36)] = None,
) -> Context:
    """Organization and workspace come from the authenticated membership, never from the client alone."""
    memberships = {
        m.organization_id: m.role
        for m in await session.scalars(select(Membership).where(Membership.user_id == user.id))
    }
    if not memberships:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu usuário não pertence a nenhuma organização.")
    query = select(Workspace).where(Workspace.organization_id.in_(memberships))
    if x_workspace_id:
        query = query.where(Workspace.id == x_workspace_id)
    workspace = await session.scalar(query.order_by(Workspace.created_at).limit(1))
    if not workspace:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cliente não encontrado.")
    return Context(
        user=user,
        role=memberships[workspace.organization_id],
        organization_id=workspace.organization_id,
        workspace=workspace,
    )


CtxDep = Annotated[Context, Depends(tenant)]


def require(role: str):
    async def check(ctx: CtxDep) -> Context:
        if not ctx.can(role):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Seu papel não permite esta ação.")
        return ctx

    return Depends(check)


AdminCtx = Annotated[Context, require("admin")]
OwnerCtx = Annotated[Context, require("owner")]
