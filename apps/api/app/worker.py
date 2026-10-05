"""Background worker: plan executions, nightly metric sync and reconciliation.

Run as its own Railway service: `python -m app.worker`. Several replicas are safe (SKIP LOCKED).
"""

import asyncio
import logging
import signal
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select

from .audit_rules import build_report
from .config import settings
from .db import SessionLocal, utcnow
from .logging_setup import configure_logging
from .models import AdAccount, AdConnection, AuthSession, Execution, Job, OAuthState, Plan, ProviderCache
from .providers import ProviderError, gateway
from .services import accounts, audit_log, connections, jobs, plans

log = logging.getLogger("aln.worker")
_last_schedule: datetime | None = None


async def handle(job: Job) -> None:
    async with SessionLocal() as session:
        if job.kind == "EXECUTE_PLAN":
            await plans.run_execution(session, job.payload["execution_id"])
        elif job.kind == "SYNC_METRICS":
            account = await session.get(AdAccount, job.payload["account_id"])
            if account:
                try:
                    snapshot = await accounts.snapshot(session, account, refresh=True, ttl_minutes=60 * 20)
                    report = build_report(snapshot)
                    if report.summary.get("critical"):
                        log.warning(
                            "audit.critical_findings",
                            extra={"account_id": account.id, "critical": report.summary["critical"]},
                        )
                except ProviderError as failure:
                    if failure.retryable:
                        raise jobs.RetryableJobError(failure.message) from failure
                    log.info("sync.skipped", extra={"account_id": account.id, "reason": failure.message})
        elif job.kind == "RECONCILE":
            await reconcile(session, job.payload["account_id"])
        else:
            log.error("job.unknown_kind", extra={"kind": job.kind})


async def reconcile(session, account_id: str) -> None:
    """Compares what this system created with what exists on the platform and records drift."""
    account = await session.get(AdAccount, account_id)
    if not account:
        return
    rows = await session.execute(
        select(Execution, Plan)
        .join(Plan, Plan.id == Execution.plan_id)
        .where(
            Plan.ad_account_id == account.id,
            Execution.status == "SUCCEEDED",
            Plan.kind.in_(("GOOGLE_SEARCH_CAMPAIGN", "TIKTOK_CAMPAIGN")),
        )
    )
    created: dict[str, str] = {}
    for execution, plan in rows:
        result = execution.result or {}
        campaign = result.get("campaign") or result.get("campaign_id")
        if campaign:
            created[str(campaign).rsplit("/", 1)[-1]] = plan.id
    if not created:
        return
    connection = await accounts.connection_of(session, account)
    try:
        states = await gateway(account.provider).reconcile(
            await connections.credentials(session, connection), accounts.account_ref(account), list(created)
        )
    except ProviderError as failure:
        if failure.retryable:
            raise jobs.RetryableJobError(failure.message) from failure
        return
    for campaign_id, state in states.items():
        if state in {"MISSING", "REMOVED"}:
            audit_log.record(
                session,
                organization_id=account.organization_id,
                workspace_id=account.workspace_id,
                action="reconcile.drift",
                actor_id=None,
                actor_name="reconciliação",
                resource_type="campaign",
                resource_id=campaign_id,
                result=state.lower(),
                details={"plan_id": created[campaign_id]},
            )
    await session.commit()


async def housekeeping() -> None:
    """Deletes expired sessions, OAuth states, finished jobs and stale metric caches (retention policy)."""
    now = utcnow()
    async with SessionLocal() as session:
        await session.execute(delete(AuthSession).where(AuthSession.expires_at < now))
        await session.execute(delete(OAuthState).where(OAuthState.expires_at < now - timedelta(days=1)))
        await session.execute(delete(ProviderCache).where(ProviderCache.expires_at < now - timedelta(days=1)))
        await session.execute(delete(Job).where(Job.status == "DONE", Job.finished_at < now - timedelta(days=30)))
        await session.commit()


async def schedule_daily() -> None:
    """Once a day (after METRICS_SYNC_HOUR_UTC) queue a sync and a reconciliation per linked account."""
    global _last_schedule
    now = datetime.now(UTC)
    if _last_schedule and now - _last_schedule < timedelta(minutes=10):
        return
    _last_schedule = now
    if now.hour < settings.metrics_sync_hour_utc:
        return
    day = now.date().isoformat()
    await housekeeping()
    async with SessionLocal() as session:
        linked = await session.execute(
            select(AdAccount.id)
            .join(AdConnection, AdConnection.id == AdAccount.connection_id)
            .where(AdConnection.status == "ACTIVE")
        )
        for (account_id,) in linked:
            for kind in ("SYNC_METRICS", "RECONCILE"):
                if await jobs.enqueue(
                    session, kind, {"account_id": account_id}, dedupe_key=f"{kind}:{day}:{account_id}", max_attempts=3
                ):
                    await session.commit()


async def run_once() -> bool:
    """Processes one job. Returns False when the queue is empty."""
    async with SessionLocal() as session:
        job = await jobs.claim(session)
    if not job:
        return False
    job_id, kind, payload = job.id, job.kind, job.payload
    try:
        await handle(job)
    except Exception as error:  # noqa: BLE001 - every failure retries with backoff, then dead-letters
        message = str(error) if isinstance(error, jobs.RetryableJobError) else f"{type(error).__name__}: {error}"
        if not isinstance(error, jobs.RetryableJobError):
            log.exception("job.failed", extra={"job_id": job_id, "kind": kind})
        async with SessionLocal() as session:
            current = await session.get(Job, job_id)
            if current and await jobs.fail(session, current, message, retryable=True) and kind == "EXECUTE_PLAN":
                await plans.fail_dead_execution(session, payload["execution_id"], message)
        return True
    async with SessionLocal() as session:
        current = await session.get(Job, job_id)
        if current:
            await jobs.finish(session, current)
    return True


async def run_forever(stop: asyncio.Event) -> None:
    log.info("worker.started")
    while not stop.is_set():
        try:
            await schedule_daily()
            async with SessionLocal() as session:
                await jobs.recover_stale(session)
            while not stop.is_set() and await run_once():
                pass
        except Exception:  # noqa: BLE001 - the loop must survive a bad iteration
            log.exception("worker.loop_error")
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.worker_poll_seconds)
        except TimeoutError:
            pass
    log.info("worker.stopped")


def main() -> None:
    configure_logging()
    stop = asyncio.Event()

    async def runner() -> None:
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:  # Windows
                pass
        await run_forever(stop)

    asyncio.run(runner())


if __name__ == "__main__":
    main()
