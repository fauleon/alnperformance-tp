import hashlib
import hmac
import json
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Annotated
from uuid import UUID

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .domain import Approval, AuditEvent, GoogleSearchCampaignPlan, PlanRecord, PlanStatus
from .policy import evaluate_plan
from .providers import ProviderName, capabilities
from .storage import AdConnection, create_tables, db_session, encrypt
from .store import store

app = FastAPI(title="ALN Performance AI Ads Manager", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup() -> None:
    await create_tables()

DEMO_ORG = UUID("11111111-1111-4111-8111-111111111111")
DEMO_WORKSPACE = UUID("22222222-2222-4222-8222-222222222222")


class TenantContext(BaseModel):
    organization_id: UUID
    workspace_id: UUID


def tenant_context(
    x_organization_id: Annotated[UUID, Header()] = DEMO_ORG,
    x_workspace_id: Annotated[UUID, Header()] = DEMO_WORKSPACE,
) -> TenantContext:
    return TenantContext(organization_id=x_organization_id, workspace_id=x_workspace_id)


def owned_plan(plan_id: UUID, tenant: TenantContext) -> PlanRecord:
    plan = store.plans.get(plan_id)
    if not plan or plan.organization_id != tenant.organization_id or plan.workspace_id != tenant.workspace_id:
        raise HTTPException(status_code=404, detail="Plano não encontrado")
    return plan


def audit(tenant: TenantContext, action: str, actor: str, resource_id: str, result: str) -> None:
    store.audits.append(AuditEvent(
        organization_id=tenant.organization_id,
        workspace_id=tenant.workspace_id,
        action=action,
        actor=actor,
        resource_id=resource_id,
        result=result,
    ))


def signed_oauth_state(tenant: TenantContext) -> str:
    if not settings.oauth_state_secret:
        raise HTTPException(status_code=503, detail="OAuth state secret ainda não configurado")
    payload = json.dumps({"o": str(tenant.organization_id), "w": str(tenant.workspace_id), "t": int(datetime.now(UTC).timestamp())}, separators=(",", ":")).encode()
    signature = hmac.new(settings.oauth_state_secret.encode(), payload, hashlib.sha256).digest()
    return urlsafe_b64encode(payload + b"." + signature).decode().rstrip("=")


def verify_oauth_state(state: str) -> TenantContext:
    try:
        raw = urlsafe_b64decode(state + "=" * (-len(state) % 4))
        payload, signature = raw.rsplit(b".", 1)
        expected = hmac.new((settings.oauth_state_secret or "").encode(), payload, hashlib.sha256).digest()
        if not hmac.compare_digest(signature, expected):
            raise ValueError("invalid signature")
        data = json.loads(payload)
        if int(datetime.now(UTC).timestamp()) - int(data["t"]) > 600:
            raise ValueError("expired")
        return TenantContext(organization_id=UUID(data["o"]), workspace_id=UUID(data["w"]))
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        raise HTTPException(status_code=400, detail="OAuth state inválido ou expirado") from error


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mutations": "disabled" if settings.global_kill_switch else "enabled"}


@app.get("/v1/providers")
async def provider_capabilities(
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> list[dict[str, object]]:
    state = signed_oauth_state(tenant)
    return [capabilities(provider, state).model_dump(mode="json") for provider in ProviderName]


@app.post("/v1/connections/{provider}/start")
async def start_provider_connection(
    provider: ProviderName,
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> dict[str, object]:
    state = signed_oauth_state(tenant)
    capability = capabilities(provider, state)
    if not capability.configured or not capability.oauth_url:
        raise HTTPException(status_code=503, detail=f"Credenciais de {provider.value} ainda não configuradas")
    audit(tenant, "provider.oauth_started", "demo-user", provider.value, "redirect")
    return {"provider": provider.value, "authorization_url": capability.oauth_url}


@app.get("/v1/connections/google/callback")
async def google_callback(
    code: Annotated[str, Query(min_length=4)],
    state: Annotated[str, Query(min_length=20)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> dict[str, str]:
    tenant = verify_oauth_state(state)
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post("https://oauth2.googleapis.com/token", data={
            "code": code,
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "redirect_uri": f"{settings.public_api_url}/v1/connections/google/callback",
            "grant_type": "authorization_code",
        })
    if response.is_error:
        raise HTTPException(status_code=400, detail="Google recusou a troca do código OAuth")
    token = response.json()
    existing = await session.scalar(select(AdConnection).where(
        AdConnection.organization_id == str(tenant.organization_id),
        AdConnection.workspace_id == str(tenant.workspace_id),
        AdConnection.provider == ProviderName.GOOGLE_ADS.value,
    ))
    connection = existing or AdConnection(organization_id=str(tenant.organization_id), workspace_id=str(tenant.workspace_id), provider=ProviderName.GOOGLE_ADS.value, encrypted_access_token="")
    connection.encrypted_access_token = encrypt(token["access_token"]) or ""
    connection.encrypted_refresh_token = encrypt(token.get("refresh_token")) or connection.encrypted_refresh_token
    connection.expires_at = datetime.now(UTC) + timedelta(seconds=int(token.get("expires_in", 3600)))
    session.add(connection)
    await session.commit()
    audit(tenant, "provider.connected", "oauth-google", ProviderName.GOOGLE_ADS.value, "success")
    return {"status": "connected", "provider": ProviderName.GOOGLE_ADS.value}


@app.get("/v1/connections")
async def list_connections(
    tenant: Annotated[TenantContext, Depends(tenant_context)],
    session: Annotated[AsyncSession, Depends(db_session)],
) -> list[dict[str, object]]:
    result = await session.scalars(select(AdConnection).where(
        AdConnection.organization_id == str(tenant.organization_id),
        AdConnection.workspace_id == str(tenant.workspace_id),
    ))
    return [{"provider": item.provider, "connected": True, "account_id": item.provider_account_id, "expires_at": item.expires_at} for item in result]


@app.post("/v1/plans", response_model=PlanRecord, status_code=status.HTTP_201_CREATED)
async def create_plan(
    plan: GoogleSearchCampaignPlan,
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> PlanRecord:
    record = PlanRecord(organization_id=tenant.organization_id, workspace_id=tenant.workspace_id, content=plan)
    store.plans[record.id] = record
    audit(tenant, "plan.created", "demo-user", str(record.id), "success")
    return record


@app.get("/v1/plans", response_model=list[PlanRecord])
async def list_plans(
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> list[PlanRecord]:
    return [p for p in store.plans.values() if p.organization_id == tenant.organization_id and p.workspace_id == tenant.workspace_id]


@app.post("/v1/plans/{plan_id}/validate")
async def validate(
    plan_id: UUID,
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> dict[str, object]:
    plan = owned_plan(plan_id, tenant)
    decision = evaluate_plan(
        plan.content,
        daily_budget_limit=Decimal(settings.default_daily_budget_limit),
        kill_switch=False,
    )
    plan.status = PlanStatus.VALIDATED if decision.allowed else PlanStatus.BLOCKED
    audit(tenant, "plan.validated", "policy-engine", str(plan.id), "allowed" if decision.allowed else "blocked")
    return {"allowed": decision.allowed, "violations": decision.violations, "policy_snapshot": decision.snapshot, "plan_hash": plan.canonical_hash}


class ApprovalRequest(BaseModel):
    approved_by: str = Field(min_length=2, max_length=120)


@app.post("/v1/plans/{plan_id}/approve", response_model=Approval)
async def approve(
    plan_id: UUID,
    request: ApprovalRequest,
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> Approval:
    plan = owned_plan(plan_id, tenant)
    if plan.status != PlanStatus.VALIDATED:
        raise HTTPException(status_code=409, detail="O plano precisa estar validado antes da aprovação")
    decision = evaluate_plan(plan.content, daily_budget_limit=Decimal(settings.default_daily_budget_limit), kill_switch=False)
    approval = Approval(
        plan_id=plan.id,
        plan_version=plan.version,
        plan_hash=plan.canonical_hash,
        purpose="CREATE_PAUSED",
        approved_by=request.approved_by,
        policy_snapshot=decision.snapshot,
    )
    store.approvals[plan.id] = approval
    plan.status = PlanStatus.APPROVED
    audit(tenant, "plan.approved", request.approved_by, str(plan.id), "success")
    return approval


def simulated_execution(plan_id: UUID, tenant: TenantContext, key: str) -> None:
    plan = owned_plan(plan_id, tenant)
    plan.status = PlanStatus.CREATED_PAUSED
    result = {"execution_id": key, "status": "CREATED_PAUSED", "provider": "GOOGLE_ADS_SIMULATOR", "external_spend": "0.00"}
    store.idempotency[key] = result
    audit(tenant, "plan.executed", "execution-worker", str(plan.id), "created_paused")


@app.post("/v1/plans/{plan_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute(
    plan_id: UUID,
    background_tasks: BackgroundTasks,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> dict[str, object]:
    plan = owned_plan(plan_id, tenant)
    if idempotency_key in store.idempotency:
        return store.idempotency[idempotency_key]
    approval = store.approvals.get(plan.id)
    if not approval or approval.plan_hash != plan.canonical_hash or approval.plan_version != plan.version:
        raise HTTPException(status_code=409, detail="Aprovação ausente, expirada ou divergente")
    if plan.status != PlanStatus.APPROVED:
        raise HTTPException(status_code=409, detail="Plano não está aprovado")
    background_tasks.add_task(simulated_execution, plan.id, tenant, idempotency_key)
    queued = {"execution_id": idempotency_key, "status": "QUEUED", "provider": "GOOGLE_ADS_SIMULATOR"}
    store.idempotency[idempotency_key] = queued
    return queued


@app.get("/v1/audit", response_model=list[AuditEvent])
async def audit_log(
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> list[AuditEvent]:
    return [a for a in reversed(store.audits) if a.organization_id == tenant.organization_id and a.workspace_id == tenant.workspace_id]
