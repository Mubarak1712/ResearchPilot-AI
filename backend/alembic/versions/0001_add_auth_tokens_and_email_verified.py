"""add auth tokens and email verified

Revision ID: 0001_add_auth_tokens
Revises: 
Create Date: 2026-08-26
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_add_auth_tokens'
down_revision = '20260823_0004'
branch_labels = None
depends_on = None


def upgrade():
    # add is_email_verified column to users
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('is_email_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')))

    # create auth_tokens table
    op.create_table(
        'auth_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('token', sa.String(length=128), nullable=False, unique=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('token_type', sa.String(length=50), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table('auth_tokens')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('is_email_verified')
