from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import func, select

from ..config import settings
from ..db import utcnow
from ..deps import AdminCtx, CtxDep, OwnerCtx, SessionDep
from ..models import Invitation, Membership, User, Workspace
from ..security import new_token, token_hash
from ..services import audit_log

router = APIRouter(prefix="/v1", tags=["workspaces"])


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    daily_budget_limit: Decimal = Field(default=Decimal("100.00"), gt=0, max_digits=14, decimal_places=2)


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    daily_budget_limit: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)


class InvitationCreate(BaseModel):
    email: EmailStr
    role: str = Field(pattern="^(owner|admin|viewer)$")


class RoleUpdate(BaseModel):
    role: str = Field(pattern="^(owner|admin|viewer)$")


@router.post("/workspaces", status_code=status.HTTP_201_CREATED)
async def create_workspace(body: WorkspaceCreate, ctx: AdminCtx, session: SessionDep):
    workspace = Workspace(
        organization_id=ctx.organization_id, name=body.name, daily_budget_limit=body.daily_budget_limit
    )
    session.add(workspace)
    await session.flush()
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=workspace.id,
        action="workspace.created",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="workspace",
        resource_id=workspace.id,
        result="success",
    )
    await session.commit()
    return {"id": workspace.id, "name": workspace.name, "daily_budget_limit": str(workspace.daily_budget_limit)}


@router.patch("/workspaces/current")
async def update_workspace(body: WorkspaceUpdate, ctx: AdminCtx, session: SessionDep):
    workspace = ctx.workspace
    changes: dict[str, str] = {}
    if body.name:
        workspace.name = body.name
        changes["name"] = body.name
    if body.daily_budget_limit is not None:
        if not ctx.can("owner"):
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o proprietário altera o limite de orçamento.")
        changes["daily_budget_limit"] = f"{workspace.daily_budget_limit} → {body.daily_budget_limit}"
        workspace.daily_budget_limit = body.daily_budget_limit
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=workspace.id,
        action="workspace.updated",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="workspace",
        resource_id=workspace.id,
        result="success",
        details=changes,
    )
    await session.commit()
    return {"id": workspace.id, "name": workspace.name, "daily_budget_limit": str(workspace.daily_budget_limit)}


@router.get("/members")
async def list_members(ctx: CtxDep, session: SessionDep):
    rows = await session.execute(
        select(Membership, User)
        .join(User, User.id == Membership.user_id)
        .where(Membership.organization_id == ctx.organization_id)
        .order_by(User.name)
    )
    invitations = await session.scalars(
        select(Invitation).where(
            Invitation.organization_id == ctx.organization_id,
            Invitation.accepted_at.is_(None),
            Invitation.expires_at > utcnow(),
        )
    )
    return {
        "members": [{"user_id": u.id, "name": u.name, "email": u.email, "role": m.role} for m, u in rows],
        "pending_invitations": [
            {"id": i.id, "email": i.email, "role": i.role, "expires_at": i.expires_at} for i in invitations
        ]
        if ctx.can("admin")
        else [],
    }


@router.post("/invitations", status_code=status.HTTP_201_CREATED)
async def invite(body: InvitationCreate, ctx: AdminCtx, session: SessionDep):
    if body.role == "owner" and not ctx.can("owner"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Só o proprietário convida outro proprietário.")
    token = new_token()
    invitation = Invitation(
        organization_id=ctx.organization_id,
        email=body.email.lower(),
        role=body.role,
        token_hash=token_hash(token),
        created_by=ctx.user.id,
        expires_at=utcnow() + timedelta(days=7),
    )
    session.add(invitation)
    await session.flush()
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=None,
        action="invitation.created",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="invitation",
        resource_id=invitation.id,
        result=body.role,
    )
    await session.commit()
    # Shown once to the admin, who sends it to the person. The token is stored only as a hash.
    return {"invite_url": f"{settings.app_url.rstrip('/')}/convite/{token}", "expires_at": invitation.expires_at}


@router.delete("/invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def cancel_invitation(invitation_id: str, ctx: AdminCtx, session: SessionDep) -> None:
    invitation = await session.get(Invitation, invitation_id)
    if not invitation or invitation.organization_id != ctx.organization_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Convite não encontrado.")
    await session.delete(invitation)
    await session.commit()


async def _owners(session: SessionDep, organization_id: str) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(Membership)
            .where(Membership.organization_id == organization_id, Membership.role == "owner")
        )
        or 0
    )


@router.patch("/members/{user_id}")
async def change_role(user_id: str, body: RoleUpdate, ctx: OwnerCtx, session: SessionDep):
    membership = await session.scalar(
        select(Membership).where(Membership.organization_id == ctx.organization_id, Membership.user_id == user_id)
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membro não encontrado.")
    if membership.role == "owner" and body.role != "owner" and await _owners(session, ctx.organization_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "A organização precisa de pelo menos um proprietário.")
    membership.role = body.role
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=None,
        action="member.role_changed",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="user",
        resource_id=user_id,
        result=body.role,
    )
    await session.commit()
    return {"user_id": user_id, "role": body.role}


@router.delete("/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_member(user_id: str, ctx: OwnerCtx, session: SessionDep) -> None:
    membership = await session.scalar(
        select(Membership).where(Membership.organization_id == ctx.organization_id, Membership.user_id == user_id)
    )
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membro não encontrado.")
    if membership.role == "owner" and await _owners(session, ctx.organization_id) <= 1:
        raise HTTPException(status.HTTP_409_CONFLICT, "A organização precisa de pelo menos um proprietário.")
    await session.delete(membership)
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=None,
        action="member.removed",
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="user",
        resource_id=user_id,
        result="removed",
    )
    await session.commit()
