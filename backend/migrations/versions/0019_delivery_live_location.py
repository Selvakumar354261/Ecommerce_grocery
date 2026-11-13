"""Store latest delivery-person location."""
from alembic import op
import sqlalchemy as sa
revision='0019';down_revision='0018';branch_labels=None;depends_on=None
def upgrade():
    op.add_column('orders',sa.Column('driver_latitude',sa.Numeric(10,7),nullable=True))
    op.add_column('orders',sa.Column('driver_longitude',sa.Numeric(10,7),nullable=True))
    op.add_column('orders',sa.Column('driver_location_updated_at',sa.DateTime(timezone=True),nullable=True))
def downgrade():
    op.drop_column('orders','driver_location_updated_at');op.drop_column('orders','driver_longitude');op.drop_column('orders','driver_latitude')
