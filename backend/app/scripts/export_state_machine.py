"""Генерирует docs/state-machine.md из таблицы переходов.

Запуск из каталога backend: uv run python -m app.scripts.export_state_machine
"""

from app.domain.state_machine import render_state_machine_md
from app.scripts.paths import docs_dir

DEFAULT_OUTPUT = docs_dir() / "state-machine.md"


def main() -> None:
    DEFAULT_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUTPUT.write_text(render_state_machine_md(), encoding="utf-8", newline="\n")
    print(f"Записано: {DEFAULT_OUTPUT}")


if __name__ == "__main__":
    main()
