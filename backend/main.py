"""
Munim — FastAPI Application Entry Point
========================================
Initialises the application, registers routers, configures middleware,
and sets up error handling and monitoring.
"""

import asyncio
import logging
from contextlib import asynccontextmanager

import httpx
import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from db.neon_client import init_db, close_db
from routers import upload, analysis, reports, whatsapp, auth, ca, beta
from config import settings

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Sentry (error monitoring — free 5k errors/month)
# ---------------------------------------------------------------------------
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=0.1,
        environment=settings.APP_ENV,
    )

# ---------------------------------------------------------------------------
# Rate limiter (prevents abuse)
# ---------------------------------------------------------------------------
limiter = Limiter(key_func=get_remote_address)


# ---------------------------------------------------------------------------
# Lifespan (startup / shutdown)
# ---------------------------------------------------------------------------
async def _keep_alive_ping() -> None:
    """
    Ping own /health every 13 min to prevent Render free tier from sleeping.
    Render spins down after 15 min of inactivity — self-ping avoids that entirely.
    """
    await asyncio.sleep(90)           # Let startup finish first
    while True:
        try:
            url = f"{settings.APP_URL.rstrip('/')}/health"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
            logger.info("Keep-alive ping → %d", resp.status_code)
        except Exception as exc:
            logger.warning("Keep-alive ping failed: %s", exc)
        await asyncio.sleep(13 * 60)  # 13 minutes


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Munim API — environment: %s", settings.APP_ENV)
    # Init DB in background so the port opens immediately — Render scans
    # for an open port right away and kills the process if nothing is found.
    # Neon serverless DB can take 5-10 s to cold-start; blocking here causes
    # Render's port-scan timeout to fire before the socket is accepting.
    asyncio.create_task(_init_db_background())
    if settings.APP_ENV != "development":
        asyncio.create_task(_keep_alive_ping())
    yield
    await close_db()
    logger.info("Munim API shut down cleanly")


async def _init_db_background() -> None:
    """Initialise DB in the background so the HTTP port opens immediately."""
    try:
        await init_db()
    except Exception as exc:  # noqa: BLE001
        logger.error("DB init failed: %s — retrying in 5 s", exc)
        await asyncio.sleep(5)
        try:
            await init_db()
        except Exception as exc2:
            logger.critical("DB init failed on retry: %s", exc2)


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Munim API",
    description="AI Business Intelligence for Indian SMBs",
    version="1.0.0",
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
    lifespan=lifespan,
)

# --- Rate limiting ---
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "ngrok-skip-browser-warning"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(auth.router,      prefix="/api/v1/auth",      tags=["Auth"])
app.include_router(upload.router,    prefix="/api/v1/upload",    tags=["Upload"])
app.include_router(analysis.router,  prefix="/api/v1/analysis",  tags=["Analysis"])
app.include_router(reports.router,   prefix="/api/v1/reports",   tags=["Reports"])
app.include_router(whatsapp.router,  prefix="/api/v1/whatsapp",  tags=["WhatsApp"])
app.include_router(ca.router,        prefix="/api/v1/ca",        tags=["CA Console"])
app.include_router(beta.router,      prefix="/api/v1/beta",      tags=["Beta"])


# ---------------------------------------------------------------------------
# Global exception handlers
# ---------------------------------------------------------------------------
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception on %s %s: %s", request.method, request.url, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An unexpected error occurred. Our team has been notified."},
    )


# ---------------------------------------------------------------------------
# Health check (used by Railway + uptime monitors)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["System"], include_in_schema=False)
async def health_check():
    return {"status": "ok", "version": "1.0.0"}


# ---------------------------------------------------------------------------
# Root
# ---------------------------------------------------------------------------
@app.get("/", tags=["System"], include_in_schema=False)
async def root():
    from fastapi.responses import RedirectResponse
    frontend = settings.APP_URL.rstrip("/")
    return RedirectResponse(url=f"{frontend}/dashboard", status_code=302)
