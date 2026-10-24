"""Структурированный снимок решения: credit_decision.decision_snapshot (JSONB)."""

import json

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def backfill_snapshots(conn) -> int:
    """AUTO-решения: JSON из comment_desc переносится в decision_snapshot, comment_desc очищается.

    Строки с битым JSON (и JSON не-объекты) остаются как есть.
    """
    rows = conn.execute(
        sa.text(
            "SELECT decision_id, comment_desc FROM credit_decision "
            "WHERE decision_type_code = 'AUTO' AND comment_desc IS NOT NULL AND decision_snapshot IS NULL"
        )
    ).all()
    moved = 0
    for decision_id, comment in rows:
        try:
            parsed = json.loads(comment)
        except ValueError:
            continue
        if not isinstance(parsed, dict):
            continue
        conn.execute(
            sa.text(
                "UPDATE credit_decision SET decision_snapshot = CAST(:snap AS JSONB), comment_desc = NULL "
                "WHERE decision_id = :id"
            ),
            {"snap": json.dumps(parsed, ensure_ascii=False), "id": decision_id},
        )
        moved += 1
    return moved


def upgrade():
    op.add_column(
        "credit_decision",
        sa.Column("decision_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    backfill_snapshots(op.get_bind())


def downgrade():
    # Возвращаем снимок AUTO-решений в comment_desc, где он лежал раньше
    op.execute(
        "UPDATE credit_decision SET comment_desc = decision_snapshot::text "
        "WHERE decision_type_code = 'AUTO' AND comment_desc IS NULL AND decision_snapshot IS NOT NULL"
    )
    op.drop_column("credit_decision", "decision_snapshot")
