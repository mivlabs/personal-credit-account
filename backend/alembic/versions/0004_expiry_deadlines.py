"""Сроки жизни оффера и запроса данных."""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("loan_offer", sa.Column("valid_until_dttm", sa.DateTime(timezone=True), nullable=True))
    op.add_column("info_request", sa.Column("due_dttm", sa.DateTime(timezone=True), nullable=True))


def downgrade():
    op.drop_column("info_request", "due_dttm")
    op.drop_column("loan_offer", "valid_until_dttm")
