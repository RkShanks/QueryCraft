"""FastAPI application factory and lifespan event handler."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.dependencies import close_redis, init_redis
from app.core.encryption import encrypt
from app.core.logging import get_logger, setup_logging
from app.core.security import OriginValidatorMiddleware, SessionMiddleware
from app.db.base import dispose_engine, get_async_session_factory
from app.llm.factory import LLMProviderFactory

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: startup and shutdown events."""
    settings = get_settings()
    setup_logging(settings.LOG_LEVEL)

    # Verify Redis connectivity
    await init_redis()
    logger.info("redis_connected", url=settings.REDIS_URL)

    # Refuse to start if the DB schema is behind the source tree's alembic head
    await _check_alembic_drift(settings.DATABASE_URL)

    # Upsert database_connections row for the source DB
    await _upsert_source_db_connection(settings)

    yield

    # Shutdown
    await LLMProviderFactory.shutdown_all()
    for sm in SessionMiddleware._instances:
        await sm.aclose()
    await close_redis()
    await dispose_engine()
    logger.info("application_shutdown")


async def _check_alembic_drift(database_url: str) -> None:
    """Raise RuntimeError if the DB schema is older than the source tree's alembic head."""
    from alembic.config import Config
    from alembic.runtime.migration import MigrationContext
    from alembic.script import ScriptDirectory
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url)
    async with engine.connect() as conn:
        current = await conn.run_sync(
            lambda sync_conn: MigrationContext.configure(sync_conn).get_current_revision()
        )
    await engine.dispose()

    alembic_ini = Path(__file__).resolve().parents[2] / "alembic.ini"
    cfg = Config(str(alembic_ini))
    cfg.set_main_option("script_location", str(alembic_ini.parent / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    head = script.get_current_head()

    if current != head:
        logger.error("migration_drift_detected", current=current, head=head)
        raise RuntimeError(
            f"Alembic migration drift: DB at {current!r}, source tree at {head!r}. "
            "Run `alembic upgrade head` before starting the app."
        )


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

    from fastapi.exceptions import RequestValidationError

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request, exc):
        if isinstance(exc.detail, dict):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return JSONResponse(status_code=exc.status_code, content={"error": "error", "message_key": str(exc.detail)})

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request, exc):
        details = []
        for err in exc.errors():
            field = ".".join(str(loc) for loc in err.get("loc", []))
            details.append({
                "field": field,
                "message_key": err.get("type", "error.validation.generic"),
                "message_params": {"msg": err.get("msg", "")},
            })
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation",
                "message_key": "error.validation.generic",
                "details": details,
            },
        )

    # Register v1 router stubs
    from app.api.v1 import admin, auth, history, query  # noqa: F401

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")

    return app
