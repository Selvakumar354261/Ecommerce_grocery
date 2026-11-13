"""Record online-order collection methods, splits, cash tender and change."""
from alembic import op
import sqlalchemy as sa

revision = '0020'
down_revision = '0019'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('order_collections',
        sa.Column('order_id', sa.Integer(), sa.ForeignKey('orders.id'), primary_key=True),
        sa.Column('actor_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('payment_method', sa.String(20), nullable=False),
        sa.Column('payments', sa.JSON(), nullable=False),
        sa.Column('total', sa.Numeric(12, 2), nullable=False),
        sa.Column('amount_tendered', sa.Numeric(12, 2), nullable=True),
        sa.Column('change_due', sa.Numeric(12, 2), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    )


def downgrade():
    op.drop_table('order_collections')
