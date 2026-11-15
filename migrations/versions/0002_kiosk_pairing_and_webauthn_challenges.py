"""kiosk pairing and webauthn challenges

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-15 16:09:07.252122
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('webauthn_challenges',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('challenge', sa.LargeBinary(), nullable=False),
    sa.Column('purpose', sa.String(length=10), nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('invite_id', sa.BigInteger(), nullable=True),
    sa.Column('session_id', sa.BigInteger(), nullable=True),
    sa.Column('data', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.CheckConstraint("purpose IN ('register', 'login', 'clock')", name='purpose_valid'),
    sa.ForeignKeyConstraint(['invite_id'], ['invites.id'], ),
    sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_webauthn_challenges_expires_at', 'webauthn_challenges', ['expires_at'], unique=False)
    op.add_column('kiosks', sa.Column('setup_token_hash', sa.LargeBinary(), nullable=False))
    op.add_column('kiosks', sa.Column('setup_expires_at', sa.DateTime(timezone=True), nullable=False))
    op.add_column('kiosks', sa.Column('paired_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('kiosks', sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True))
    op.alter_column('kiosks', 'token_hash',
               existing_type=postgresql.BYTEA(),
               nullable=True)
    op.alter_column('kiosks', 'created_by',
               existing_type=sa.BIGINT(),
               nullable=True)
    op.create_unique_constraint('kiosks_setup_token_hash_key', 'kiosks', ['setup_token_hash'])


def downgrade() -> None:
    op.drop_constraint('kiosks_setup_token_hash_key', 'kiosks', type_='unique')
    op.alter_column('kiosks', 'created_by',
               existing_type=sa.BIGINT(),
               nullable=False)
    op.alter_column('kiosks', 'token_hash',
               existing_type=postgresql.BYTEA(),
               nullable=False)
    op.drop_column('kiosks', 'last_seen_at')
    op.drop_column('kiosks', 'paired_at')
    op.drop_column('kiosks', 'setup_expires_at')
    op.drop_column('kiosks', 'setup_token_hash')
    op.drop_index('ix_webauthn_challenges_expires_at', table_name='webauthn_challenges')
    op.drop_table('webauthn_challenges')
