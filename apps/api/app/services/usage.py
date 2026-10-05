import logging
from contextlib import contextmanager
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..models import ApiUsage
from ..providers.google_ads import request_counter

log = logging.getLogger("aln.quota")


@contextmanager
def count_requests():
    counter = [0]
    token = request_counter.set(counter)
    try:
        yield counter
    finally:
        request_counter.reset(token)


async def record(session: AsyncSession, provider: str, operations: int) -> int:
    if operations <= 0:
        return 0
    day = datetime.now(UTC).date().isoformat()
    usage = await session.scalar(select(ApiUsage).where(ApiUsage.provider == provider, ApiUsage.day == day))
    if not usage:
        usage = ApiUsage(provider=provider, day=day, operations=0)
        session.add(usage)
    before = usage.operations
    usage.operations = before + operations
    quota = settings.google_ads_daily_operation_quota
    if provider == "GOOGLE_ADS" and before < quota * 0.8 <= usage.operations:
        log.warning("quota.alert", extra={"provider": provider, "operations": usage.operations, "quota": quota})
    return usage.operations


async def today(session: AsyncSession, provider: str) -> int:
    day = datetime.now(UTC).date().isoformat()
    usage = await session.scalar(select(ApiUsage).where(ApiUsage.provider == provider, ApiUsage.day == day))
    return usage.operations if usage else 0
