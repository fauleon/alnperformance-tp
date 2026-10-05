from typing import Annotated, Any

from fastapi import APIRouter, Header, HTTPException, Query, status
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select

from .. import ai, ratelimit
from ..deps import AdminCtx, CtxDep, SessionDep
from ..diff import describe, revision_diff
from ..domain import FUNDS_CONFIRMATION_TEXT, PlanKind, PlanStatus, Provider, approval_purpose, parse_plan
from ..models import Approval, Execution, Plan, PlanRevision
from ..providers import ProviderError, gateway
from ..services import accounts, connections, plans, usage
from ..templates import Briefing, PropertySheet, briefing_plan, real_estate_plan

router = APIRouter(prefix="/v1", tags=["plans"])


class PlanCreate(BaseModel):
    kind: PlanKind
    account_id: str = Field(max_length=36)
    content: dict[str, Any]
    title: str | None = Field(default=None, max_length=200)
    source: str = Field(default="manual", pattern="^(manual|copilot|audit|template)$")


class PlanUpdate(BaseModel):
    content: dict[str, Any]


class ApproveRequest(BaseModel):
    plan_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    confirm_funds: bool = False


class FromRealEstate(BaseModel):
    account_id: str = Field(max_length=36)
    sheet: PropertySheet


class FromBriefing(BaseModel):
    account_id: str = Field(max_length=36)
    briefing: Briefing
    use_keyword_ideas: bool = True


def plan_out(plan: Plan) -> dict[str, Any]:
    return {
        "id": plan.id,
        "kind": plan.kind,
        "provider": plan.provider,
        "title": plan.title,
        "status": plan.status,
        "version": plan.version,
        "source": plan.source,
        "account_id": plan.ad_account_id,
        "plan_hash": plans.plan_hash(plan),
        "created_at": plan.created_at,
        "updated_at": plan.updated_at,
        "reverts_execution_id": plan.reverts_execution_id,
    }


def execution_out(execution: Execution) -> dict[str, Any]:
    return {
        "id": execution.id,
        "plan_id": execution.plan_id,
        "status": execution.status,
        "idempotency_key": execution.idempotency_key,
        "result": execution.result,
        "error": execution.error,
        "before": execution.before_state,
        "after": execution.after_state,
        "created_at": execution.created_at,
        "finished_at": execution.finished_at,
    }


@router.get("/plans")
async def list_plans(
    ctx: CtxDep, session: SessionDep, status_filter: Annotated[str | None, Query(alias="status", max_length=24)] = None
):
    query = select(Plan).where(Plan.organization_id == ctx.organization_id, Plan.workspace_id == ctx.workspace_id)
    if status_filter:
        query = query.where(Plan.status == status_filter)
    else:
        query = query.where(Plan.status != PlanStatus.ARCHIVED)
    return [plan_out(p) for p in await session.scalars(query.order_by(Plan.updated_at.desc()).limit(200))]


@router.post("/plans", status_code=status.HTTP_201_CREATED)
async def create(body: PlanCreate, ctx: AdminCtx, session: SessionDep):
    plan = await plans.create_plan(
        session,
        ctx,
        kind=body.kind,
        account_id=body.account_id,
        content=body.content,
        source=body.source,
        title=body.title,
    )
    return plan_out(plan)


@router.get("/plans/{plan_id}")
async def detail(plan_id: str, ctx: CtxDep, session: SessionDep):
    plan = await plans.get_plan(session, ctx, plan_id)
    revisions = list(
        await session.scalars(
            select(PlanRevision).where(PlanRevision.plan_id == plan.id).order_by(PlanRevision.version)
        )
    )
    approvals = await session.scalars(
        select(Approval).where(Approval.plan_id == plan.id).order_by(Approval.created_at.desc())
    )
    executions = await session.scalars(
        select(Execution).where(Execution.plan_id == plan.id).order_by(Execution.created_at.desc())
    )
    snapshot = None
    account = None
    if plan.ad_account_id:
        try:
            account = await accounts.account_for(session, ctx, plan.ad_account_id)
            if plan.kind in {PlanKind.GOOGLE_CHANGE, PlanKind.TIKTOK_CHANGE}:
                snapshot = await accounts.snapshot(session, account)
        except (HTTPException, ProviderError):
            snapshot = None
    model = parse_plan(PlanKind(plan.kind), plan.content)
    return {
        **plan_out(plan),
        "content": plan.content,
        "validation": plan.validation,
        "purpose": approval_purpose(model).value,
        "funds_confirmation_text": FUNDS_CONFIRMATION_TEXT,
        "account": {
            "id": account.id,
            "name": account.name,
            "external_id": account.external_id,
            "currency": account.currency,
        }
        if account
        else None,
        "changes": describe(PlanKind(plan.kind), plan.content, snapshot),
        "revisions": [
            {"version": r.version, "created_at": r.created_at, "content_hash": r.content_hash} for r in revisions
        ],
        "last_revision_diff": revision_diff(revisions[-2].content, revisions[-1].content) if len(revisions) > 1 else [],
        "approvals": [
            {
                "id": a.id,
                "version": a.plan_version,
                "purpose": a.purpose,
                "approved_by": a.approved_by_name,
                "approved_at": a.created_at,
                "consumed": bool(a.consumed_at),
                "financial_confirmation": a.financial_confirmation,
            }
            for a in approvals
        ],
        "executions": [execution_out(e) for e in executions],
    }


