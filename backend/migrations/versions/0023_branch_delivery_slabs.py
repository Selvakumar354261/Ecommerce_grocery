"""Configurable distance-based delivery prices per branch."""
from alembic import op
import sqlalchemy as sa
revision='0023'
down_revision='0022'
branch_labels=None
depends_on=None
def upgrade():
    op.add_column('branches',sa.Column('delivery_slabs',sa.JSON(),nullable=False,server_default='[]'))
def downgrade():
    op.drop_column('branches','delivery_slabs')
