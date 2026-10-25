"""Preserve full source labels and calculation periods when publishing evidence."""
from alembic import op
from sqlalchemy import String, Text, inspect, text

revision = "0005_evidence_label_capacity"
down_revision = "0004_artifact_kind_capacity"
branch_labels = None
depends_on = None

COLUMNS = {"passages": {"section": 300, "row_label": 300, "column_label": 300},
           "calculations": {"period": 100}}


def upgrade():
    # SQLite does not enforce VARCHAR lengths. Avoid rebuilding a populated
    # evidence table whose passages are referenced by facts and evidence links.
    if op.get_bind().dialect.name == "sqlite":
        return
    for table, columns in COLUMNS.items():
        existing = {column["name"]: column for column in inspect(op.get_bind()).get_columns(table)}
        bounded = {name: existing[name] for name in columns
                   if getattr(existing[name]["type"], "length", None) is not None}
        if bounded:
            with op.batch_alter_table(table) as batch:
                for name, column in bounded.items():
                    batch.alter_column(name, existing_type=column["type"], type_=Text(),
                                       existing_nullable=True)


def downgrade():
    bind = op.get_bind()
    # Check every field before changing any column; never truncate source evidence.
    for table, columns in COLUMNS.items():
        for name, length in columns.items():
            if bind.execute(text(f'SELECT 1 FROM {table} WHERE length({name}) > :limit LIMIT 1'),
                            {"limit": length}).first():
                raise RuntimeError("Cannot narrow evidence labels while long source values exist")
    if bind.dialect.name == "sqlite":
        return
    for table, columns in COLUMNS.items():
        with op.batch_alter_table(table) as batch:
            for name, length in columns.items():
                batch.alter_column(name, existing_type=Text(), type_=String(length),
                                   existing_nullable=True)
