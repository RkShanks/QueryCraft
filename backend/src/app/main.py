"""FastAPI application factory and lifespan event handler."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.dependencies import close_redis, init_redis
from app.core.encryption import encrypt
from app.core.logging import get_logger, setup_logging
from app.core.security import OriginValidatorMiddleware, SessionMiddleware
from app.db.base import dispose_engine, get_async_session_factory

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    # Verify Redis connectivity
    await init_redis()
    logger.info("redis_connected", url=settings.REDIS_URL)

    # Upsert database_connections row for the source DB
    await _upsert_source_db_connection(settings)

    yield

    # Shutdown
    await close_redis()
    await dispose_engine()
    logger.info("application_shutdown")


async def _upsert_source_db_connection(settings):
    """Upsert the source database connection row on startup."""
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    # Initialize engine
    session_factory = get_async_session_factory()

    try:
        async with session_factory() as session:
            # Check if connection already exists
            result = await session.execute(
                text("SELECT id FROM database_connections WHERE name = :name"),
                {"name": settings.SOURCE_DB_NAME},
            )
            existing = result.scalar_one_or_none()

            if existing is None:
                # Encrypt the source DB password
                encrypted_password = encrypt(
                    settings.SOURCE_DB_PASSWORD,
                    settings.PLATFORM_ENCRYPTION_KEY,
                )
                await session.execute(
                    text("""
                        INSERT INTO database_connections (
                            name, host, port, database_name, username, encrypted_password, ssl_mode
                        )
                        VALUES (:name, :host, :port, :database_name, :username, :encrypted_password, :ssl_mode)
                    """),
                    {
                        "name": settings.SOURCE_DB_NAME,
                        "host": settings.SOURCE_DB_HOST,
                        "port": settings.SOURCE_DB_PORT,
                        "database_name": settings.SOURCE_DB_NAME,
                        "username": settings.SOURCE_DB_USER,
                        "encrypted_password": encrypted_password,
                        "ssl_mode": settings.SOURCE_DB_SSL_MODE,
                    },
                )
                await session.commit()
                logger.info("source_db_connection_created", name=settings.SOURCE_DB_NAME)
            else:
                logger.info("source_db_connection_exists", name=settings.SOURCE_DB_NAME)
    except ProgrammingError:
        logger.warning("database_connections_table_missing", msg="Skipping seed. Run alembic upgrade head.")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="QueryCraft API",
        version="1.0.0",
        description="Text-to-SQL Analytics Platform API",
        lifespan=lifespan,
    )

    # Middleware stack (applied in reverse order)
    # 1. CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 2. Origin validator (ASGI middleware)
    app.add_middleware(
        OriginValidatorMiddleware,
        allowed_origins=settings.allowed_origins_list,
    )

    # 3. Session middleware (ASGI middleware)
    app.add_middleware(
        SessionMiddleware,
        redis_url=settings.REDIS_URL,
        idle_timeout_hours=settings.SESSION_IDLE_TIMEOUT_HOURS,
    )

    # Register v1 router stubs
    from app.api.v1 import admin, auth, history, query  # noqa: F401

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    return app
