import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import ratelimit
from .config import settings
from .db import create_all
from .deps import client_ip
from .logging_setup import configure_logging
from .providers import ProviderError
from .routers import auth, connections, copilot, insights, plans, workspaces
from .security import EncryptionNotConfigured

log = logging.getLogger("aln.api")
MAX_BODY_BYTES = 512 * 1024
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}
CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "alnia"


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    if settings.database_url.startswith("sqlite"):
        await create_all()  # local development only; production runs migrations
    worker_task = None
    stop = asyncio.Event()
    if settings.run_worker_in_api:
        from .worker import run_forever

        worker_task = asyncio.create_task(run_forever(stop))
    yield
    stop.set()
    if worker_task:
        with suppress(asyncio.CancelledError, TimeoutError):
            await asyncio.wait_for(worker_task, timeout=10)


app = FastAPI(
    title="ALN Hub ia API",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None,
    openapi_url=None if settings.is_production else "/openapi.json",
)


@app.middleware("http")
async def guard(request: Request, call_next):
    """Body limit, global rate limit, CSRF (custom header + allowed Origin) and security headers."""
    if request.method in UNSAFE:
        length = request.headers.get("content-length")
        if length and length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "Requisição grande demais."}, status_code=413)
        origin = request.headers.get("origin")
        if request.headers.get(CSRF_HEADER) != CSRF_VALUE or (
            origin and origin.rstrip("/") not in settings.allowed_origins
        ):
            return JSONResponse({"detail": "Origem não autorizada."}, status_code=403)
    if request.url.path != "/health":
        try:
            ratelimit.hit(f"ip:{client_ip(request)}", 600, 60)
        except StarletteHTTPException as error:
            return JSONResponse({"detail": error.detail}, status_code=error.status_code, headers=error.headers)
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    if settings.is_production:
        response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    allow_headers=["Content-Type", "X-Workspace-Id", "Idempotency-Key", "X-Requested-With"],
    max_age=600,
)


@app.exception_handler(ProviderError)
async def provider_error(request: Request, error: ProviderError):
    code = 409 if error.needs_reconnect else 503 if error.retryable else 502
    return JSONResponse(
        {
            "detail": {
                "message": error.message,
                "problems": error.details,
                "needs_reconnect": error.needs_reconnect,
                "retryable": error.retryable,
            }
        },
        status_code=code,
    )


@app.exception_handler(EncryptionNotConfigured)
async def encryption_error(request: Request, error: EncryptionNotConfigured):
    log.error("encryption.not_configured")
    return JSONResponse({"detail": "Criptografia de tokens não configurada no servidor."}, status_code=503)


@app.get("/health", include_in_schema=False)
async def health() -> dict[str, str]:
    return {"status": "ok", "mutations": "disabled" if settings.global_kill_switch else "enabled"}


for module in (auth, workspaces, connections, insights, plans, copilot):
    app.include_router(module.router)
