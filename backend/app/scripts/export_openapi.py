"""Экспортирует схему OpenAPI в docs/api/openapi.yaml.

Запуск из каталога backend: uv run python -m app.scripts.export_openapi
Файл фиксируется в git: на нём стоит клиент фронта, а тест падает, если файл разошёлся с кодом.
"""

from pathlib import Path
from typing import Any

import yaml

from app.main import app

# backend/app/scripts/export_openapi.py -> корень репозитория
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.yaml"


class _NoAliasDumper(yaml.SafeDumper):
    """Без якорей и алиасов YAML (&id001): файл читают люди и генераторы клиента."""

    def ignore_aliases(self, data: Any) -> bool:
        return True


def render_openapi_yaml(schema: dict[str, Any] | None = None) -> str:
    return yaml.dump(
        schema if schema is not None else app.openapi(),
        Dumper=_NoAliasDumper,
        allow_unicode=True,
        sort_keys=False,
        default_flow_style=False,
        width=120,
    )


def main() -> None:
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(render_openapi_yaml(), encoding="utf-8", newline="\n")
    print(f"Записано: {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
