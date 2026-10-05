import logging
from typing import Any

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import utcnow
from ..deps import Context
from ..domain import (
    FUNDS_CONFIRMATION_TEXT,
    PLAN_PROVIDER,
    ApprovalPurpose,
    GoogleSearchCampaignPlan,
    PlanKind,
    PlanStatus,
    Provider,
    TikTokCampaignPlan,
    approval_purpose,
    canonical_hash,
    dump_plan,
    parse_plan,
)
from ..models import AdAccount, Approval, Execution, Plan, PlanRevision, Workspace
from ..policy import PolicyDecision, evaluate_plan
from ..providers import ProviderError, gateway
from . import accounts, audit_log, connections, jobs, revert, usage

log = logging.getLogger("aln.plans")
FINAL_EXECUTION = {"SUCCEEDED", "FAILED"}


def _validation_error(error: ValidationError) -> HTTPException:
    problems = [
        {"field": ".".join(str(p) for p in item["loc"]), "message": item["msg"]}
        for item in error.errors(include_url=False)[:30]
    ]
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, {"message": "Plano inválido.", "problems": problems})


def parse(kind: PlanKind, content: dict[str, Any]):
    try:
        return parse_plan(kind, content)
    except ValidationError as error:
        raise _validation_error(error) from error


def plan_hash(plan: Plan) -> str:
    return canonical_hash(plan.content)


def _title(model: Any) -> str:
    if isinstance(model, GoogleSearchCampaignPlan | TikTokCampaignPlan):
        return model.name
    actions = ", ".join(sorted({c.action.replace("_", " ").lower() for c in model.changes}))
    return f"Alteração: {actions}"[:200]


def _with_account(kind: PlanKind, content: dict[str, Any], account: AdAccount) -> dict[str, Any]:
    key = "customer_id" if PLAN_PROVIDER[kind] == Provider.GOOGLE_ADS else "advertiser_id"
    return {**content, key: account.external_id}


async def get_plan(session: AsyncSession, ctx: Context, plan_id: str) -> Plan:
    plan = await session.get(Plan, plan_id)
    if not plan or plan.organization_id != ctx.organization_id or plan.workspace_id != ctx.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plano não encontrado.")
    return plan


def _audit(
    session: AsyncSession, ctx: Context, action: str, plan: Plan, result: str, details: dict[str, Any] | None = None
) -> None:
    audit_log.record(
        session,
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        action=action,
        actor_id=ctx.user.id,
        actor_name=ctx.user.name,
        resource_type="plan",
        resource_id=plan.id,
        result=result,
        details=details,
    )


async def create_plan(
    session: AsyncSession,
    ctx: Context,
    *,
    kind: PlanKind,
    account_id: str,
    content: dict[str, Any],
    source: str = "manual",
    title: str | None = None,
    reverts_execution_id: str | None = None,
) -> Plan:
    account = await accounts.account_for(session, ctx, account_id)
    if account.provider != PLAN_PROVIDER[kind]:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "O tipo de plano não combina com a conta escolhida.")
    model = parse(kind, _with_account(kind, content, account))
    plan = Plan(
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        ad_account_id=account.id,
        provider=account.provider,
        kind=kind.value,
        title=(title or _title(model))[:200],
        content=dump_plan(model),
        source=source,
        created_by=ctx.user.id,
        reverts_execution_id=reverts_execution_id,
    )
    session.add(plan)
    await session.flush()
    session.add(
        PlanRevision(
            plan_id=plan.id, version=1, content=plan.content, content_hash=plan_hash(plan), created_by=ctx.user.id
        )
    )
    _audit(session, ctx, "plan.created", plan, "success", {"kind": kind.value, "source": source})
    await session.commit()
    return plan


async def revise_plan(session: AsyncSession, ctx: Context, plan: Plan, content: dict[str, Any]) -> Plan:
    if plan.status in {PlanStatus.QUEUED, PlanStatus.EXECUTED}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plano já enviado para execução não pode ser editado.")
    account = await accounts.account_for(session, ctx, plan.ad_account_id or "")
    kind = PlanKind(plan.kind)
    model = parse(kind, _with_account(kind, content, account))
    new_content = dump_plan(model)
    if canonical_hash(new_content) == plan_hash(plan):
        return plan
    plan.version += 1
    plan.content = new_content
    plan.title = _title(model)
    plan.status = PlanStatus.DRAFT
    plan.validation = None  # every approval of the previous version stops matching
    session.add(
        PlanRevision(
            plan_id=plan.id,
            version=plan.version,
            content=new_content,
            content_hash=canonical_hash(new_content),
            created_by=ctx.user.id,
        )
    )
    _audit(session, ctx, "plan.revised", plan, "success", {"version": plan.version})
    await session.commit()
    return plan


def _policy(plan: Plan, workspace: Workspace, account: AdAccount) -> PolicyDecision:
    return evaluate_plan(
        parse_plan(PlanKind(plan.kind), plan.content),
        daily_budget_limit=workspace.daily_budget_limit,
        kill_switch=settings.global_kill_switch,
        account_currency=account.currency,
    )


