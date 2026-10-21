"""Генерирует docs/state-machine.md из таблицы переходов.

Запуск из каталога backend: uv run python -m app.scripts.export_state_machine
"""

from pathlib import Path

from app.domain.state_machine import render_state_machine_md

# backend/app/scripts/export_state_machine.py -> корень репозитория
DEFAULT_OUTPUT = Path(__file__).resolve().parents[3] / "docs" / "state-machine.md"


def main() -> None:
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(render_state_machine_md(), encoding="utf-8", newline="\n")
    print(f"Записано: {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
