"""Add mobile OTP customer authentication."""
from alembic import op
import sqlalchemy as sa

revision='0012'
down_revision='0011'
branch_labels=None
depends_on=None

def upgrade():
    op.alter_column('users','email',existing_type=sa.String(180),nullable=True)
    op.alter_column('users','password_hash',existing_type=sa.String(256),nullable=True)
    op.add_column('users',sa.Column('phone',sa.String(20),nullable=True))
    op.create_unique_constraint('uq_users_phone','users',['phone'])
    op.create_table('mobile_otps',
        sa.Column('phone',sa.String(20),primary_key=True),
        sa.Column('code_hash',sa.String(64),nullable=False),
        sa.Column('expires_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('sent_at',sa.DateTime(timezone=True),nullable=False),
        sa.Column('attempts',sa.Integer(),nullable=False,server_default='0'))

def downgrade():
    op.drop_table('mobile_otps')
    op.drop_constraint('uq_users_phone','users',type_='unique')
    op.drop_column('users','phone')
    op.alter_column('users','password_hash',existing_type=sa.String(256),nullable=False)
    op.alter_column('users','email',existing_type=sa.String(180),nullable=False)
