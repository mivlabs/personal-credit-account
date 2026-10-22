from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import AuthUser
from app.core.errors import NotFoundError
from app.core.logging import application_id_var
from app.db.models import LoanApplication
from app.domain.enums import UserRole


def load_application(
    session: Session, application_id: int, user: AuthUser, *, lock: bool = False
) -> LoanApplication:
    """Заявка по id с проверкой доступа. Клиент видит только заявки своей компании: чужая — 404, не 403.

    lock=True блокирует строку (SELECT … FOR UPDATE) на время транзакции.
    """
    stmt = select(LoanApplication).where(LoanApplication.application_id == application_id)
    if lock:
        stmt = stmt.with_for_update(of=LoanApplication)
    app = session.scalar(stmt)
    if app is None or (user.role == UserRole.CLIENT and app.company_id != user.company_id):
        raise NotFoundError("Заявка не найдена")
    application_id_var.set(application_id)
    return app
