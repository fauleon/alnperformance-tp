from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from pydantic import BaseModel

from ..domain import AnyPlan, PlanKind
from ..snapshot import AccountSnapshot


class ProviderError(Exception):
    """A provider failure, already translated into something safe to show and to audit."""

    def __init__(
        self, message: str, *, retryable: bool = False, needs_reconnect: bool = False, details: list[str] | None = None
    ) -> None:
        super().__init__(message)
        self.message = message
        self.retryable = retryable
        self.needs_reconnect = needs_reconnect
        self.details = details or []


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str | None = None
    expires_in: int | None = None
    scopes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Credentials:
    access_token: str | None
    refresh_token: str | None = None


@dataclass
class AccountRef:
    external_id: str
    login_customer_id: str | None = None
    currency: str | None = None


class DiscoveredAccount(BaseModel):
    external_id: str
    name: str
    currency: str | None = None
    time_zone: str | None = None
    login_customer_id: str | None = None
    is_manager: bool = False
    is_test_account: bool = False
    selectable: bool = True
    parent_name: str | None = None


@dataclass
class ExecutionResult:
    status: str  # CREATED_PAUSED | APPLIED | ALREADY_EXISTS
    resources: dict[str, Any] = field(default_factory=dict)
    before: dict[str, Any] = field(default_factory=dict)
    after: dict[str, Any] = field(default_factory=dict)
    operations: int = 0


class AdsGateway(Protocol):
    provider: str
    supports_pkce: bool

    def authorization_url(self, *, state: str, redirect_uri: str, code_challenge: str | None) -> str: ...

    async def exchange_code(self, *, code: str, redirect_uri: str, code_verifier: str | None) -> TokenBundle: ...

    async def refresh(self, refresh_token: str) -> TokenBundle: ...

    async def revoke(self, token: str) -> None: ...

    async def discover_accounts(
        self, creds: Credentials, token: TokenBundle | None = None
    ) -> list[DiscoveredAccount]: ...

    async def snapshot(self, creds: Credentials, account: AccountRef, start: date, end: date) -> AccountSnapshot: ...

    async def validate(self, creds: Credentials, account: AccountRef, kind: PlanKind, plan: AnyPlan) -> list[str]: ...

    async def execute(
        self, creds: Credentials, account: AccountRef, kind: PlanKind, plan: AnyPlan
    ) -> ExecutionResult: ...

    async def reconcile(self, creds: Credentials, account: AccountRef, campaign_ids: list[str]) -> dict[str, str]: ...
