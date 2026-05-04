# Multi-stage build for QueryCraft Backend
# Stage 1: Builder
FROM python:3.12-slim AS builder

WORKDIR /build
COPY pyproject.toml .
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.12-slim AS runtime

# Create non-root user
RUN groupadd --system appuser && useradd --system --gid appuser appuser

# Copy installed packages
COPY --from=builder /install /usr/local

# Copy application code
WORKDIR /app
COPY src/ ./src/
COPY alembic/ ./alembic/
COPY alembic.ini .

# Switch to non-root user
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
