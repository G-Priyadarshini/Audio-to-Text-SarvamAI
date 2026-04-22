import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from redis.asyncio import Redis
from app.config import settings
from app.database import init_db, close_db
from app.routes import api_router
from app.middleware.rate_limit import limiter

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("icepot")
# Ensure file handler for persistent error logs
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    fh = logging.FileHandler("backend_error.log", mode="a", encoding="utf-8")
    fh.setLevel(logging.ERROR)
    fh.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(fh)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    logger.info("Starting ICEPOT backend...")

    # Create temp directory
    os.makedirs(settings.TEMP_DIR, exist_ok=True)

    # Initialize database
    await init_db()
    logger.info("Database initialized")

    # Initialize Redis (optional – app works without it)
    try:
        app.state.redis = Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            decode_responses=True,
        )
        await app.state.redis.ping()
        logger.info("Redis connected")
    except Exception as exc:
        logger.warning(
            "Redis not available (%s). Upload tracking will use filesystem, "
            "and transcription will run inline instead of via arq worker.",
            exc,
        )
        app.state.redis = None

    # Check for ffmpeg availability used by pydub
    try:
        import shutil

        if shutil.which("ffmpeg") is None:
            logger.warning(
                "ffmpeg not found on PATH — audio conversions (pydub) may fail."
            )
        else:
            logger.info("ffmpeg found: %s", shutil.which("ffmpeg"))
    except Exception:
        logger.warning("Could not check ffmpeg availability")

    # If user provided an explicit ffmpeg binary path in settings, configure pydub
    try:
        if settings.FFMPEG_BINARY:
            # set pydub's converter if file exists
            from pydub import AudioSegment

            if os.path.exists(settings.FFMPEG_BINARY):
                AudioSegment.converter = settings.FFMPEG_BINARY
                logger.info("Configured pydub to use ffmpeg at %s", settings.FFMPEG_BINARY)
            else:
                logger.warning(
                    "FFMPEG_BINARY is set but path does not exist: %s",
                    settings.FFMPEG_BINARY,
                )
    except Exception:
        logger.debug("Could not configure pydub ffmpeg converter", exc_info=True)

    yield

    # Shutdown
    logger.info("Shutting down ICEPOT backend...")
    if getattr(app.state, "redis", None) is not None:
        await app.state.redis.close()
    await close_db()


def create_app() -> FastAPI:
    app = FastAPI(
        title="ICEPOT - Audio to Text API",
        description="Local backend for audio transcription",
        version="1.0.0",
        lifespan=lifespan,
    )

    # Global exception handler to surface and log unexpected server errors
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled exception during request %s %s", request.method, request.url)
        return JSONResponse({"detail": "Internal server error"}, status_code=500)

    # Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # CORS — allow extension origin and localhost (include port 8000)
    # Use a regex to match chrome-extension origins (chrome-extension://<id>)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost",
            "http://127.0.0.1",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_origin_regex=r"^chrome-extension://.*$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routes
    app.include_router(api_router)

    # Health check
    @app.get("/health")
    async def health():
        return {"status": "ok", "service": "icepot"}

    return app


app = create_app()
