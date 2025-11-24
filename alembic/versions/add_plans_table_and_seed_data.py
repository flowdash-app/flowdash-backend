"""Add plans table and seed data

Revision ID: plans_001
Revises: subscription_001
Create Date: 2025-01-15 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from datetime import datetime


# revision identifiers, used by Alembic.
revision = 'plans_001'
down_revision = 'subscription_001'
branch_labels = None
depends_on = None


def upgrade():
    # Create plans table
    op.create_table('plans',
        sa.Column('tier', sa.String(), nullable=False),
        sa.Column('name', sa.String(), nullable=False),
        sa.Column('price_monthly', sa.Numeric(10, 2), nullable=False),
        sa.Column('price_yearly', sa.Numeric(10, 2), nullable=False),
        sa.Column('limits', JSONB, nullable=False),
        sa.Column('features', JSONB, nullable=False),
        sa.Column('active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('recommended', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=True, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('tier')
    )
    op.create_index(op.f('ix_plans_active'), 'plans', ['active'], unique=False)
    op.create_index(op.f('ix_plans_recommended'), 'plans', ['recommended'], unique=False)
    
    # Seed free plan
    op.execute("""
        INSERT INTO plans (tier, name, price_monthly, price_yearly, limits, features, active, recommended, created_at, updated_at)
        VALUES (
            'free',
            'Free',
            0.00,
            0.00,
            '{"toggles_per_day": 0, "refreshes_per_day": 5, "error_views_per_day": 3, "triggers": 1, "max_instances": 1, "push_notifications": false, "cache_ttl_minutes": 30}'::jsonb,
            '["Read-only monitoring", "5 list refreshes per day", "3 detailed error views per day", "1 simple mobile trigger", "1 n8n instance", "30-minute data cache"]'::jsonb,
            true,
            false,
            now(),
            now()
        )
    """)
    
    # Seed pro plan
    op.execute("""
        INSERT INTO plans (tier, name, price_monthly, price_yearly, limits, features, active, recommended, created_at, updated_at)
        VALUES (
            'pro',
            'Pro',
            19.99,
            199.99,
            '{"toggles_per_day": 100, "refreshes_per_day": 200, "error_views_per_day": -1, "triggers": 10, "max_instances": 5, "push_notifications": true, "cache_ttl_minutes": 3}'::jsonb,
            '["Instant push notifications", "100 workflow toggles per day", "200 list refreshes per day", "Unlimited detailed error views", "10 custom triggers with forms", "Up to 5 n8n instances"]'::jsonb,
            true,
            true,
            now(),
            now()
        )
    """)


def downgrade():
    op.drop_index(op.f('ix_plans_recommended'), table_name='plans')
    op.drop_index(op.f('ix_plans_active'), table_name='plans')
    op.drop_table('plans')

