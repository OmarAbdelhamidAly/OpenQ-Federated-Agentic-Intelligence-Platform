"""Initial migration — create all tables with RLS policies.

Revision ID: 001_initial
Revises: None
Create Date: 2026-02-26
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Tenants ───────────────────────────────────────────────
    op.create_table(
        "tenants",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("plan", sa.String(50), server_default="internal"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── Users ─────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("email", sa.Text(), unique=True, nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("role IN ('admin', 'viewer')", name="ck_users_role"),
    )
    op.create_index("ix_users_tenant_id", "users", ["tenant_id"])

    # ── Data Sources ──────────────────────────────────────────
    op.create_table(
        "data_sources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("file_path", sa.Text(), nullable=True),
        sa.Column("config_encrypted", sa.Text(), nullable=True),
        sa.Column("schema_json", JSONB, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.CheckConstraint("type IN ('csv', 'sql')", name="ck_data_sources_type"),
    )
    op.create_index("ix_data_sources_tenant_id", "data_sources", ["tenant_id"])

    # ── Analysis Jobs ─────────────────────────────────────────
    op.create_table(
        "analysis_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_id", UUID(as_uuid=True), sa.ForeignKey("data_sources.id"), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'done', 'error')",
            name="ck_analysis_jobs_status",
        ),
    )
    op.create_index("ix_analysis_jobs_tenant_id", "analysis_jobs", ["tenant_id"])
    op.create_index("ix_analysis_jobs_user_id", "analysis_jobs", ["user_id"])

    # ── Analysis Results ──────────────────────────────────────
    op.create_table(
        "analysis_results",
        sa.Column("job_id", UUID(as_uuid=True), sa.ForeignKey("analysis_jobs.id"), primary_key=True),
        sa.Column("chart_json", JSONB, nullable=True),
        sa.Column("insight_report", sa.Text(), nullable=True),
        sa.Column("exec_summary", sa.Text(), nullable=True),
        sa.Column("recommendations_json", JSONB, nullable=True),
        sa.Column("follow_up_suggestions", JSONB, nullable=True),
    )

    # ── Row-Level Security Policies ───────────────────────────
    # Enable RLS on all tenant-scoped tables
    for table in ["users", "data_sources", "analysis_jobs"]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"USING (tenant_id::text = current_setting('app.tenant_id', true))"
        )

    # analysis_results uses job-level isolation via JOIN
    op.execute("ALTER TABLE analysis_results ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE analysis_results FORCE ROW LEVEL SECURITY")
    op.execute(
        "CREATE POLICY analysis_results_tenant_isolation ON analysis_results "
        "USING (job_id IN (SELECT id FROM analysis_jobs WHERE "
        "tenant_id::text = current_setting('app.tenant_id', true)))"
    )


def downgrade() -> None:
    # Drop policies first
    for table in ["users", "data_sources", "analysis_jobs"]:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")

    op.execute("DROP POLICY IF EXISTS analysis_results_tenant_isolation ON analysis_results")
    op.execute("ALTER TABLE analysis_results DISABLE ROW LEVEL SECURITY")

    # Drop tables in reverse order
    op.drop_table("analysis_results")
    op.drop_table("analysis_jobs")
    op.drop_table("data_sources")
    op.drop_table("users")
    op.drop_table("tenants")
