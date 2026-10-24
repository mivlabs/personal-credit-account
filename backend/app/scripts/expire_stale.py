"""Закрывает все просроченные заявки (оффер или запрос данных) переводом в EXPIRED.

Запуск из каталога backend: uv run python -m app.scripts.expire_stale
"""

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db.session import get_sessionmaker
from app.services.expiry import expire_all_stale


def main() -> None:
    setup_logging(get_settings().log_level)
    closed = expire_all_stale(get_sessionmaker())
    print(f"Закрыто просроченных заявок: {closed}")


if __name__ == "__main__":
    main()