async def validate_plan(session: AsyncSession, ctx: Context, plan: Plan) -> dict[str, Any]:
    if plan.status in {PlanStatus.QUEUED, PlanStatus.EXECUTED}:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plano já executado.")
    account = await accounts.account_for(session, ctx, plan.ad_account_id or "")
    decision = _policy(plan, ctx.workspace, account)
    model = parse_plan(PlanKind(plan.kind), plan.content)
    structural = [v for v in decision.violations if "kill switch" not in v]
    remote_status, remote_errors = "skipped", []
    if not structural:
        try:
            connection = await accounts.connection_of(session, account)
            creds = await connections.credentials(session, connection)
            with usage.count_requests() as counter:
                try:
                    remote_errors = await gateway(plan.provider).validate(
                        creds, accounts.account_ref(account), PlanKind(plan.kind), model
                    )
                finally:
                    await usage.record(session, plan.provider, counter[0])
            remote_status = "rejected" if remote_errors else "ok"
        except ProviderError as failure:
            remote_status, remote_errors = "unavailable", [failure.message, *failure.details]
    allowed = decision.allowed and remote_status == "ok"
    plan.status = PlanStatus.VALIDATED if allowed else PlanStatus.BLOCKED
    plan.validation = {
        "allowed": allowed,
        "plan_hash": plan_hash(plan),
        "plan_version": plan.version,
        "violations": list(decision.violations),
        "warnings": list(decision.warnings),
        "remote_status": remote_status,
        "remote_errors": remote_errors[:30],
        "purpose": approval_purpose(model).value,
        "policy_snapshot": decision.snapshot,
        "validated_at": utcnow().isoformat(),
    }
    _audit(
        session,
        ctx,
        "plan.validated",
        plan,
        "allowed" if allowed else "blocked",
        {"violations": list(decision.violations), "remote_status": remote_status},
    )
    await session.commit()
    return plan.validation


async def approve_plan(
    session: AsyncSession, ctx: Context, plan: Plan, *, plan_hash_seen: str, confirm_funds: bool
) -> Approval:
    current = plan_hash(plan)
    if plan_hash_seen != current:
        raise HTTPException(status.HTTP_409_CONFLICT, "O plano mudou depois que você o revisou. Revise de novo.")
    validation = plan.validation or {}
    if (
        plan.status != PlanStatus.VALIDATED
        or validation.get("plan_hash") != current
        or validation.get("plan_version") != plan.version
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "O plano precisa estar validado nesta versão antes da aprovação.")
    account = await accounts.account_for(session, ctx, plan.ad_account_id or "")
    decision = _policy(plan, ctx.workspace, account)
    if not decision.allowed:
        plan.status = PlanStatus.BLOCKED
        await session.commit()
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"message": "Bloqueado pela política.", "violations": list(decision.violations)}
        )
    purpose = approval_purpose(parse_plan(PlanKind(plan.kind), plan.content))
    if purpose == ApprovalPurpose.BUDGET_CHANGE and not confirm_funds:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, f"Confirme: “{FUNDS_CONFIRMATION_TEXT}”")
    approval = Approval(
        plan_id=plan.id,
        plan_version=plan.version,
        plan_hash=current,
        purpose=purpose.value,
        approved_by=ctx.user.id,
        approved_by_name=ctx.user.name,
        financial_confirmation=confirm_funds and purpose == ApprovalPurpose.BUDGET_CHANGE,
        policy_snapshot=decision.snapshot,
    )
    session.add(approval)
    plan.status = PlanStatus.APPROVED
    _audit(
        session,
        ctx,
        "plan.approved",
        plan,
        purpose.value.lower(),
        {"version": plan.version, "financial_confirmation": approval.financial_confirmation},
    )
    await session.commit()
    return approval


async def execute_plan(session: AsyncSession, ctx: Context, plan: Plan, idempotency_key: str) -> Execution:
    existing = await session.scalar(
        select(Execution).where(
            Execution.organization_id == ctx.organization_id, Execution.idempotency_key == idempotency_key
        )
    )
    if existing:
        if existing.plan_id != plan.id:
            raise HTTPException(status.HTTP_409_CONFLICT, "Idempotency-Key já usada em outro plano.")
        return existing
    approval = await session.scalar(
        select(Approval).where(Approval.plan_id == plan.id).order_by(Approval.created_at.desc()).limit(1)
    )
    if (
        not approval
        or approval.consumed_at
        or approval.plan_hash != plan_hash(plan)
        or approval.plan_version != plan.version
    ):
        raise HTTPException(status.HTTP_409_CONFLICT, "Aprovação ausente, já usada ou de outra versão do plano.")
    if plan.status != PlanStatus.APPROVED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plano não está aprovado.")
    if not settings.mutations_enabled(plan.provider):
        raise HTTPException(status.HTTP_423_LOCKED, "Mutações desligadas (kill switch global ou flag da plataforma).")
    account = await accounts.account_for(session, ctx, plan.ad_account_id or "")
    decision = _policy(plan, ctx.workspace, account)
    if not decision.allowed:
        raise HTTPException(
            status.HTTP_409_CONFLICT, {"message": "Bloqueado pela política.", "violations": list(decision.violations)}
        )
    execution = Execution(
        organization_id=ctx.organization_id,
        workspace_id=ctx.workspace_id,
        plan_id=plan.id,
        approval_id=approval.id,
        idempotency_key=idempotency_key,
        requested_by=ctx.user.id,
    )
    session.add(execution)
    approval.consumed_at = utcnow()
    plan.status = PlanStatus.QUEUED
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(
            select(Execution).where(
                Execution.organization_id == ctx.organization_id, Execution.idempotency_key == idempotency_key
            )
        )
        if existing:
            return existing
        raise
    await jobs.enqueue(session, "EXECUTE_PLAN", {"execution_id": execution.id})
    _audit(session, ctx, "plan.execution_queued", plan, "queued", {"execution_id": execution.id})
    await session.commit()
    return execution


