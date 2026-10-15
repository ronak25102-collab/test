"""Allow durable provider failover identifiers without truncating saved state."""
from alembic import op
from sqlalchemy import String, inspect, text

revision = '0004_artifact_kind_capacity'
down_revision = '0003_source_availability'
branch_labels = None
depends_on = None


def upgrade():
    kind = next(column for column in inspect(op.get_bind()).get_columns('artifacts')
                if column['name'] == 'kind')
    if kind['type'].length < 128:
        with op.batch_alter_table('artifacts') as batch:
            batch.alter_column('kind', existing_type=kind['type'], type_=String(128),
                               existing_nullable=False)


def downgrade():
    # A rollback must not truncate identifiers used to avoid duplicate requests.
    bind = op.get_bind()
    if bind.execute(text('SELECT 1 FROM artifacts WHERE length(kind) > 50 LIMIT 1')).first():
        raise RuntimeError('Cannot narrow artifact kinds while long durable identifiers exist')
    with op.batch_alter_table('artifacts') as batch:
        batch.alter_column('kind', existing_type=String(128), type_=String(50),
                           existing_nullable=False)