@router.put("/plans/{plan_id}")
async def revise(plan_id: str, body: PlanUpdate, ctx: AdminCtx, session: SessionDep):
    plan = await plans.get_plan(session, ctx, plan_id)
    return plan_out(await plans.revise_plan(session, ctx, plan, body.content))


@router.post("/plans/{plan_id}/validate")
async def validate(plan_id: str, ctx: AdminCtx, session: SessionDep):
    plan = await plans.get_plan(session, ctx, plan_id)
    return await plans.validate_plan(session, ctx, plan)


@router.post("/plans/{plan_id}/approve")
async def approve(plan_id: str, body: ApproveRequest, ctx: AdminCtx, session: SessionDep):
    plan = await plans.get_plan(session, ctx, plan_id)
    approval = await plans.approve_plan(
        session, ctx, plan, plan_hash_seen=body.plan_hash, confirm_funds=body.confirm_funds
    )
    return {
        "id": approval.id,
        "purpose": approval.purpose,
        "plan_version": approval.plan_version,
        "plan_hash": approval.plan_hash,
        "approved_by": approval.approved_by_name,
    }


@router.post("/plans/{plan_id}/execute", status_code=status.HTTP_202_ACCEPTED)
async def execute(
    plan_id: str,
    ctx: AdminCtx,
    session: SessionDep,
    idempotency_key: Annotated[str, Header(min_length=8, max_length=128)],
):
    plan = await plans.get_plan(session, ctx, plan_id)
    return execution_out(await plans.execute_plan(session, ctx, plan, idempotency_key))


@router.post("/plans/{plan_id}/archive")
async def archive(plan_id: str, ctx: AdminCtx, session: SessionDep):
    plan = await plans.get_plan(session, ctx, plan_id)
    if plan.status == PlanStatus.QUEUED:
        raise HTTPException(status.HTTP_409_CONFLICT, "Plano em execução não pode ser arquivado.")
    plan.status = PlanStatus.ARCHIVED
    await session.commit()
    return plan_out(plan)


@router.get("/executions/{execution_id}")
async def execution(execution_id: str, ctx: CtxDep, session: SessionDep):
    item = await session.get(Execution, execution_id)
    if not item or item.organization_id != ctx.organization_id or item.workspace_id != ctx.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execução não encontrada.")
    return execution_out(item)


@router.post("/executions/{execution_id}/revert", status_code=status.HTTP_201_CREATED)
async def revert(execution_id: str, ctx: AdminCtx, session: SessionDep):
    item = await session.get(Execution, execution_id)
    if not item or item.organization_id != ctx.organization_id or item.workspace_id != ctx.workspace_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Execução não encontrada.")
    return plan_out(await plans.create_revert(session, ctx, item))


@router.post("/plans/from-real-estate", status_code=status.HTTP_201_CREATED)
async def from_real_estate(body: FromRealEstate, ctx: AdminCtx, session: SessionDep):
    account = await accounts.account_for(session, ctx, body.account_id)
    content = real_estate_plan(body.sheet, account.external_id)
    plan = await plans.create_plan(
        session, ctx, kind=PlanKind.GOOGLE_SEARCH_CAMPAIGN, account_id=account.id, content=content, source="template"
    )
    return plan_out(plan)


@router.post("/plans/from-briefing", status_code=status.HTTP_201_CREATED)
async def from_briefing(body: FromBriefing, ctx: AdminCtx, session: SessionDep):
    ratelimit.hit(f"briefing:{ctx.user.id}", 10, 600)
    account = await accounts.account_for(session, ctx, body.account_id)
    if account.provider != Provider.GOOGLE_ADS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Briefing para TikTok: use o formulário de campanha."
        )
    try:
        fallback = briefing_plan(body.briefing, account.external_id)
        parse_plan(PlanKind.GOOGLE_SEARCH_CAMPAIGN, fallback)
    except ValidationError as error:
        raise plans._validation_error(error) from error
    ideas: list[dict[str, Any]] = []
    notes = []
    if body.use_keyword_ideas:
        try:
            creds = await connections.credentials(session, await accounts.connection_of(session, account))
            with usage.count_requests() as counter:
                try:
                    ideas = await gateway(account.provider).keyword_ideas(
                        creds,
                        accounts.account_ref(account),
                        seeds=body.briefing.seed_keywords[:20],
                        url=str(body.briefing.landing_page),
                        geo_ids=body.briefing.geo_target_ids,
                    )
                finally:
                    await usage.record(session, account.provider, counter[0])
        except ProviderError as failure:
            notes.append(f"Sem ideias de palavras do Google agora: {failure.message}")
    generated = await ai.generate_plan(body.briefing.model_dump(mode="json"), ideas, account.external_id, fallback)
    plan = await plans.create_plan(
        session,
        ctx,
        kind=PlanKind.GOOGLE_SEARCH_CAMPAIGN,
        account_id=account.id,
        content=generated["content"],
        source=generated["source"],
    )
    return {**plan_out(plan), "notes": " ".join([generated["notes"], *notes]).strip(), "keyword_ideas": ideas[:50]}
