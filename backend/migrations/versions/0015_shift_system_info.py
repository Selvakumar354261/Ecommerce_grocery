"""Record cashier system information on shifts."""
from alembic import op
import sqlalchemy as sa

revision='0015'
down_revision='0014'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('shifts',sa.Column('client_ip',sa.String(45),nullable=True))
    op.add_column('shifts',sa.Column('system_info',sa.String(200),nullable=True))

def downgrade():
    op.drop_column('shifts','system_info')
    op.drop_column('shifts','client_ip')
