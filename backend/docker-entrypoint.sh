#!/bin/sh
# Старт контейнера api: миграции -> seed -> основной процесс.
# RUN_MIGRATIONS=0 пропускает миграции и seed (используется сервисом tests).
set -e

if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
    echo "[entrypoint] alembic upgrade head"
    alembic upgrade head
    echo "[entrypoint] seed"
    python -m app.seed.run
fi

exec "$@"
