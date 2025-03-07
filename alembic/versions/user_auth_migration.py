"""User authentication tables

Revision ID: user_auth_migration
Revises: initial_migration
Create Date: 2025-07-03 09:17:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = 'user_auth_migration'
down_revision = 'initial_migration'
branch_labels = None
depends_on = None


def upgrade():
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # Create auth_providers table
    op.create_table(
        'auth_providers',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('provider_type', sa.String(), nullable=False),
        sa.Column('provider_user_id', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('provider_type', 'provider_user_id',
                            name='unique_provider_account')
    )

    # Add user_id column to conversations table
    op.add_column('conversations', sa.Column(
        'user_id', postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(None, 'conversations', 'users', ['user_id'], ['id'])


def downgrade():
    # Drop foreign key from conversations table
    op.drop_constraint(None, 'conversations', type_='foreignkey')

    # Drop user_id column from conversations table
    op.drop_column('conversations', 'user_id')

    # Drop auth_providers table
    op.drop_table('auth_providers')

    # Drop users table
    op.drop_table('users')
