"""Store POS payment allocations for split payments."""
from alembic import op
import sqlalchemy as sa

revision='0016'
down_revision='0015'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('sale_payments',
        sa.Column('id',sa.Integer(),primary_key=True),
        sa.Column('sale_id',sa.Integer(),sa.ForeignKey('sales.id',ondelete='CASCADE'),nullable=False),
        sa.Column('method',sa.String(20),nullable=False),
        sa.Column('amount',sa.Numeric(12,2),nullable=False),
        sa.UniqueConstraint('sale_id','method',name='uq_sale_payment_method'))
    op.create_index('ix_sale_payments_sale_id','sale_payments',['sale_id'])
    op.execute("INSERT INTO sale_payments (sale_id, method, amount) SELECT id, payment_method, total FROM sales WHERE payment_method IN ('cash','card','upi')")

def downgrade():
    op.drop_index('ix_sale_payments_sale_id',table_name='sale_payments')
    op.drop_table('sale_payments')
