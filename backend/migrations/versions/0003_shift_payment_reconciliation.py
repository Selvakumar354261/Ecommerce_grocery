"""Reconcile card and UPI totals when closing cashier shifts."""
from alembic import op
import sqlalchemy as sa

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    for name in ('counted_card','expected_card','card_variance','counted_upi','expected_upi','upi_variance'):
        op.add_column('shifts', sa.Column(name, sa.Numeric(12, 2), nullable=True))

def downgrade():
    for name in reversed(('counted_card','expected_card','card_variance','counted_upi','expected_upi','upi_variance')):
        op.drop_column('shifts', name)
