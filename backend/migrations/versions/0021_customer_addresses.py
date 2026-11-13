"""Customer-owned saved addresses and coordinates."""
from alembic import op
import sqlalchemy as sa

revision='0021'
down_revision='0020'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('customer_addresses',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('user_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('label',sa.String(80),nullable=False),
        sa.Column('address',sa.String(500),nullable=False),
        sa.Column('latitude',sa.Numeric(10,7),nullable=False),
        sa.Column('longitude',sa.Numeric(10,7),nullable=False),
        sa.CheckConstraint('latitude >= -90 AND latitude <= 90'),
        sa.CheckConstraint('longitude >= -180 AND longitude <= 180'))
    op.create_index('ix_customer_addresses_user_id','customer_addresses',['user_id'])

def downgrade():
    op.drop_table('customer_addresses')
