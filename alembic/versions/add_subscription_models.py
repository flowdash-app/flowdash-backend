"""Add subscription models and user plan_tier

Revision ID: subscription_001
Revises: 58bf1d9670e3
Create Date: 2025-11-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'subscription_001'
down_revision = '58bf1d9670e3'
branch_labels = None
depends_on = None


def upgrade():
    # Add plan_tier and is_tester to users table
    op.add_column('users', sa.Column('plan_tier', sa.String(), nullable=False, server_default='free'))
    op.add_column('users', sa.Column('is_tester', sa.Boolean(), nullable=False, server_default='false'))
    op.create_index(op.f('ix_users_plan_tier'), 'users', ['plan_tier'], unique=False)
    
    # Create subscriptions table
    op.create_table('subscriptions',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('plan_tier', sa.String(), nullable=False),
        sa.Column('status', sa.Enum('ACTIVE', 'CANCELLED', 'EXPIRED', 'PENDING', name='subscriptionstatus'), nullable=False),
        sa.Column('billing_period', sa.Enum('MONTHLY', 'YEARLY', name='billingperiod'), nullable=True),
        sa.Column('platform', sa.Enum('GOOGLE_PLAY', 'APPLE_STORE', name='platform'), nullable=True),
        sa.Column('purchase_token', sa.String(), nullable=True),
        sa.Column('receipt_data', sa.String(), nullable=True),
        sa.Column('start_date', sa.DateTime(), nullable=True),
        sa.Column('end_date', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscriptions_id'), 'subscriptions', ['id'], unique=False)
    op.create_index(op.f('ix_subscriptions_plan_tier'), 'subscriptions', ['plan_tier'], unique=False)
    op.create_index(op.f('ix_subscriptions_status'), 'subscriptions', ['status'], unique=False)
    op.create_index(op.f('ix_subscriptions_user_id'), 'subscriptions', ['user_id'], unique=False)
    
    # Create subscription_history table
    op.create_table('subscription_history',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=False),
        sa.Column('subscription_id', sa.String(), nullable=False),
        sa.Column('action', sa.String(), nullable=False),
        sa.Column('from_plan', sa.String(), nullable=True),
        sa.Column('to_plan', sa.String(), nullable=True),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['subscription_id'], ['subscriptions.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_subscription_history_action'), 'subscription_history', ['action'], unique=False)
    op.create_index(op.f('ix_subscription_history_created_at'), 'subscription_history', ['created_at'], unique=False)
    op.create_index(op.f('ix_subscription_history_id'), 'subscription_history', ['id'], unique=False)
    op.create_index(op.f('ix_subscription_history_subscription_id'), 'subscription_history', ['subscription_id'], unique=False)
    op.create_index(op.f('ix_subscription_history_user_id'), 'subscription_history', ['user_id'], unique=False)


def downgrade():
    # Drop subscription_history table
    op.drop_index(op.f('ix_subscription_history_user_id'), table_name='subscription_history')
    op.drop_index(op.f('ix_subscription_history_subscription_id'), table_name='subscription_history')
    op.drop_index(op.f('ix_subscription_history_id'), table_name='subscription_history')
    op.drop_index(op.f('ix_subscription_history_created_at'), table_name='subscription_history')
    op.drop_index(op.f('ix_subscription_history_action'), table_name='subscription_history')
    op.drop_table('subscription_history')
    
    # Drop subscriptions table
    op.drop_index(op.f('ix_subscriptions_user_id'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_status'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_plan_tier'), table_name='subscriptions')
    op.drop_index(op.f('ix_subscriptions_id'), table_name='subscriptions')
    op.drop_table('subscriptions')
    
    # Remove plan_tier and is_tester from users
    op.drop_index(op.f('ix_users_plan_tier'), table_name='users')
    op.drop_column('users', 'is_tester')
    op.drop_column('users', 'plan_tier')

