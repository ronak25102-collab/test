"""Preserve the evidence basis for source availability without inventing dates."""
from alembic import op
from sqlalchemy import Column, String, inspect

revision = '0003_source_availability'
down_revision = '0002_evidence_and_heartbeats'
branch_labels = None
depends_on = None


def upgrade():
    columns = {column['name'] for column in inspect(op.get_bind()).get_columns('source_documents')}
    if 'cutoff_eligibility_basis' not in columns:
        op.add_column('source_documents', Column('cutoff_eligibility_basis', String(30), nullable=False,
                                               server_default='publication_date'))


def downgrade():
    with op.batch_alter_table('source_documents') as batch:
        batch.drop_column('cutoff_eligibility_basis')
