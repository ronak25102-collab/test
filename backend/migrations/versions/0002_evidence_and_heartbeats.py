"""Add evidence relationship and worker heartbeat tables."""

from alembic import op

from signal_research.db.models import Base

revision = "0002_evidence_and_heartbeats"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # create_all is safe here because the first release used a metadata-based
    # bootstrap migration; it adds only tables absent from older checkouts.
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    pass
