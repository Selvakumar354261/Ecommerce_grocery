"""Assign online orders to delivery personnel."""
from alembic import op
import sqlalchemy as sa

revision='0017'
down_revision='0016'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('orders',sa.Column('assigned_delivery_user_id',sa.Integer(),nullable=True))
    op.add_column('orders',sa.Column('delivery_assigned_at',sa.DateTime(timezone=True),nullable=True))
    op.create_foreign_key('fk_orders_delivery_user','orders','users',['assigned_delivery_user_id'],['id'])
    op.create_index('ix_orders_assigned_delivery_user_id','orders',['assigned_delivery_user_id'])

def downgrade():
    op.drop_index('ix_orders_assigned_delivery_user_id',table_name='orders')
    op.drop_constraint('fk_orders_delivery_user','orders',type_='foreignkey')
    op.drop_column('orders','delivery_assigned_at')
    op.drop_column('orders','assigned_delivery_user_id')
