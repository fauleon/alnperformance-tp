from datetime import timedelta
from decimal import Decimal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from .. import ratelimit
from ..config import settings
from ..db import utcnow
from ..deps import SessionDep, UserDep, client_ip
from ..models import AuthSession, Invitation, Membership, Organization, User, Workspace
from ..security import DUMMY_PASSWORD_HASH, hash_password, new_token, password_problem, token_hash, verify_password
from ..services import audit_log

router = APIRouter(prefix="/v1", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class SignupRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=200)
    organization_name: str = Field(min_length=2, max_length=120)


class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=200)
    new_password: str = Field(min_length=10, max_length=200)


class AcceptInvitation(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=1, max_length=200)


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        settings.session_cookie_name,
        token,
        max_age=settings.session_ttl_hours * 3600,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path="/",
    )


async def open_session(session: AsyncSession, request: Request, response: Response, user: User) -> None:
    token = new_token()
    session.add(
        AuthSession(
            user_id=user.id,
            token_hash=token_hash(token),
            expires_at=utcnow() + timedelta(hours=settings.session_ttl_hours),
            ip=client_ip(request),
            user_agent=(request.headers.get("user-agent") or "")[:200],
        )
    )
    user.last_login_at = utcnow()
    set_session_cookie(response, token)


async def me_payload(session: AsyncSession, user: User) -> dict[str, object]:
    memberships = list(await session.scalars(select(Membership).where(Membership.user_id == user.id)))
    org_ids = [m.organization_id for m in memberships]
    organizations = {o.id: o for o in await session.scalars(select(Organization).where(Organization.id.in_(org_ids)))}
    workspaces = list(
        await session.scalars(
            select(Workspace).where(Workspace.organization_id.in_(org_ids)).order_by(Workspace.created_at)
        )
    )
    roles = {m.organization_id: m.role for m in memberships}
    return {
        "user": {"id": user.id, "name": user.name, "email": user.email},
        "organizations": [
            {"id": oid, "name": organizations[oid].name, "role": roles[oid]} for oid in org_ids if oid in organizations
        ],
        "workspaces": [
            {
                "id": w.id,
                "name": w.name,
                "organization_id": w.organization_id,
                "role": roles[w.organization_id],
                "daily_budget_limit": str(w.daily_budget_limit),
            }
            for w in workspaces
        ],
    }


@router.post("/auth/login")
async def login(body: LoginRequest, request: Request, response: Response, session: SessionDep):
    email = body.email.lower()
    ratelimit.hit(f"login-ip:{client_ip(request)}", 20, 300)
    ratelimit.hit(f"login-email:{email}", 8, 900)
    user = await session.scalar(select(User).where(User.email == email))
    valid = verify_password(body.password, user.password_hash if user else DUMMY_PASSWORD_HASH)
    if not user or not valid or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-mail ou senha incorretos.")
    await open_session(session, request, response, user)
    await session.commit()
    return await me_payload(session, user)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, session: SessionDep) -> None:
    if token := request.cookies.get(settings.session_cookie_name):
        await session.execute(delete(AuthSession).where(AuthSession.token_hash == token_hash(token)))
        await session.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/auth/me")
async def me(user: UserDep, session: SessionDep):
    return await me_payload(session, user)


@router.get("/auth/config")
async def auth_config():
    return {"allow_signup": settings.allow_signup}


@router.post("/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(body: SignupRequest, request: Request, response: Response, session: SessionDep):
    if not settings.allow_signup:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Cadastro aberto desativado. Peça um convite à ALN.")
    ratelimit.hit(f"signup-ip:{client_ip(request)}", 5, 3600)
    if problem := password_problem(body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    email = body.email.lower()
    if await session.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(status.HTTP_409_CONFLICT, "Este e-mail já tem cadastro.")
    user = User(email=email, name=body.name, password_hash=hash_password(body.password))
    org = Organization(name=body.organization_name)
    session.add_all([user, org])
    await session.flush()
    session.add_all(
        [
            Membership(user_id=user.id, organization_id=org.id, role="owner"),
            Workspace(
                organization_id=org.id,
                name=body.organization_name,
                daily_budget_limit=Decimal(settings.default_daily_budget_limit),
            ),
        ]
    )
    audit_log.record(
        session,
        organization_id=org.id,
        workspace_id=None,
        action="user.signup",
        actor_id=user.id,
        actor_name=user.name,
        resource_type="user",
        resource_id=user.id,
        result="success",
    )
    await open_session(session, request, response, user)
    await session.commit()
    return await me_payload(session, user)


@router.post("/auth/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: PasswordChange, request: Request, response: Response, user: UserDep, session: SessionDep
) -> None:
    ratelimit.hit(f"password:{user.id}", 5, 900)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Senha atual incorreta.")
    if problem := password_problem(body.new_password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
    user.password_hash = hash_password(body.new_password)
    await session.execute(delete(AuthSession).where(AuthSession.user_id == user.id))  # sign out everywhere
    await open_session(session, request, response, user)
    await session.commit()


async def _invitation(session: AsyncSession, token: str) -> Invitation:
    invitation = await session.scalar(select(Invitation).where(Invitation.token_hash == token_hash(token)))
    if not invitation or invitation.accepted_at or invitation.expires_at <= utcnow():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Convite inválido ou expirado.")
    return invitation


@router.get("/invitations/{token}")
async def invitation_info(token: str, request: Request, session: SessionDep):
    ratelimit.hit(f"invite-ip:{client_ip(request)}", 30, 600)
    invitation = await _invitation(session, token)
    org = await session.get(Organization, invitation.organization_id)
    existing = await session.scalar(select(User.id).where(User.email == invitation.email))
    return {
        "email": invitation.email,
        "role": invitation.role,
        "organization": org.name if org else "",
        "existing_user": bool(existing),
    }


@router.post("/invitations/{token}/accept")
async def accept_invitation(
    token: str, body: AcceptInvitation, request: Request, response: Response, session: SessionDep
):
    ratelimit.hit(f"invite-ip:{client_ip(request)}", 30, 600)
    invitation = await _invitation(session, token)
    user = await session.scalar(select(User).where(User.email == invitation.email))
    if user:
        if not verify_password(body.password, user.password_hash):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Senha incorreta para este e-mail.")
    else:
        if problem := password_problem(body.password):
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, problem)
        user = User(email=invitation.email, name=body.name, password_hash=hash_password(body.password))
        session.add(user)
        await session.flush()
    already = await session.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.organization_id == invitation.organization_id
        )
    )
    if not already:
        session.add(Membership(user_id=user.id, organization_id=invitation.organization_id, role=invitation.role))
    invitation.accepted_at = utcnow()
    audit_log.record(
        session,
        organization_id=invitation.organization_id,
        workspace_id=None,
        action="invitation.accepted",
        actor_id=user.id,
        actor_name=user.name,
        resource_type="user",
        resource_id=user.id,
        result=invitation.role,
    )
    await open_session(session, request, response, user)
    await session.commit()
    return await me_payload(session, user)
