"""Store customer delivery coordinates on orders.

Revision ID: 0018
Revises: 0017
"""
from alembic import op
import sqlalchemy as sa

revision = '0018'
down_revision = '0017'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('orders', sa.Column('latitude', sa.Numeric(10, 7), nullable=True))
    op.add_column('orders', sa.Column('longitude', sa.Numeric(10, 7), nullable=True))

def downgrade():
    op.drop_column('orders', 'longitude')
    op.drop_column('orders', 'latitude')
