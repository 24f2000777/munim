"""
Munim — FastAPI Application Entry Point
========================================
Initialises the application, registers routers, configures middleware,
and sets up error handling and monitoring.
"""

import logging
from contextlib import asynccontextmanager

import sentry_sdk
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from db.neon_client import init_db, close_db
from routers import upload, analysis, reports, whatsapp, auth, ca
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
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Munim API — environment: %s", settings.APP_ENV)
    await init_db()
    yield
    await close_db()
    logger.info("Munim API shut down cleanly")


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
    allow_headers=["Authorization", "Content-Type"],
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
    return {
        "product": "Munim",
        "tagline": "AI Business Intelligence for Indian SMBs",
        "docs": "/docs",
    }
