"""Sliding-window rate limiter kept in process memory.

Good for a single API replica (the Railway default). With more replicas, each one limits on its own,
which still bounds abuse at replicas × limit.
"""

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, status

_hits: dict[str, deque[float]] = defaultdict(deque)
_lock = Lock()


def hit(key: str, limit: int, window_seconds: int) -> None:
    now = time.monotonic()
    with _lock:
        bucket = _hits[key]
        while bucket and now - bucket[0] > window_seconds:
            bucket.popleft()
        if len(bucket) >= limit:
            retry = int(window_seconds - (now - bucket[0])) + 1
            raise HTTPException(
                status.HTTP_429_TOO_MANY_REQUESTS,
                "Muitas tentativas. Aguarde um pouco.",
                headers={"Retry-After": str(retry)},
            )
        bucket.append(now)
        if len(_hits) > 50_000:  # keep memory bounded
            for stale in [k for k, v in _hits.items() if not v or now - v[-1] > 3600][:10_000]:
                _hits.pop(stale, None)


def reset() -> None:
    with _lock:
        _hits.clear()
