"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-10-22 01:54:18.953275
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


MODIFY_DTTM_TABLES = (
    "company",
    "dim_application_status",
    "dim_credit_product",
    "dim_user_role",
    "loan_application",
)


def upgrade() -> None:
    op.create_table(
        "company",
        sa.Column("company_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("inn_code", sa.String(length=64), nullable=False),
        sa.Column("ogrn_code", sa.String(length=64), nullable=True),
        sa.Column("company_name", sa.String(length=256), nullable=False),
        sa.Column("legal_form_code", sa.String(length=64), nullable=False),
        sa.Column("registration_dt", sa.Date(), nullable=True),
        sa.Column("legal_address_desc", sa.Text(), nullable=True),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modify_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("inn_code ~ '^[0-9]{10}([0-9]{2})?$'", name=op.f("ck_company_inn_format")),
        sa.CheckConstraint("legal_form_code IN ('IP', 'OOO')", name=op.f("ck_company_legal_form")),
        sa.PrimaryKeyConstraint("company_id", name=op.f("pk_company")),
        sa.UniqueConstraint("inn_code", name=op.f("uq_company_inn_code")),
    )
    op.create_table(
        "dim_application_status",
        sa.Column("status_code", sa.String(length=64), nullable=False),
        sa.Column("status_name", sa.String(length=256), nullable=False),
        sa.Column("final_bool", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modify_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("action_ind_code", sa.String(length=64), server_default=sa.text("'I'"), nullable=False),
        sa.CheckConstraint(
            "action_ind_code IN ('I', 'U', 'D')", name=op.f("ck_dim_application_status_action_ind")
        ),
        sa.PrimaryKeyConstraint("status_code", name=op.f("pk_dim_application_status")),
    )
    op.create_table(
        "dim_credit_product",
        sa.Column("product_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("product_code", sa.String(length=64), nullable=False),
        sa.Column("product_name", sa.String(length=256), nullable=False),
        sa.Column("min_amt", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("max_amt", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("min_term_qnt", sa.Integer(), nullable=False),
        sa.Column("max_term_qnt", sa.Integer(), nullable=False),
        sa.Column("rate_nval", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("requirement_desc", sa.Text(), nullable=True),
        sa.Column("active_bool", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modify_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("action_ind_code", sa.String(length=64), server_default=sa.text("'I'"), nullable=False),
        sa.CheckConstraint(
            "action_ind_code IN ('I', 'U', 'D')", name=op.f("ck_dim_credit_product_action_ind")
        ),
        sa.CheckConstraint("min_amt <= max_amt", name=op.f("ck_dim_credit_product_amt_range")),
        sa.CheckConstraint("min_term_qnt <= max_term_qnt", name=op.f("ck_dim_credit_product_term_range")),
        sa.PrimaryKeyConstraint("product_id", name=op.f("pk_dim_credit_product")),
        sa.UniqueConstraint("product_code", name=op.f("uq_dim_credit_product_product_code")),
    )
    op.create_table(
        "dim_user_role",
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.Column("role_name", sa.String(length=256), nullable=False),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modify_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("action_ind_code", sa.String(length=64), server_default=sa.text("'I'"), nullable=False),
        sa.CheckConstraint("action_ind_code IN ('I', 'U', 'D')", name=op.f("ck_dim_user_role_action_ind")),
        sa.PrimaryKeyConstraint("role_code", name=op.f("pk_dim_user_role")),
    )
    op.create_table(
        "app_user",
        sa.Column("user_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=True),
        sa.Column("role_code", sa.String(length=64), nullable=False),
        sa.Column("login_code", sa.String(length=64), nullable=False),
        sa.Column("password_hash_cval", sa.Text(), nullable=False),
        sa.Column("user_name", sa.String(length=256), nullable=False),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["company.company_id"], name=op.f("fk_app_user_company_id")),
        sa.ForeignKeyConstraint(
            ["role_code"], ["dim_user_role.role_code"], name=op.f("fk_app_user_role_code")
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_app_user")),
        sa.UniqueConstraint("login_code", name=op.f("uq_app_user_login_code")),
    )
    op.create_index("ix_app_user_company_id", "app_user", ["company_id"], unique=False)
    op.create_index("ix_app_user_role_code", "app_user", ["role_code"], unique=False)
    op.create_table(
        "loan_application",
        sa.Column("application_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("company_id", sa.BigInteger(), nullable=False),
        sa.Column("product_id", sa.BigInteger(), nullable=False),
        sa.Column("status_code", sa.String(length=64), server_default="DRAFT", nullable=False),
        sa.Column("requested_amt", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("term_qnt", sa.Integer(), nullable=True),
        sa.Column("purpose_desc", sa.Text(), nullable=True),
        sa.Column("revenue_amt", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("debt_amt", sa.Numeric(precision=18, scale=2), nullable=True),
        sa.Column("idempotency_key_code", sa.String(length=64), nullable=True),
        sa.Column("submit_dttm", sa.DateTime(timezone=True), nullable=True),
        sa.Column("draft_step_qnt", sa.Integer(), nullable=True),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("modify_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"], ["company.company_id"], name=op.f("fk_loan_application_company_id")
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["dim_credit_product.product_id"], name=op.f("fk_loan_application_product_id")
        ),
        sa.ForeignKeyConstraint(
            ["status_code"],
            ["dim_application_status.status_code"],
            name=op.f("fk_loan_application_status_code"),
        ),
        sa.PrimaryKeyConstraint("application_id", name=op.f("pk_loan_application")),
        sa.UniqueConstraint("idempotency_key_code", name=op.f("uq_loan_application_idempotency_key_code")),
    )
    op.create_index("ix_loan_application_company_id", "loan_application", ["company_id"], unique=False)
    op.create_index("ix_loan_application_product_id", "loan_application", ["product_id"], unique=False)
    op.create_index("ix_loan_application_status_code", "loan_application", ["status_code"], unique=False)
    op.create_table(
        "credit_decision",
        sa.Column("decision_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("decision_type_code", sa.String(length=64), nullable=False),
        sa.Column("outcome_code", sa.String(length=64), nullable=False),
        sa.Column("score_qnt", sa.Integer(), nullable=True),
        sa.Column("reason_desc", sa.Text(), nullable=False),
        sa.Column("comment_desc", sa.Text(), nullable=True),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "decision_type_code IN ('AUTO', 'MANUAL')", name=op.f("ck_credit_decision_decision_type")
        ),
        sa.CheckConstraint(
            "outcome_code IN ('APPROVED', 'COUNTER_OFFER', 'NEEDS_INFO', 'MANUAL_REVIEW', 'REJECTED')",
            name=op.f("ck_credit_decision_outcome"),
        ),
        sa.CheckConstraint(
            "score_qnt IS NULL OR score_qnt BETWEEN 0 AND 100", name=op.f("ck_credit_decision_score_range")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["loan_application.application_id"],
            name=op.f("fk_credit_decision_application_id"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"], name=op.f("fk_credit_decision_user_id")),
        sa.PrimaryKeyConstraint("decision_id", name=op.f("pk_credit_decision")),
    )
    op.create_index("ix_credit_decision_application_id", "credit_decision", ["application_id"], unique=False)
    op.create_index("ix_credit_decision_user_id", "credit_decision", ["user_id"], unique=False)
    op.create_table(
        "external_check",
        sa.Column("check_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("source_code", sa.String(length=64), nullable=False),
        sa.Column("check_status_code", sa.String(length=64), nullable=False),
        sa.Column("response_cval", sa.Text(), nullable=True),
        sa.Column(
            "request_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column("response_dttm", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "check_status_code IN ('OK', 'TIMEOUT', 'ERROR')", name=op.f("ck_external_check_check_status")
        ),
        sa.CheckConstraint("source_code IN ('EGRUL', 'FNS', 'BKI')", name=op.f("ck_external_check_source")),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["loan_application.application_id"],
            name=op.f("fk_external_check_application_id"),
        ),
        sa.PrimaryKeyConstraint("check_id", name=op.f("pk_external_check")),
    )
    op.create_index("ix_external_check_application_id", "external_check", ["application_id"], unique=False)
    op.create_table(
        "info_request",
        sa.Column("request_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("request_desc", sa.Text(), nullable=False),
        sa.Column("field_list_cval", sa.Text(), server_default="[]", nullable=False),
        sa.Column("request_status_code", sa.String(length=64), nullable=False),
        sa.Column("answer_dttm", sa.DateTime(timezone=True), nullable=True),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "request_status_code IN ('OPEN', 'ANSWERED')", name=op.f("ck_info_request_request_status")
        ),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["loan_application.application_id"],
            name=op.f("fk_info_request_application_id"),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.user_id"], name=op.f("fk_info_request_user_id")),
        sa.PrimaryKeyConstraint("request_id", name=op.f("pk_info_request")),
    )
    op.create_index("ix_info_request_application_id", "info_request", ["application_id"], unique=False)
    op.create_index("ix_info_request_user_id", "info_request", ["user_id"], unique=False)
    op.create_table(
        "loan_application_aud",
        sa.Column("audit_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        sa.Column("from_status_code", sa.String(length=64), nullable=True),
        sa.Column("to_status_code", sa.String(length=64), nullable=False),
        sa.Column("event_desc", sa.Text(), nullable=True),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["application_id"],
            ["loan_application.application_id"],
            name=op.f("fk_loan_application_aud_application_id"),
        ),
        sa.ForeignKeyConstraint(
            ["from_status_code"],
            ["dim_application_status.status_code"],
            name=op.f("fk_loan_application_aud_from_status_code"),
        ),
        sa.ForeignKeyConstraint(
            ["to_status_code"],
            ["dim_application_status.status_code"],
            name=op.f("fk_loan_application_aud_to_status_code"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["app_user.user_id"], name=op.f("fk_loan_application_aud_user_id")
        ),
        sa.PrimaryKeyConstraint("audit_id", name=op.f("pk_loan_application_aud")),
    )
    op.create_index(
        "ix_loan_application_aud_application_id_create_dttm",
        "loan_application_aud",
        ["application_id", "create_dttm"],
        unique=False,
    )
    op.create_index("ix_loan_application_aud_user_id", "loan_application_aud", ["user_id"], unique=False)
    op.create_index(
        "ix_loan_application_aud_from_status_code", "loan_application_aud", ["from_status_code"], unique=False
    )
    op.create_index(
        "ix_loan_application_aud_to_status_code", "loan_application_aud", ["to_status_code"], unique=False
    )
    op.create_table(
        "decision_factor",
        sa.Column("factor_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("decision_id", sa.BigInteger(), nullable=False),
        sa.Column("factor_code", sa.String(length=64), nullable=False),
        sa.Column("factor_cval", sa.Text(), nullable=True),
        sa.Column("point_qnt", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["decision_id"], ["credit_decision.decision_id"], name=op.f("fk_decision_factor_decision_id")
        ),
        sa.PrimaryKeyConstraint("factor_id", name=op.f("pk_decision_factor")),
    )
    op.create_index("ix_decision_factor_decision_id", "decision_factor", ["decision_id"], unique=False)
    op.create_table(
        "loan_offer",
        sa.Column("offer_id", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("decision_id", sa.BigInteger(), nullable=False),
        sa.Column("offer_amt", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("term_qnt", sa.Integer(), nullable=False),
        sa.Column("rate_nval", sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column("monthly_payment_amt", sa.Numeric(precision=18, scale=2), nullable=False),
        sa.Column("offer_status_code", sa.String(length=64), nullable=False),
        sa.Column("accept_dttm", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sign_dttm", sa.DateTime(timezone=True), nullable=True),
        sa.Column("create_dttm", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "offer_status_code IN ('SENT', 'ACCEPTED', 'DECLINED', 'SIGNED')",
            name=op.f("ck_loan_offer_offer_status"),
        ),
        sa.ForeignKeyConstraint(
            ["decision_id"], ["credit_decision.decision_id"], name=op.f("fk_loan_offer_decision_id")
        ),
        sa.PrimaryKeyConstraint("offer_id", name=op.f("pk_loan_offer")),
        sa.UniqueConstraint("decision_id", name=op.f("uq_loan_offer_decision_id")),
    )

    # modify_dttm обновляется самой БД при любом UPDATE, а не приложением
    op.execute(
        """
        CREATE FUNCTION set_modify_dttm() RETURNS trigger AS $$
        BEGIN
            NEW.modify_dttm = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    for table in MODIFY_DTTM_TABLES:
        op.execute(
            f"CREATE TRIGGER trg_{table}_modify_dttm BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION set_modify_dttm()"
        )

    # История заявки только добавляется: UPDATE, DELETE и TRUNCATE запрещены на уровне БД
    op.execute(
        """
        CREATE FUNCTION forbid_audit_change() RETURNS trigger AS $$
        BEGIN
            RAISE EXCEPTION 'loan_application_aud is append-only: % is forbidden', TG_OP
                USING ERRCODE = 'integrity_constraint_violation';
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        "CREATE TRIGGER trg_loan_application_aud_append_only "
        "BEFORE UPDATE OR DELETE ON loan_application_aud "
        "FOR EACH ROW EXECUTE FUNCTION forbid_audit_change()"
    )
    op.execute(
        "CREATE TRIGGER trg_loan_application_aud_no_truncate "
        "BEFORE TRUNCATE ON loan_application_aud "
        "FOR EACH STATEMENT EXECUTE FUNCTION forbid_audit_change()"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER trg_loan_application_aud_no_truncate ON loan_application_aud")
    op.execute("DROP TRIGGER trg_loan_application_aud_append_only ON loan_application_aud")
    op.execute("DROP FUNCTION forbid_audit_change()")
    for table in MODIFY_DTTM_TABLES:
        op.execute(f"DROP TRIGGER trg_{table}_modify_dttm ON {table}")
    op.execute("DROP FUNCTION set_modify_dttm()")

    op.drop_table("loan_offer")
    op.drop_index("ix_decision_factor_decision_id", table_name="decision_factor")
    op.drop_table("decision_factor")
    op.drop_index("ix_loan_application_aud_to_status_code", table_name="loan_application_aud")
    op.drop_index("ix_loan_application_aud_from_status_code", table_name="loan_application_aud")
    op.drop_index("ix_loan_application_aud_user_id", table_name="loan_application_aud")
    op.drop_index("ix_loan_application_aud_application_id_create_dttm", table_name="loan_application_aud")
    op.drop_table("loan_application_aud")
    op.drop_index("ix_info_request_user_id", table_name="info_request")
    op.drop_index("ix_info_request_application_id", table_name="info_request")
    op.drop_table("info_request")
    op.drop_index("ix_external_check_application_id", table_name="external_check")
    op.drop_table("external_check")
    op.drop_index("ix_credit_decision_user_id", table_name="credit_decision")
    op.drop_index("ix_credit_decision_application_id", table_name="credit_decision")
    op.drop_table("credit_decision")
    op.drop_index("ix_loan_application_status_code", table_name="loan_application")
    op.drop_index("ix_loan_application_product_id", table_name="loan_application")
    op.drop_index("ix_loan_application_company_id", table_name="loan_application")
    op.drop_table("loan_application")
    op.drop_index("ix_app_user_role_code", table_name="app_user")
    op.drop_index("ix_app_user_company_id", table_name="app_user")
    op.drop_table("app_user")
    op.drop_table("dim_user_role")
    op.drop_table("dim_credit_product")
    op.drop_table("dim_application_status")
    op.drop_table("company")
