"""initial schema

Revision ID: 0001
Revises: 
Activity log is append-only for everyone: a trigger refuses UPDATE and DELETE.

Create Date: 2026-11-15 15:45:40.897765
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('login_failures',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('key', sa.String(length=300), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_login_failures_key_time', 'login_failures', ['key', 'created_at'], unique=False)
    op.create_table('users',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=254), nullable=True),
    sa.Column('role', sa.String(length=10), nullable=False),
    sa.Column('password_hash', sa.Text(), nullable=True),
    sa.Column('active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(role = 'md') = (email IS NOT NULL)", name='email_only_for_md'),
    sa.CheckConstraint("(role = 'md') = (password_hash IS NOT NULL)", name='password_only_for_md'),
    sa.CheckConstraint("role IN ('worker', 'manager', 'md')", name='role_valid'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('uq_users_email', 'users', [sa.literal_column('lower(email)')], unique=True, postgresql_where=sa.text('email IS NOT NULL'))
    op.create_index('uq_users_one_active_md_or_manager', 'users', ['role'], unique=True, postgresql_where=sa.text("active AND role IN ('md', 'manager')"))
    op.create_table('activity_log',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=True),
    sa.Column('action', sa.String(length=40), nullable=False),
    sa.Column('entity', sa.String(length=40), nullable=False),
    sa.Column('entity_id', sa.String(length=100), nullable=True),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_activity_log_created_at', 'activity_log', ['created_at'], unique=False)
    op.create_table('devices',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('credential_id', sa.LargeBinary(), nullable=False),
    sa.Column('public_key', sa.LargeBinary(), nullable=False),
    sa.Column('sign_count', sa.BigInteger(), server_default=sa.text('0'), nullable=False),
    sa.Column('transports', postgresql.ARRAY(sa.String(length=20)), nullable=True),
    sa.Column('registered_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('credential_id')
    )
    op.create_index('uq_devices_one_active_per_user', 'devices', ['user_id'], unique=True, postgresql_where=sa.text('revoked_at IS NULL'))
    op.create_table('invites',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.LargeBinary(), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_invites_user_id'), 'invites', ['user_id'], unique=False)
    op.create_table('kiosks',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('token_hash', sa.LargeBinary(), nullable=False),
    sa.Column('created_by', sa.BigInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['created_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_table('reasons',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('work_date', sa.Date(), nullable=False),
    sa.Column('type', sa.String(length=20), nullable=False),
    sa.Column('claimed_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('text', sa.String(length=500), server_default='', nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(type = 'missed_clock_out') = (claimed_time IS NOT NULL)", name='claimed_time_only_for_missed_clock_out'),
    sa.CheckConstraint("type IN ('late', 'absent', 'missed_clock_out', 'left_early')", name='type_valid'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'work_date', 'type', name='uq_reasons_one_per_type_per_day')
    )
    op.create_table('scan_attempts',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=True),
    sa.Column('result', sa.String(length=40), nullable=False),
    sa.Column('method', sa.String(length=5), nullable=True),
    sa.Column('client_ms_to_scan', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_scan_attempts_created_at', 'scan_attempts', ['created_at'], unique=False)
    op.create_table('decisions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('reason_id', sa.BigInteger(), nullable=False),
    sa.Column('actor_id', sa.BigInteger(), nullable=False),
    sa.Column('decision', sa.String(length=10), nullable=False),
    sa.Column('note', sa.String(length=500), server_default='', nullable=False),
    sa.Column('is_override', sa.Boolean(), server_default=sa.text('false'), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("decision IN ('approved', 'rejected')", name='decision_valid'),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['reason_id'], ['reasons.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_decisions_reason_id'), 'decisions', ['reason_id'], unique=False)
    op.create_table('scans',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('kind', sa.String(length=3), nullable=False),
    sa.Column('server_time', sa.DateTime(timezone=True), nullable=False),
    sa.Column('work_date', sa.Date(), nullable=False),
    sa.Column('source', sa.String(length=5), nullable=False),
    sa.Column('kiosk_id', sa.BigInteger(), nullable=True),
    sa.Column('kiosk_window', sa.BigInteger(), nullable=True),
    sa.Column('ip', sa.String(length=45), nullable=True),
    sa.Column('entered_by', sa.BigInteger(), nullable=True),
    sa.Column('paper_reason', sa.String(length=30), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("(source = 'paper') = (entered_by IS NOT NULL AND paper_reason IS NOT NULL)", name='paper_needs_who_and_why'),
    sa.CheckConstraint("kind IN ('in', 'out')", name='kind_valid'),
    sa.CheckConstraint("paper_reason IS NULL OR paper_reason IN ('tv_not_working', 'no_smartphone', 'phone_dead_or_forgotten')", name='paper_reason_valid'),
    sa.CheckConstraint("source IN ('qr', 'typed', 'paper')", name='source_valid'),
    sa.ForeignKeyConstraint(['entered_by'], ['users.id'], ),
    sa.ForeignKeyConstraint(['kiosk_id'], ['kiosks.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'work_date', 'kind', name='uq_scans_one_per_kind_per_day')
    )
    op.create_index('ix_scans_work_date', 'scans', ['work_date'], unique=False)
    op.create_table('sessions',
    sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
    sa.Column('user_id', sa.BigInteger(), nullable=False),
    sa.Column('token_hash', sa.LargeBinary(), nullable=False),
    sa.Column('csrf_token', sa.String(length=64), nullable=False),
    sa.Column('device_id', sa.BigInteger(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['device_id'], ['devices.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('token_hash')
    )
    op.create_index(op.f('ix_sessions_user_id'), 'sessions', ['user_id'], unique=False)

    op.execute("""
        CREATE FUNCTION activity_log_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'activity_log is append-only';
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER activity_log_append_only
        BEFORE UPDATE OR DELETE OR TRUNCATE ON activity_log
        FOR EACH STATEMENT EXECUTE FUNCTION activity_log_append_only();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS activity_log_append_only ON activity_log")
    op.execute("DROP FUNCTION IF EXISTS activity_log_append_only()")
    op.drop_index(op.f('ix_sessions_user_id'), table_name='sessions')
    op.drop_table('sessions')
    op.drop_index('ix_scans_work_date', table_name='scans')
    op.drop_table('scans')
    op.drop_index(op.f('ix_decisions_reason_id'), table_name='decisions')
    op.drop_table('decisions')
    op.drop_index('ix_scan_attempts_created_at', table_name='scan_attempts')
    op.drop_table('scan_attempts')
    op.drop_table('reasons')
    op.drop_table('kiosks')
    op.drop_index(op.f('ix_invites_user_id'), table_name='invites')
    op.drop_table('invites')
    op.drop_index('uq_devices_one_active_per_user', table_name='devices', postgresql_where=sa.text('revoked_at IS NULL'))
    op.drop_table('devices')
    op.drop_index('ix_activity_log_created_at', table_name='activity_log')
    op.drop_table('activity_log')
    op.drop_index('uq_users_one_active_md_or_manager', table_name='users', postgresql_where=sa.text("active AND role IN ('md', 'manager')"))
    op.drop_index('uq_users_email', table_name='users', postgresql_where=sa.text('email IS NOT NULL'))
    op.drop_table('users')
    op.drop_index('ix_login_failures_key_time', table_name='login_failures')
    op.drop_table('login_failures')
