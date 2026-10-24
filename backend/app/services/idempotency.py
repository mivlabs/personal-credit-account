"""Successful command response and its effects commit atomically; errors are never cached."""

import hashlib
import json
from collections.abc import Callable

from sqlalchemy import select, text

from app.core.errors import IdempotencyConflictError
from app.db.models import IdempotencyRecord
from app.services.access import load_application


def execute(
    session,
    user,
    application_id: int,
    operation: str,
    key: str | None,
    body: dict,
    response_type,
    action: Callable,
):
    if key is None:
        return action()
    scope = f"{user.id}:{operation}:{key}"
    lock_id = int.from_bytes(hashlib.sha256(scope.encode()).digest()[:8], "big", signed=True)
    session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_id})
    load_application(session, application_id, user, lock=True)
    digest = hashlib.sha256(
        json.dumps(
            {"applicationId": application_id, "body": body}, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    record = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.user_id == user.id,
            IdempotencyRecord.operation_code == operation,
            IdempotencyRecord.key_code == key,
        )
    )
    if record is not None:
        if record.request_hash_code != digest:
            raise IdempotencyConflictError("Ключ уже использован для другой команды или другого тела запроса")
        return response_type.model_validate_json(record.response_cval)
    session.info["defer_commit"] = True
    try:
        result = action()
        session.add(
            IdempotencyRecord(
                user_id=user.id,
                application_id=application_id,
                operation_code=operation,
                key_code=key,
                request_hash_code=digest,
                response_cval=result.model_dump_json(by_alias=True),
            )
        )
        session.commit()
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.info.pop("defer_commit", None)
