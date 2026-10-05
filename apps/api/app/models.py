from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base, JsonType, UTCDateTime, new_id, utcnow


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class User(TimestampMixin, Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Organization(TimestampMixin, Base):
    __tablename__ = "organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))


class Workspace(TimestampMixin, Base):
    """A client (advertiser) inside an organization. Ad accounts, plans and audit live here."""

    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    daily_budget_limit: Mapped[Decimal] = mapped_column(Numeric(14, 2))


class Membership(TimestampMixin, Base):
    __tablename__ = "memberships"
    __table_args__ = (UniqueConstraint("user_id", "organization_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(16))  # owner | admin | viewer


class Invitation(TimestampMixin, Base):
    __tablename__ = "invitations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id", ondelete="CASCADE"), index=True)
    email: Mapped[str] = mapped_column(String(254))
    role: Mapped[str] = mapped_column(String(16))
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_by: Mapped[str] = mapped_column(String(36))
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    accepted_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AuthSession(TimestampMixin, Base):
    __tablename__ = "auth_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(200), nullable=True)


class OAuthState(TimestampMixin, Base):
    """Single-use OAuth state with the PKCE verifier. The browser only ever sees a random nonce."""

    __tablename__ = "oauth_states"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    nonce_hash: Mapped[str] = mapped_column(String(64), unique=True)
    provider: Mapped[str] = mapped_column(String(24))
    organization_id: Mapped[str] = mapped_column(String(36))
    workspace_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(String(36))
    encrypted_code_verifier: Mapped[str | None] = mapped_column(Text, nullable=True)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AdConnection(TimestampMixin, Base):
    """One OAuth grant. A grant can reach many ad accounts (MCC hierarchy, TikTok advertisers)."""

    __tablename__ = "ad_connections"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    provider: Mapped[str] = mapped_column(String(24))
    status: Mapped[str] = mapped_column(String(24), default="ACTIVE")  # ACTIVE | NEEDS_RECONNECT | REVOKED
    encrypted_access_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    encrypted_refresh_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    access_token_expires_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    scopes: Mapped[str | None] = mapped_column(Text, nullable=True)
    discovered_accounts: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonType, nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class AdAccount(TimestampMixin, Base):
    __tablename__ = "ad_accounts"
    __table_args__ = (UniqueConstraint("workspace_id", "provider", "external_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    connection_id: Mapped[str] = mapped_column(ForeignKey("ad_connections.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(24))
    external_id: Mapped[str] = mapped_column(String(32))
    login_customer_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    time_zone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    is_test_account: Mapped[bool] = mapped_column(Boolean, default=False)


class Plan(TimestampMixin, Base):
    __tablename__ = "plans"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    ad_account_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    provider: Mapped[str] = mapped_column(String(24))
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(24), default="DRAFT")
    content: Mapped[dict[str, Any]] = mapped_column(JsonType)
    source: Mapped[str] = mapped_column(String(24), default="manual")
    validation: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    reverts_execution_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, onupdate=utcnow)


class PlanRevision(TimestampMixin, Base):
    __tablename__ = "plan_revisions"
    __table_args__ = (UniqueConstraint("plan_id", "version"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    content: Mapped[dict[str, Any]] = mapped_column(JsonType)
    content_hash: Mapped[str] = mapped_column(String(64))
    created_by: Mapped[str] = mapped_column(String(36))


class Approval(TimestampMixin, Base):
    __tablename__ = "approvals"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    plan_version: Mapped[int] = mapped_column(Integer)
    plan_hash: Mapped[str] = mapped_column(String(64))
    purpose: Mapped[str] = mapped_column(String(24))
    approved_by: Mapped[str] = mapped_column(String(36))
    approved_by_name: Mapped[str] = mapped_column(String(120))
    financial_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    policy_snapshot: Mapped[dict[str, Any]] = mapped_column(JsonType)
    consumed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Execution(TimestampMixin, Base):
    __tablename__ = "executions"
    __table_args__ = (UniqueConstraint("organization_id", "idempotency_key"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str] = mapped_column(String(36), index=True)
    plan_id: Mapped[str] = mapped_column(ForeignKey("plans.id", ondelete="CASCADE"), index=True)
    approval_id: Mapped[str] = mapped_column(String(36))
    idempotency_key: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(24), default="QUEUED")
    result: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    before_state: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    after_state: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(36))
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class Job(TimestampMixin, Base):
    """Durable work queue on Postgres (FOR UPDATE SKIP LOCKED). DEAD is the dead-letter state."""

    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType)
    dedupe_key: Mapped[str | None] = mapped_column(String(160), unique=True, nullable=True)
    status: Mapped[str] = mapped_column(String(16), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    run_after: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)
    locked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(500), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    workspace_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    action: Mapped[str] = mapped_column(String(64))
    actor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    actor_name: Mapped[str] = mapped_column(String(120))
    resource_type: Mapped[str] = mapped_column(String(40))
    resource_id: Mapped[str] = mapped_column(String(120))
    result: Mapped[str] = mapped_column(String(40))
    details: Mapped[dict[str, Any] | None] = mapped_column(JsonType, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow, index=True)


class ProviderCache(Base):
    __tablename__ = "provider_cache"
    key: Mapped[str] = mapped_column(String(200), primary_key=True)
    organization_id: Mapped[str] = mapped_column(String(36), index=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JsonType)
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)


class ApiUsage(Base):
    __tablename__ = "api_usage"
    __table_args__ = (UniqueConstraint("provider", "day"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    provider: Mapped[str] = mapped_column(String(24))
    day: Mapped[str] = mapped_column(String(10))
    operations: Mapped[int] = mapped_column(Integer, default=0)
