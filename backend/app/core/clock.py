"""Единственный источник «сейчас» для бизнес-кода: в тестах подменяется через monkeypatch."""

from datetime import UTC, datetime


def now() -> datetime:
    return datetime.now(UTC)
