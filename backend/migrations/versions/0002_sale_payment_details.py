"""Add POS payment tender and change details."""
from alembic import op
import sqlalchemy as sa

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('sales', sa.Column('amount_tendered', sa.Numeric(12, 2), nullable=True))
    op.add_column('sales', sa.Column('change_due', sa.Numeric(12, 2), nullable=False, server_default='0'))
    op.alter_column('sales', 'change_due', server_default=None)

def downgrade():
    op.drop_column('sales', 'change_due')
    op.drop_column('sales', 'amount_tendered')