async def _finish(
    session: AsyncSession,
    execution: Execution,
    plan: Plan,
    *,
    ok: bool,
    message: str,
    details: dict[str, Any] | None = None,
) -> None:
    execution.status = "SUCCEEDED" if ok else "FAILED"
    execution.finished_at = utcnow()
    plan.status = PlanStatus.EXECUTED if ok else PlanStatus.FAILED
    if not ok:
        execution.error = message[:500]
    audit_log.record(
        session,
        organization_id=execution.organization_id,
        workspace_id=execution.workspace_id,
        action="plan.executed" if ok else "plan.execution_failed",
        actor_id=execution.requested_by,
        actor_name="worker",
        resource_type="plan",
        resource_id=plan.id,
        result=message[:40],
        details={"execution_id": execution.id, **(details or {})},
    )
    await session.commit()


async def run_execution(session: AsyncSession, execution_id: str) -> None:
    """Called by the worker. Re-checks every guard: things may have changed since approval."""
    execution = await session.get(Execution, execution_id)
    if not execution or execution.status in FINAL_EXECUTION:
        return
    plan = await session.get(Plan, execution.plan_id)
    approval = await session.get(Approval, execution.approval_id)
    account = await session.get(AdAccount, plan.ad_account_id) if plan and plan.ad_account_id else None
    if not plan or not approval or not account:
        if plan:
            await _finish(session, execution, plan, ok=False, message="Plano, aprovação ou conta não existem mais.")
        return
    if approval.plan_hash != plan_hash(plan) or approval.plan_version != plan.version:
        await _finish(session, execution, plan, ok=False, message="O plano mudou depois da aprovação.")
        return
    if not settings.mutations_enabled(plan.provider):
        await _finish(session, execution, plan, ok=False, message="Mutações desligadas no momento da execução.")
        return
    execution.status = "RUNNING"
    await session.commit()

    kind = PlanKind(plan.kind)
    model = parse_plan(kind, plan.content)
    try:
        connection = await accounts.connection_of(session, account)
        creds = await connections.credentials(session, connection)
        with usage.count_requests() as counter:
            try:
                result = await gateway(plan.provider).execute(creds, accounts.account_ref(account), kind, model)
            finally:
                await usage.record(session, plan.provider, counter[0])
    except ProviderError as failure:
        if failure.retryable:
            execution.status, execution.error = "RETRYING", failure.message[:500]
            await session.commit()
            raise jobs.RetryableJobError(failure.message) from failure
        await _finish(session, execution, plan, ok=False, message=failure.message, details={"errors": failure.details})
        return
    execution.result = {"status": result.status, **result.resources}
    execution.before_state = result.before or None
    execution.after_state = result.after or None
    await _finish(
        session,
        execution,
        plan,
        ok=True,
        message=result.status.lower(),
        details={"status": result.status, "operations": result.operations},
    )


async def fail_dead_execution(session: AsyncSession, execution_id: str, error: str) -> None:
    execution = await session.get(Execution, execution_id)
    if execution and execution.status not in FINAL_EXECUTION:
        plan = await session.get(Plan, execution.plan_id)
        if plan:
            await _finish(session, execution, plan, ok=False, message=f"Falhou após várias tentativas: {error}")


async def create_revert(session: AsyncSession, ctx: Context, execution: Execution) -> Plan:
    if execution.status != "SUCCEEDED":
        raise HTTPException(status.HTTP_409_CONFLICT, "Só é possível reverter execuções concluídas.")
    plan = await get_plan(session, ctx, execution.plan_id)
    inverse = revert.inverse(PlanKind(plan.kind), plan.content, execution.before_state, execution.result)
    if not inverse:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Esta execução não tem reversão automática. Desfaça pela plataforma."
        )
    kind, content = inverse
    return await create_plan(
        session,
        ctx,
        kind=kind,
        account_id=plan.ad_account_id or "",
        content=content,
        source="revert",
        title=f"Reverter: {plan.title}",
        reverts_execution_id=execution.id,
    )
