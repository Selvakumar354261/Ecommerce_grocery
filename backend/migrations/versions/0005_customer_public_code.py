"""Add receipt-safe public customer references."""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('pos_customers',sa.Column('public_code',sa.String(20),nullable=True))
    op.execute("UPDATE pos_customers SET public_code = 'CUS-' || UPPER(SUBSTRING(MD5(mobile || ':' || id::text) FROM 1 FOR 10))")
    op.alter_column('pos_customers','public_code',nullable=False)
    op.create_index('ix_pos_customers_public_code','pos_customers',['public_code'],unique=True)
    op.add_column('sales',sa.Column('customer_code',sa.String(20),nullable=True))
    op.execute("UPDATE sales SET customer_code = pos_customers.public_code FROM pos_customers WHERE sales.customer_id = pos_customers.id")

def downgrade():
    op.drop_column('sales','customer_code')
    op.drop_index('ix_pos_customers_public_code',table_name='pos_customers')
    op.drop_column('pos_customers','public_code')
