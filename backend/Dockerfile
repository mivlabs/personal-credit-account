# syntax=docker/dockerfile:1

# Версии зафиксированы точными тегами (uv совпадает с локальным для воспроизводимости uv.lock)
FROM ghcr.io/astral-sh/uv:0.11.11 AS uv

# ---- builder: зависимости по uv.lock ----
FROM python:3.12.15-slim-bookworm AS builder
COPY --from=uv /uv /uvx /bin/
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app

COPY pyproject.toml uv.lock ./
# Только продакшен-зависимости; --frozen: lock-файл не пересчитывается и не обновляется
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY docker-entrypoint.sh ./

# ---- dev: то же + pytest и ruff, для `docker compose --profile test run --rm tests` ----
FROM builder AS dev
RUN uv sync --frozen --no-install-project
COPY tests ./tests
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
CMD ["pytest", "-q"]

# ---- runtime: минимальный образ без uv и dev-зависимостей ----
FROM python:3.12.15-slim-bookworm AS runtime
RUN useradd --system --uid 10001 --no-create-home app
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app
COPY --from=builder --chown=app:app /app /app
# каталог для сгенерированного JWT-секрета (named volume наследует владельца)
RUN mkdir -p /app/data && chown app:app /app/data
USER app
EXPOSE 8000
# sh вместо прямого запуска: бит исполнения теряется при коммите с Windows
ENTRYPOINT ["sh", "./docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
