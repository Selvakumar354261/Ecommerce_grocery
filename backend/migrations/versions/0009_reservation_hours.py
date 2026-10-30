"""Store the reservation duration in hours."""
from alembic import op

revision='0009'
down_revision='0008'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("UPDATE system_settings SET key='reservation_hours', value=GREATEST(1, CEIL(CAST(value AS numeric) / 60))::integer::text WHERE key='reservation_minutes'")

def downgrade():
    op.execute("UPDATE system_settings SET key='reservation_minutes', value=(CAST(value AS integer) * 60)::text WHERE key='reservation_hours'")
