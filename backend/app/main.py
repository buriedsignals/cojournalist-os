"""
FastAPI main application entry point.

PURPOSE: Creates the FastAPI app, configures CORS middleware, rate limiting
(slowapi), mounts all routers under /api prefix, and serves the SvelteKit
SPA static build. Also handles HTTP client lifecycle (shutdown cleanup).

DEPENDS ON: config (settings), all routers (mounted here),
    services/http_client (shutdown hook)
USED BY: Render deployment (uvicorn entrypoint)
"""
import logging
import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.responses import Response
from starlette.types import Scope

from app.config import settings
from app.routers import (
    scraper,
    onboarding,
    data_extractor,
    user,
    scouts,
    units,
    export,
    pulse,
    social,
    civic,
    license,
    v1,
)
from app.services.http_client import close_http_client

# Configure logging
log_level = logging.DEBUG if settings.environment == "development" else logging.INFO
logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Rate limiter configuration
limiter = Limiter(key_func=get_remote_address)


class SPAStaticFiles(StaticFiles):
    """
    Custom StaticFiles that serves index.html for SPA routing,
    but doesn't intercept API requests.
    """
    async def get_response(self, path: str, scope: Scope) -> Response:
        # If it's an API request, don't handle it - let it 404
        # so FastAPI's actual API routes can handle it
        if path.startswith('api/'):
            raise RuntimeError("Not a static file")

        try:
            # Try to serve the requested file
            return await super().get_response(path, scope)
        except Exception:
            # If file not found, serve index.html for SPA client-side routing
            # (except for API routes which should 404)
            if not path.startswith('api'):
                index_path = os.path.join(self.directory, 'index.html')
                return FileResponse(index_path)
            raise


# Create FastAPI app
app = FastAPI(
    title="coJournalist API",
    description="Public REST API for programmatic access to coJournalist — create scouts and retrieve information units.",
    version="1.0.0",
    debug=settings.debug,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# Configure rate limiter
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Startup event to initialize services and log startup information
@app.on_event("startup")
async def startup_event():
    """Initialize services and log startup information."""
    # Startup diagnostics
    logger.info("=" * 50)
    logger.info("🚀 coJournalist API Starting...")
    logger.info(f"App Name: {settings.app_name}")
    logger.info(f"Environment: {settings.environment}")
    logger.info(f"Debug Mode: {settings.debug}")
    logger.info(f"MuckRock OAuth: {'Configured' if settings.muckrock_client_id else 'Not configured'}")
    logger.info(f"Default Credits: {settings.default_credits}")
    logger.info(f"Default Timezone: {settings.default_timezone}")
    logger.info("Plan URL (Pro): %s", settings.muckrock_pro_plan_url)
    logger.info("=" * 50)

    logger.info("Application startup complete")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on shutdown."""
    logger.info("Shutting down application...")
    await close_http_client()
    logger.info("Application shutdown complete")


@app.middleware("http")
async def normalize_api_prefix(request: Request, call_next):
    """
    Temporary workaround: older frontend bundles may still call /api/api/*.
    Normalize those paths so the actual /api routes handle them instead of returning 500.
    """
    path = request.scope.get("path", "")
    if path.startswith("/api/api"):
        new_path = path.replace("/api/api", "/api", 1)
        request.scope["path"] = new_path

        raw_path = request.scope.get("raw_path")
        if isinstance(raw_path, (bytes, bytearray)):
            request.scope["raw_path"] = raw_path.replace(b"/api/api", b"/api", 1)

        logger.warning("Normalized duplicated API prefix: %s -> %s", path, new_path)

    return await call_next(request)


# Internal routers — hidden from public API docs
# MuckRock auth router is SaaS-only (stripped in OSS mirror)
if settings.deployment_target != "supabase":
    from app.routers import auth
    app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"], include_in_schema=False)
app.include_router(onboarding.router, prefix="/api/onboarding", tags=["Onboarding"], include_in_schema=False)
app.include_router(scraper.router, prefix="/api", tags=["Scraper"], include_in_schema=False)
app.include_router(data_extractor.router, prefix="/api", tags=["Data"], include_in_schema=False)
app.include_router(user.router, prefix="/api", tags=["User"], include_in_schema=False)
app.include_router(scouts.router, prefix="/api", tags=["Scouts"], include_in_schema=False)
app.include_router(units.router, prefix="/api", tags=["Units"], include_in_schema=False)
app.include_router(export.router, prefix="/api", tags=["Export"], include_in_schema=False)
app.include_router(pulse.router, prefix="/api", tags=["Pulse"], include_in_schema=False)
app.include_router(social.router, prefix="/api", tags=["Social"], include_in_schema=False)
app.include_router(civic.router, prefix="/api", tags=["Civic"], include_in_schema=False)

# License key management — hidden from public API docs
app.include_router(license.router, prefix="/api", tags=["License"], include_in_schema=False)

# Public v1 API — visible in docs
app.include_router(v1.router, prefix="/api/v1")
# billing router removed — billing now handled on Squarelet

# Serve built frontend if available
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend_client"
if FRONTEND_DIST.exists():
    logger.info("Serving frontend assets from %s", FRONTEND_DIST)
    app.mount("/", SPAStaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")
else:
    logger.info("Frontend assets directory not found at %s (skipping mount).", FRONTEND_DIST)


# Health check endpoint
@app.get("/api/health", include_in_schema=False)
async def health_check():
    """Health check endpoint for monitoring."""
    return {"status": "healthy", "service": settings.app_name}


@app.get("/api/ready", include_in_schema=False)
async def readiness_check():
    """Readiness check endpoint."""
    return {"status": "ready"}


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler for unhandled errors."""
    # Log full exception server-side for debugging
    logger.exception(f"Unhandled exception: {exc}")
    # Return generic error to client (no internal details)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error"},
    )
