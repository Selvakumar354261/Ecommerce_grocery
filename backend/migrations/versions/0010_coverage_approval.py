"""Add manager approval workflow for out-of-coverage deliveries."""
from alembic import op
import sqlalchemy as sa

revision='0010'
down_revision='0009'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('orders',sa.Column('coverage_approval_required',sa.Boolean(),nullable=False,server_default=sa.false()))
    op.add_column('orders',sa.Column('delivery_distance_km',sa.Numeric(8,2),nullable=True))
    op.add_column('orders',sa.Column('approval_expires_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('orders',sa.Column('coverage_approved_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('orders',sa.Column('coverage_approved_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=True))
    op.alter_column('orders','coverage_approval_required',server_default=None)

def downgrade():
    op.drop_column('orders','coverage_approved_by')
    op.drop_column('orders','coverage_approved_at')
    op.drop_column('orders','approval_expires_at')
    op.drop_column('orders','delivery_distance_km')
    op.drop_column('orders','coverage_approval_required')
