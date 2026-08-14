from decimal import Decimal
from typing import Annotated
from uuid import UUID

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .config import settings
from .domain import Approval, AuditEvent, GoogleSearchCampaignPlan, PlanRecord, PlanStatus
from .policy import evaluate_plan
from .providers import ProviderName, capabilities
from .store import store

app = FastAPI(title="ALN Performance AI Ads Manager", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "mutations": "disabled" if settings.global_kill_switch else "enabled"}


@app.get("/v1/providers")
async def provider_capabilities(
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> list[dict[str, object]]:
    state = f"{tenant.organization_id}:{tenant.workspace_id}"
    return [capabilities(provider, state).model_dump(mode="json") for provider in ProviderName]


@app.post("/v1/connections/{provider}/start")
async def start_provider_connection(
    provider: ProviderName,
    tenant: Annotated[TenantContext, Depends(tenant_context)],
) -> dict[str, object]:
    state = f"{tenant.organization_id}:{tenant.workspace_id}"
    capability = capabilities(provider, state)
    if not capability.configured or not capability.oauth_url:
        raise HTTPException(status_code=503, detail=f"Credenciais de {provider.value} ainda não configuradas")
    audit(tenant, "provider.oauth_started", "demo-user", provider.value, "redirect")
    return {"provider": provider.value, "authorization_url": capability.oauth_url}


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
