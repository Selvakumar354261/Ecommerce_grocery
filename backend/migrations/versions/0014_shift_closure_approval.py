"""Add manager approval workflow for shift closure."""
from alembic import op
import sqlalchemy as sa

revision='0014'
down_revision='0013'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('shifts',sa.Column('closure_status',sa.String(20),nullable=False,server_default='open'))
    op.add_column('shifts',sa.Column('closure_requested_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('shifts',sa.Column('shortage_reason',sa.String(500),nullable=True))
    op.add_column('shifts',sa.Column('approved_at',sa.DateTime(timezone=True),nullable=True))
    op.add_column('shifts',sa.Column('approved_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=True))
    op.execute("UPDATE shifts SET closure_status = 'approved', closure_requested_at = closed_at, approved_at = closed_at WHERE closed_at IS NOT NULL")

def downgrade():
    op.drop_column('shifts','approved_by')
    op.drop_column('shifts','approved_at')
    op.drop_column('shifts','shortage_reason')
    op.drop_column('shifts','closure_requested_at')
    op.drop_column('shifts','closure_status')
