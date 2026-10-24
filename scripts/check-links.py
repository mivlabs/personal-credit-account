"""Проверка относительных ссылок в markdown: файл существует, якорь (#заголовок) есть в целевом файле.

Запуск из корня репозитория: python scripts/check-links.py
Код выхода 1, если найдены битые ссылки. Внешние ссылки (http, mailto) не проверяются.
"""

import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {"node_modules", ".venv", ".git", "dist", "test-results", "__pycache__"}
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
FENCE = re.compile(r"^\s*```")


def slug(heading: str) -> str:
    text = re.sub(r"[`*_]", "", heading.strip().lower())
    text = re.sub(r"[^\w\- ]", "", text, flags=re.UNICODE)
    return text.replace(" ", "-")


def anchors(path: Path) -> set[str]:
    result: set[str] = set()
    in_fence = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
        elif not in_fence and line.startswith("#"):
            result.add(slug(line.lstrip("#")))
    return result


def main() -> int:
    bad = 0
    files = [p for p in ROOT.rglob("*.md") if not SKIP_DIRS & set(p.relative_to(ROOT).parts)]
    for md in sorted(files):
        in_fence = False
        for lineno, line in enumerate(md.read_text(encoding="utf-8").splitlines(), 1):
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            for target in LINK.findall(line):
                if re.match(r"^(https?:|mailto:|<)", target):
                    continue
                raw, _, frag = target.partition("#")
                dest = md if not raw else (md.parent / unquote(raw)).resolve()
                if not dest.exists():
                    print(f"{md.relative_to(ROOT)}:{lineno}: нет файла {target}")
                    bad += 1
                elif frag and dest.suffix == ".md" and unquote(frag).lower() not in anchors(dest):
                    print(f"{md.relative_to(ROOT)}:{lineno}: нет якоря {target}")
                    bad += 1
    print("битых ссылок:", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
