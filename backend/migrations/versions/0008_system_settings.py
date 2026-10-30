"""Add backend-managed system settings."""
from alembic import op
import sqlalchemy as sa

revision='0008'
down_revision='0007'
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('system_settings',
        sa.Column('key',sa.String(80),primary_key=True),
        sa.Column('value',sa.String(500),nullable=False),
        sa.Column('updated_by',sa.Integer(),sa.ForeignKey('users.id'),nullable=True),
        sa.Column('updated_at',sa.DateTime(timezone=True),nullable=False),
    )
    op.execute("INSERT INTO system_settings (key,value,updated_at) VALUES ('reservation_minutes','30',CURRENT_TIMESTAMP)")

def downgrade():
    op.drop_table('system_settings')
