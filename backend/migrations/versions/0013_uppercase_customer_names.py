"""Normalize customer names to uppercase."""
from alembic import op

revision='0013'
down_revision='0012'
branch_labels=None
depends_on=None

def upgrade():
    op.execute("UPDATE users SET name = UPPER(TRIM(name)) WHERE role = 'customer'")
    op.execute("UPDATE pos_customers SET name = UPPER(TRIM(name))")
    op.execute("UPDATE sales SET customer_name = UPPER(TRIM(customer_name))")

def downgrade():
    pass
