"""Associate new investigations with their authenticated Clerk user."""
from alembic import op
from sqlalchemy import Column, String, inspect, text

revision = "0006_run_ownership"
down_revision = "0005_evidence_label_capacity"
branch_labels = None
depends_on = None


def upgrade():
    inspector = inspect(op.get_bind())
    if "owner_user_id" not in {column["name"] for column in inspector.get_columns("research_runs")}:
        op.add_column("research_runs", Column("owner_user_id", String(128), nullable=True))
    if "ix_run_owner_created_at" not in {index["name"] for index in inspector.get_indexes("research_runs")}:
        op.create_index("ix_run_owner_created_at", "research_runs", ["owner_user_id", "created_at"])


def downgrade():
    if op.get_bind().execute(text(
            "SELECT 1 FROM research_runs WHERE owner_user_id IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Cannot remove ownership while private investigations exist")
    op.drop_index("ix_run_owner_created_at", table_name="research_runs")
    with op.batch_alter_table("research_runs") as batch:
        batch.drop_column("owner_user_id")
