"""Add auditable return and exchange transactions."""
from alembic import op
import sqlalchemy as sa

revision='0006'
down_revision='0005'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('return_exchanges',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('sale_id',sa.Integer(),sa.ForeignKey('sales.id'),nullable=False),
        sa.Column('branch_id',sa.Integer(),sa.ForeignKey('branches.id'),nullable=False),
        sa.Column('actor_id',sa.Integer(),sa.ForeignKey('users.id'),nullable=False),
        sa.Column('shift_id',sa.Integer(),sa.ForeignKey('shifts.id'),nullable=False),
        sa.Column('customer_code',sa.String(20),nullable=False),
        sa.Column('kind',sa.String(20),nullable=False),
        sa.Column('returned_items',sa.JSON(),nullable=False),
        sa.Column('replacement_items',sa.JSON(),nullable=False),
        sa.Column('return_total',sa.Numeric(12,2),nullable=False),
        sa.Column('replacement_total',sa.Numeric(12,2),nullable=False),
        sa.Column('amount_due',sa.Numeric(12,2),nullable=False),
        sa.Column('refund_due',sa.Numeric(12,2),nullable=False),
        sa.Column('settlement_method',sa.String(20),nullable=False),
        sa.Column('reason',sa.String(500),nullable=False),
        sa.Column('created_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_return_exchanges_sale_id','return_exchanges',['sale_id'])
    op.create_index('ix_return_exchanges_branch_id','return_exchanges',['branch_id'])
    op.create_index('ix_return_exchanges_shift_id','return_exchanges',['shift_id'])

def downgrade():
    op.drop_index('ix_return_exchanges_branch_id',table_name='return_exchanges')
    op.drop_index('ix_return_exchanges_sale_id',table_name='return_exchanges')
    op.drop_table('return_exchanges')
    op.drop_index('ix_return_exchanges_shift_id',table_name='return_exchanges')
