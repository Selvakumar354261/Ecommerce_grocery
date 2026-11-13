"""Store the contact mobile with each saved delivery location."""
from alembic import op
import sqlalchemy as sa

revision='0022'
down_revision='0021'
branch_labels=None
depends_on=None

def upgrade():
    # Existing locations have no known contact; never invent one.
    op.add_column('customer_addresses',sa.Column('phone',sa.String(10),nullable=True))

def downgrade():
    op.drop_column('customer_addresses','phone')
