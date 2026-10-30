"""Add reusable POS customers and sale customer snapshots."""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None

def upgrade():
    op.create_table('pos_customers',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('mobile',sa.String(10),nullable=False),
        sa.Column('name',sa.String(100),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
        sa.UniqueConstraint('mobile'))
    op.create_index('ix_pos_customers_mobile','pos_customers',['mobile'],unique=True)
    op.add_column('sales',sa.Column('customer_id',sa.Integer(),nullable=True))
    op.add_column('sales',sa.Column('customer_name',sa.String(100),nullable=True))
    op.add_column('sales',sa.Column('customer_mobile',sa.String(10),nullable=True))
    op.create_foreign_key('fk_sales_customer_id','sales','pos_customers',['customer_id'],['id'])
    op.create_index('ix_sales_customer_id','sales',['customer_id'])
    op.create_index('ix_sales_customer_mobile','sales',['customer_mobile'])

def downgrade():
    op.drop_index('ix_sales_customer_mobile',table_name='sales')
    op.drop_index('ix_sales_customer_id',table_name='sales')
    op.drop_constraint('fk_sales_customer_id','sales',type_='foreignkey')
    op.drop_column('sales','customer_mobile')
    op.drop_column('sales','customer_name')
    op.drop_column('sales','customer_id')
    op.drop_index('ix_pos_customers_mobile',table_name='pos_customers')
    op.drop_table('pos_customers')
