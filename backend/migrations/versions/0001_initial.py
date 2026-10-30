"""Initial schema. SQL snapshot is immutable; future changes use new revisions."""
from pathlib import Path
from alembic import op
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    sql=(Path(__file__).parent.parent/'initial.sql').read_text()
    for statement in sql.split(';'):
        if statement.strip():op.execute(statement)

def downgrade():
    for table in ['count_requests','idempotency','audit','purchases','suppliers','transfers','sale_items','sales','shifts','order_events','order_items','orders','movements','stock','variants','products','login_attempts','sessions','users','branches']:
        op.execute(f'DROP TABLE IF EXISTS {table}')
