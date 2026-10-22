"""Пути к зафиксированным документам (docs/api/openapi.yaml, docs/state-machine.md)."""

import os
from pathlib import Path


def docs_dir() -> Path:
    """Каталог docs: по умолчанию в корне репозитория, в контейнере тестов задаётся через DOCS_DIR."""
    override = os.environ.get("DOCS_DIR")
    if override:
        return Path(override)
    # backend/app/scripts/paths.py -> корень репозитория
    return Path(__file__).resolve().parents[3] / "docs"
