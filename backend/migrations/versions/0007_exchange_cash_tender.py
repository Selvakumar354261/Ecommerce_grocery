"""Record cash tender and change on return/exchange settlements."""
from alembic import op
import sqlalchemy as sa

revision='0007'
down_revision='0006'
branch_labels=None
depends_on=None

def upgrade():
    op.add_column('return_exchanges',sa.Column('amount_tendered',sa.Numeric(12,2),nullable=True))
    op.add_column('return_exchanges',sa.Column('change_due',sa.Numeric(12,2),nullable=False,server_default='0'))
    op.alter_column('return_exchanges','change_due',server_default=None)

def downgrade():
    op.drop_column('return_exchanges','change_due')
    op.drop_column('return_exchanges','amount_tendered')
