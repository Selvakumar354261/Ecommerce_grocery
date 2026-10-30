"""Store the manager-approved delivery estimate."""
from alembic import op
import sqlalchemy as sa

revision='0011'
down_revision='0010'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('orders',sa.Column('estimated_delivery_days',sa.Integer(),nullable=True))

def downgrade():
    op.drop_column('orders','estimated_delivery_days')
