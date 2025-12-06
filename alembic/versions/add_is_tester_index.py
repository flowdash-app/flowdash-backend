"""Add index on is_tester column for performance

Revision ID: tester_index_001
Revises: subscription_001
Create Date: 2025-12-05 05:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'tester_index_001'
down_revision = 'subscription_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add index on is_tester column for performance optimization
    # This speeds up queries that filter by is_tester status
    op.create_index(op.f('ix_users_is_tester'), 'users', ['is_tester'], unique=False)


def downgrade():
    # Remove index on is_tester column
    op.drop_index(op.f('ix_users_is_tester'), table_name='users')
