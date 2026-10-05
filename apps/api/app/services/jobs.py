import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import utcnow
from ..models import Job

log = logging.getLogger("aln.jobs")
STALE_AFTER = timedelta(minutes=15)


class RetryableJobError(Exception):
    """Transient failure: the job is retried with exponential backoff until max_attempts, then DEAD."""


def backoff(attempt: int) -> timedelta:
    return timedelta(seconds=min(30 * 2 ** max(attempt - 1, 0), 1800))


async def enqueue(
    session: AsyncSession,
    kind: str,
    payload: dict[str, Any],
    *,
    dedupe_key: str | None = None,
    run_after: datetime | None = None,
    max_attempts: int = 5,
) -> Job | None:
    """Adds a job to the current transaction. With a dedupe key, an existing job wins."""
    if dedupe_key and await session.scalar(select(Job.id).where(Job.dedupe_key == dedupe_key)):
        return None
    job = Job(
        kind=kind, payload=payload, dedupe_key=dedupe_key, run_after=run_after or utcnow(), max_attempts=max_attempts
    )
    session.add(job)
    try:
        await session.flush()
    except IntegrityError:  # another process enqueued the same dedupe key first
        await session.rollback()
        return None
    return job


async def claim(session: AsyncSession) -> Job | None:
    now = utcnow()
    query = (
        select(Job).where(Job.status.in_(("QUEUED", "RETRY")), Job.run_after <= now).order_by(Job.run_after).limit(1)
    )
    if session.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)
    job = await session.scalar(query)
    if not job:
        await session.rollback()
        return None
    job.status, job.locked_at, job.attempts = "RUNNING", now, job.attempts + 1
    await session.commit()
    return job


async def finish(session: AsyncSession, job: Job) -> None:
    job.status, job.finished_at, job.last_error = "DONE", utcnow(), None
    await session.commit()


async def fail(session: AsyncSession, job: Job, error: str, *, retryable: bool) -> bool:
    """Returns True when the job is dead (dead-letter) and needs attention."""
    job.last_error = error[:500]
    if retryable and job.attempts < job.max_attempts:
        job.status, job.run_after, job.locked_at = "RETRY", utcnow() + backoff(job.attempts), None
        await session.commit()
        return False
    job.status, job.finished_at = "DEAD", utcnow()
    await session.commit()
    log.error("job.dead_letter", extra={"job_id": job.id, "kind": job.kind, "error": error[:200]})
    return True


async def recover_stale(session: AsyncSession) -> int:
    """Jobs left RUNNING by a crashed worker go back to the queue."""
    result = await session.execute(
        update(Job)
        .where(Job.status == "RUNNING", Job.locked_at < utcnow() - STALE_AFTER)
        .values(status="RETRY", run_after=utcnow(), locked_at=None)
    )
    await session.commit()
    return getattr(result, "rowcount", 0) or 0
