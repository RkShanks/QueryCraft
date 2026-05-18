# syntax=docker/dockerfile:1.7
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Install deps first (cache layer)
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --all-extras

# Now install the project itself
COPY src/ ./src/
COPY tests/ ./tests/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --all-extras

# Runtime stage
FROM python:3.12-slim-bookworm

# Install uv for runtime commands (e.g., uv run)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN groupadd --system app && useradd --system --gid app --create-home app

# MSSQL ODBC driver system dependencies (ADR-10)
RUN apt-get update && apt-get install -y \
    unixodbc unixodbc-dev freetds-dev tdsodbc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/src /app/src
COPY --from=builder --chown=app:app /app/tests /app/tests
COPY pyproject.toml .

# Copy Alembic files (required for migrations)
COPY --chown=app:app alembic/ ./alembic/
COPY --chown=app:app alembic.ini .

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
