"""FastAPI application factory and lifespan event handler."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.credential_provider import init_credential_provider
from app.core.dependencies import close_redis, init_redis
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

    # Initialize credential provider (ADR-9: fail startup if DB_CREDENTIAL_KEY missing/invalid)
    init_credential_provider(settings.DB_CREDENTIAL_KEY)
    logger.info("credential_provider_initialized")

    # Upsert database_connections row for the source DB
    await _upsert_source_db_connection(settings)

    # Sync admin user credentials from .env (dev/single-admin: picks up changes)
    await _sync_admin_user(settings)

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
        current = await conn.run_sync(lambda sync_conn: MigrationContext.configure(sync_conn).get_current_revision())
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


async def _sync_admin_user(settings):
    """Sync admin user credentials from .env on startup (dev/single-admin behavior).

    Re-hashes the password so changes to ADMIN_PASSWORD in .env are picked up
    even on an existing volume. Migrations do not rerun automatically.
    """
    from argon2 import PasswordHasher
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    session_factory = get_async_session_factory()
    ph = PasswordHasher()
    password_hash = ph.hash(settings.ADMIN_PASSWORD)

    try:
        async with session_factory() as session:
            await session.execute(
                text(
                    """
                    INSERT INTO users (username, display_name, password_hash, role, role_id, is_builtin, auth_provider)
                    SELECT :username, :display_name, :password_hash, 'admin', id, true, 'local'
                    FROM roles
                    WHERE name = 'Admin' AND is_builtin = true
                    ON CONFLICT (username) DO UPDATE SET
                        display_name = EXCLUDED.display_name,
                        password_hash = EXCLUDED.password_hash,
                        role_id = EXCLUDED.role_id,
                        updated_at = now(),
                        is_builtin = true,
                        auth_provider = 'local'
                    """
                ),
                {
                    "username": settings.ADMIN_USERNAME,
                    "display_name": settings.ADMIN_DISPLAY_NAME,
                    "password_hash": password_hash,
                },
            )
            await session.commit()
            logger.info("admin_user_synced", username=settings.ADMIN_USERNAME)
    except ProgrammingError:
        logger.warning("users_table_missing", msg="Skipping admin sync. Run alembic upgrade head.")


async def _upsert_source_db_connection(settings):
    """Upsert the source database connection row on startup (Phase 3).

    Uses Fernet credential provider (ADR-9) for password encryption.
    """
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError

    from app.core.credential_provider import get_credential_provider

    session_factory = get_async_session_factory()
    provider = get_credential_provider()

    try:
        async with session_factory() as session:
            result = await session.execute(
                text("SELECT id FROM source_database_connections WHERE display_name = :name"),
                {"name": settings.SOURCE_DB_NAME},
            )
            existing = result.scalar_one_or_none()

            encrypted_password = provider.encrypt(settings.SOURCE_DB_PASSWORD)

            if existing is None:
                await session.execute(
                    text("""
                        INSERT INTO source_database_connections (
                            display_name, database_type, host, port,
                            database_name, username, encrypted_password, ssl_mode
                        )
                        VALUES (
                            :name, 'postgresql', :host, :port, :database_name,
                            :username, :encrypted_password, :ssl_mode
                        )
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
                await session.execute(
                    text("""
                        UPDATE source_database_connections
                        SET host = :host,
                            port = :port,
                            database_name = :database_name,
                            username = :username,
                            encrypted_password = :encrypted_password,
                            ssl_mode = :ssl_mode,
                            updated_at = now()
                        WHERE display_name = :name
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
                logger.info("source_db_connection_updated", name=settings.SOURCE_DB_NAME)
    except ProgrammingError:
        logger.warning("source_database_connections_table_missing", msg="Skipping seed. Run alembic upgrade head.")


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
            details.append(
                {
                    "field": field,
                    "message_key": err.get("type", "error.validation.generic"),
                    "message_params": {"msg": err.get("msg", "")},
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": "validation",
                "message_key": "error.validation.generic",
                "details": details,
            },
        )

    # Register v1 router stubs
    from app.api.v1 import (
        admin,
        admin_connections,
        admin_roles,
        admin_sso,
        auth,
        connections,
        feedback,
        history,
        query,
        sessions,
        sso_auth,
    )  # noqa: F401

    app.include_router(auth.router, prefix="/api/v1")
    app.include_router(query.router, prefix="/api/v1")
    app.include_router(history.router, prefix="/api/v1")
    app.include_router(admin.router, prefix="/api/v1")
    app.include_router(admin_connections.router, prefix="/api/v1")
    app.include_router(admin_sso.router, prefix="/api/v1")
    app.include_router(admin_roles.router, prefix="/api/v1")
    app.include_router(connections.router, prefix="/api/v1")
    app.include_router(sessions.router, prefix="/api/v1")
    app.include_router(feedback.router, prefix="/api/v1")
    app.include_router(sso_auth.router, prefix="/api/v1")

    return app
