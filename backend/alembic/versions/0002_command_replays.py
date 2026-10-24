"""Persistent command idempotency and simulated disbursement uniqueness."""

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "idempotency_record",
        sa.Column("record_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column("user_id", sa.BigInteger(), sa.ForeignKey("app_user.user_id"), nullable=False),
        sa.Column(
            "application_id",
            sa.BigInteger(),
            sa.ForeignKey("loan_application.application_id"),
            nullable=False,
        ),
        sa.Column("operation_code", sa.String(64), nullable=False),
        sa.Column("key_code", sa.String(64), nullable=False),
        sa.Column("request_hash_code", sa.String(64), nullable=False),
        sa.Column("response_cval", sa.Text(), nullable=False),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "operation_code", "key_code"),
    )
    op.create_table(
        "disbursement",
        sa.Column("disbursement_id", sa.BigInteger(), sa.Identity(), primary_key=True),
        sa.Column(
            "application_id",
            sa.BigInteger(),
            sa.ForeignKey("loan_application.application_id"),
            nullable=False,
        ),
        sa.Column("offer_id", sa.BigInteger(), sa.ForeignKey("loan_offer.offer_id"), nullable=False),
        sa.Column("amount_amt", sa.Numeric(18, 2), nullable=False),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("application_id"),
    )


def downgrade():
    op.drop_table("disbursement")
    op.drop_table("idempotency_record")
