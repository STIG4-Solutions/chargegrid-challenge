"""Baseline do schema ChargeGrid.

DDL explicito, congelado no estado desta revisao. Nao usar
Base.metadata.create_all() aqui: o metadata reflete os modelos ATUAIS, entao a
baseline passaria a criar colunas introduzidas por migrations posteriores e o
upgrade quebraria num banco novo (DuplicateColumn na 0003).

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Codigos legiveis (SES-20483, INV-1042, RES-5007) vem de sequencias do banco.
# O autogenerate do Alembic nao detecta Sequence solta no metadata, entao ela
# precisa ser declarada aqui na mao - sem isso nenhuma sessao pode ser criada.
SEQUENCIAS = [
    ("session_code_seq", 20001),
    ("invoice_code_seq", 1001),
    ("reservation_code_seq", 5001),
]

# Series temporais append-only: BRIN e ordens de grandeza menor que B-tree
# quando as linhas ja chegam ordenadas no tempo, que e o caso do poller.
BRIN_INDEXES = [
    ("ix_telemetry_samples_recorded_at_brin", "telemetry_samples", "recorded_at"),
    ("ix_site_meter_readings_recorded_at_brin", "site_meter_readings", "recorded_at"),
    ("ix_command_logs_sent_at_brin", "command_logs", "sent_at"),
    ("ix_audit_logs_occurred_at_brin", "audit_logs", "occurred_at"),
]


def upgrade() -> None:
    for nome, inicio in SEQUENCIAS:
        op.execute(f"CREATE SEQUENCE IF NOT EXISTS {nome} START WITH {inicio}")

    op.create_table('sites',
    sa.Column('name', sa.String(length=160), nullable=False),
    sa.Column('address', sa.Text(), nullable=True),
    sa.Column('city', sa.String(length=80), nullable=True),
    sa.Column('state', sa.String(length=2), nullable=True),
    sa.Column('latitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('longitude', sa.Numeric(precision=9, scale=6), nullable=True),
    sa.Column('timezone', sa.String(length=64), nullable=False),
    sa.Column('grid_limit_kw', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('reserved_kw', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('main_breaker_current_a', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('allow_pv_kw', sa.Boolean(), nullable=False),
    sa.Column('allow_battery_kw', sa.Boolean(), nullable=False),
    sa.Column('battery_min_soc', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('default_tariff_id', sa.UUID(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_sites'))
    )
    op.create_table('tariffs',
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('type', sa.Enum('PER_KWH', 'PER_TIME', 'TIME_OF_USE', 'FLAT', name='tariff_type', native_enum=False), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('active', sa.Boolean(), nullable=False),
    sa.Column('price_per_kwh', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('price_per_min', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('idle_fee_per_min', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('session_fee', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('min_charge', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('free_minutes', sa.Integer(), nullable=False),
    sa.Column('dynamic_multiplier', sa.Numeric(precision=5, scale=3), nullable=False),
    sa.Column('dynamic_enabled', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_tariffs_site_id_sites'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tariffs'))
    )
    op.create_table('charge_points',
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=24), nullable=False),
    sa.Column('name', sa.String(length=120), nullable=False),
    sa.Column('serial_number', sa.String(length=32), nullable=True),
    sa.Column('connector', sa.Enum('TYPE2', 'CCS2', 'CHADEMO', name='connector_type', native_enum=False), nullable=False),
    sa.Column('phase_type', sa.Enum('SINGLE', 'THREE', name='phase_type', native_enum=False), nullable=False),
    sa.Column('rated_kw', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('min_kw', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('limit_kw', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('status', sa.Enum('AVAILABLE', 'PREPARING', 'CHARGING', 'SUSPENDED', 'FINISHING', 'RESERVED', 'FAULTED', 'OFFLINE', 'MAINTENANCE', name='charge_point_status', native_enum=False), nullable=False),
    sa.Column('current_kw', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('tariff_id', sa.UUID(), nullable=True),
    sa.Column('firmware_version', sa.String(length=32), nullable=True),
    sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('last_fault_code', sa.String(length=120), nullable=True),
    sa.Column('active_faults', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_charge_points_site_id_sites'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id'], name=op.f('fk_charge_points_tariff_id_tariffs'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_charge_points')),
    sa.UniqueConstraint('site_id', 'code', name='uq_charge_points_site_id_code')
    )
    op.create_index(op.f('ix_charge_points_serial_number'), 'charge_points', ['serial_number'], unique=False)
    op.create_index(op.f('ix_charge_points_status'), 'charge_points', ['status'], unique=False)
    op.create_table('site_meter_readings',
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('grid_import_kw', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('pv_kw', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('battery_kw', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('battery_soc', sa.Numeric(precision=5, scale=2), nullable=True),
    sa.Column('building_load_kw', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('ev_load_kw', sa.Numeric(precision=8, scale=2), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_site_meter_readings_site_id_sites'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_site_meter_readings'))
    )
    op.create_table('site_payment_methods',
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('kind', sa.Enum('PIX', 'CREDIT_CARD', 'RFID_SUBSCRIPTION', 'WALLET', name='payment_method_kind', native_enum=False), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=False),
    sa.Column('enabled', sa.Boolean(), nullable=False),
    sa.Column('fee_percent', sa.Numeric(precision=6, scale=3), nullable=False),
    sa.Column('fee_fixed', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('provider_config', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_site_payment_methods_site_id_sites'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_site_payment_methods')),
    sa.UniqueConstraint('site_id', 'kind', name='uq_site_payment_methods_site_id_kind')
    )
    op.create_table('tariff_windows',
    sa.Column('tariff_id', sa.UUID(), nullable=False),
    sa.Column('label', sa.String(length=60), nullable=False),
    sa.Column('day_mask', sa.SmallInteger(), nullable=False),
    sa.Column('starts_at', sa.Time(), nullable=False),
    sa.Column('ends_at', sa.Time(), nullable=False),
    sa.Column('price_per_kwh', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('price_per_min', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('idle_fee_per_min', sa.Numeric(precision=10, scale=4), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id'], name=op.f('fk_tariff_windows_tariff_id_tariffs'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_tariff_windows'))
    )
    op.create_table('users',
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('full_name', sa.String(length=160), nullable=False),
    sa.Column('hashed_password', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('ADMIN', 'OPERATOR', 'DRIVER', name='user_role', native_enum=False), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('phone', sa.String(length=32), nullable=True),
    sa.Column('document', sa.String(length=32), nullable=True),
    sa.Column('site_id', sa.UUID(), nullable=True),
    sa.Column('wallet_balance', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_users_site_id_sites'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_users'))
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_table('audit_logs',
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('actor_id', sa.UUID(), nullable=True),
    sa.Column('actor_email', sa.String(length=255), nullable=True),
    sa.Column('action', sa.String(length=64), nullable=False),
    sa.Column('entity_type', sa.String(length=48), nullable=False),
    sa.Column('entity_id', sa.String(length=64), nullable=True),
    sa.Column('before', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('after', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('ip_address', sa.String(length=64), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['actor_id'], ['users.id'], name=op.f('fk_audit_logs_actor_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_audit_logs'))
    )
    op.create_table('charge_point_connections',
    sa.Column('charge_point_id', sa.UUID(), nullable=False),
    sa.Column('protocol', sa.String(length=24), nullable=False),
    sa.Column('host', sa.String(length=120), nullable=True),
    sa.Column('port', sa.Integer(), nullable=False),
    sa.Column('unit_id', sa.Integer(), nullable=False),
    sa.Column('options', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['charge_point_id'], ['charge_points.id'], name=op.f('fk_charge_point_connections_charge_point_id_charge_points'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_charge_point_connections')),
    sa.UniqueConstraint('charge_point_id', name=op.f('uq_charge_point_connections_charge_point_id'))
    )
    op.create_table('command_logs',
    sa.Column('charge_point_id', sa.UUID(), nullable=False),
    sa.Column('sent_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('command', sa.String(length=48), nullable=False),
    sa.Column('register', sa.Integer(), nullable=True),
    sa.Column('raw_value', sa.Integer(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('success', sa.Boolean(), nullable=False),
    sa.Column('error', sa.Text(), nullable=True),
    sa.Column('latency_ms', sa.Integer(), nullable=True),
    sa.Column('triggered_by', sa.String(length=32), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['charge_point_id'], ['charge_points.id'], name=op.f('fk_command_logs_charge_point_id_charge_points'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_command_logs'))
    )
    op.create_table('rfid_cards',
    sa.Column('uid', sa.String(length=14), nullable=False),
    sa.Column('label', sa.String(length=80), nullable=True),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('tariff_id', sa.UUID(), nullable=True),
    sa.Column('synced_to_hardware', sa.Boolean(), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_rfid_cards_site_id_sites'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id'], name=op.f('fk_rfid_cards_tariff_id_tariffs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_rfid_cards_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_rfid_cards')),
    sa.UniqueConstraint('uid', name='uq_rfid_cards_uid')
    )
    op.create_index(op.f('ix_rfid_cards_uid'), 'rfid_cards', ['uid'], unique=False)
    op.create_table('vehicles',
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('model', sa.String(length=80), nullable=False),
    sa.Column('plate', sa.String(length=16), nullable=True),
    sa.Column('vin', sa.String(length=24), nullable=True),
    sa.Column('battery_kwh', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('max_ac_kw', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_vehicles_user_id_users'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_vehicles'))
    )
    op.create_index(op.f('ix_vehicles_plate'), 'vehicles', ['plate'], unique=False)
    op.create_index(op.f('ix_vehicles_vin'), 'vehicles', ['vin'], unique=False)
    op.create_table('reservations',
    sa.Column('code', sa.String(length=24), nullable=False),
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('charge_point_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('vehicle_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Enum('PENDING', 'CONFIRMED', 'CONSUMED', 'CANCELLED', 'EXPIRED', name='reservation_status', native_enum=False), nullable=False),
    sa.Column('starts_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('ends_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('target_kwh', sa.Numeric(precision=10, scale=3), nullable=True),
    sa.Column('reserved_kw', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('pushed_to_hardware', sa.Boolean(), nullable=False),
    sa.Column('cancelled_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['charge_point_id'], ['charge_points.id'], name=op.f('fk_reservations_charge_point_id_charge_points'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_reservations_site_id_sites'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_reservations_user_id_users'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], name=op.f('fk_reservations_vehicle_id_vehicles'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_reservations'))
    )
    op.create_index(op.f('ix_reservations_code'), 'reservations', ['code'], unique=True)
    op.create_index('ix_reservations_cp_window', 'reservations', ['charge_point_id', 'starts_at', 'ends_at'], unique=False)
    op.create_index(op.f('ix_reservations_status'), 'reservations', ['status'], unique=False)
    op.create_table('charging_sessions',
    sa.Column('code', sa.String(length=24), nullable=False),
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('charge_point_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('vehicle_id', sa.UUID(), nullable=True),
    sa.Column('rfid_card_id', sa.UUID(), nullable=True),
    sa.Column('tariff_id', sa.UUID(), nullable=True),
    sa.Column('reservation_id', sa.UUID(), nullable=True),
    sa.Column('state', sa.Enum('AUTHORIZING', 'STARTING', 'CHARGING', 'SUSPENDED', 'FINISHING', 'FINISHED', 'BILLED', 'ERROR', name='session_state', native_enum=False), nullable=False),
    sa.Column('auth_method', sa.Enum('RFID', 'APP', 'PLUG_AND_CHARGE', 'RESERVATION', 'OPERATOR', name='auth_method', native_enum=False), nullable=False),
    sa.Column('stop_reason', sa.Enum('LOCAL', 'REMOTE', 'EV_DISCONNECTED', 'ENERGY_LIMIT', 'TIME_LIMIT', 'AMOUNT_LIMIT', 'POWER_SHORTAGE', 'FAULT', 'DEAUTHORIZED', name='stop_reason', native_enum=False), nullable=True),
    sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('charging_stopped_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('energy_kwh', sa.Numeric(precision=10, scale=3), nullable=False),
    sa.Column('green_energy_kwh', sa.Numeric(precision=10, scale=3), nullable=False),
    sa.Column('duration_s', sa.Integer(), nullable=False),
    sa.Column('idle_minutes', sa.Integer(), nullable=False),
    sa.Column('peak_power_kw', sa.Numeric(precision=7, scale=3), nullable=False),
    sa.Column('meter_start_kwh', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('meter_stop_kwh', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('estimated_cost', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('preauth_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('limit_kwh', sa.Numeric(precision=10, scale=3), nullable=True),
    sa.Column('limit_minutes', sa.Integer(), nullable=True),
    sa.Column('limit_amount', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('error_message', sa.Text(), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['charge_point_id'], ['charge_points.id'], name=op.f('fk_charging_sessions_charge_point_id_charge_points'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['reservation_id'], ['reservations.id'], name=op.f('fk_charging_sessions_reservation_id_reservations'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['rfid_card_id'], ['rfid_cards.id'], name=op.f('fk_charging_sessions_rfid_card_id_rfid_cards'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_charging_sessions_site_id_sites'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tariff_id'], ['tariffs.id'], name=op.f('fk_charging_sessions_tariff_id_tariffs'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_charging_sessions_user_id_users'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], name=op.f('fk_charging_sessions_vehicle_id_vehicles'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_charging_sessions'))
    )
    op.create_index(op.f('ix_charging_sessions_code'), 'charging_sessions', ['code'], unique=True)
    op.create_index('ix_charging_sessions_cp_state', 'charging_sessions', ['charge_point_id', 'state'], unique=False)
    op.create_index('ix_charging_sessions_started_at', 'charging_sessions', ['started_at'], unique=False)
    op.create_index(op.f('ix_charging_sessions_state'), 'charging_sessions', ['state'], unique=False)
    op.create_table('invoices',
    sa.Column('code', sa.String(length=24), nullable=False),
    sa.Column('site_id', sa.UUID(), nullable=False),
    sa.Column('session_id', sa.UUID(), nullable=True),
    sa.Column('user_id', sa.UUID(), nullable=True),
    sa.Column('status', sa.Enum('DRAFT', 'OPEN', 'PAID', 'FAILED', 'REFUNDED', 'VOID', name='invoice_status', native_enum=False), nullable=False),
    sa.Column('currency', sa.String(length=3), nullable=False),
    sa.Column('subtotal', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('discount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('total', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('processing_fee', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('net_amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('issued_on', sa.Date(), nullable=False),
    sa.Column('due_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('paid_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('tariff_snapshot', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['charging_sessions.id'], name=op.f('fk_invoices_session_id_charging_sessions'), ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['site_id'], ['sites.id'], name=op.f('fk_invoices_site_id_sites'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_invoices_user_id_users'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoices')),
    sa.UniqueConstraint('session_id', name=op.f('uq_invoices_session_id'))
    )
    op.create_index(op.f('ix_invoices_code'), 'invoices', ['code'], unique=True)
    op.create_index(op.f('ix_invoices_status'), 'invoices', ['status'], unique=False)
    op.create_table('session_events',
    sa.Column('session_id', sa.UUID(), nullable=False),
    sa.Column('occurred_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('event_type', sa.String(length=48), nullable=False),
    sa.Column('from_state', sa.String(length=24), nullable=True),
    sa.Column('to_state', sa.String(length=24), nullable=True),
    sa.Column('message', sa.Text(), nullable=True),
    sa.Column('payload', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['session_id'], ['charging_sessions.id'], name=op.f('fk_session_events_session_id_charging_sessions'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_session_events'))
    )
    op.create_table('telemetry_samples',
    sa.Column('charge_point_id', sa.UUID(), nullable=False),
    sa.Column('session_id', sa.UUID(), nullable=True),
    sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
    sa.Column('voltage_a', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('voltage_b', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('voltage_c', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('current_a', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('current_b', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('current_c', sa.Numeric(precision=7, scale=2), nullable=True),
    sa.Column('power_kw', sa.Numeric(precision=7, scale=3), nullable=False),
    sa.Column('session_energy_kwh', sa.Numeric(precision=10, scale=3), nullable=False),
    sa.Column('meter_kwh', sa.Numeric(precision=12, scale=3), nullable=True),
    sa.Column('raw_status', sa.SmallInteger(), nullable=True),
    sa.Column('power_source_bits', sa.SmallInteger(), nullable=True),
    sa.Column('green_kwh', sa.Numeric(precision=10, scale=3), nullable=True),
    sa.Column('applied_limit_kw', sa.Numeric(precision=6, scale=2), nullable=True),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['charge_point_id'], ['charge_points.id'], name=op.f('fk_telemetry_samples_charge_point_id_charge_points'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['session_id'], ['charging_sessions.id'], name=op.f('fk_telemetry_samples_session_id_charging_sessions'), ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_telemetry_samples'))
    )
    op.create_table('invoice_lines',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('kind', sa.String(length=32), nullable=False),
    sa.Column('description', sa.String(length=200), nullable=False),
    sa.Column('quantity', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('unit', sa.String(length=12), nullable=False),
    sa.Column('unit_price', sa.Numeric(precision=12, scale=4), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_invoice_lines_invoice_id_invoices'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_invoice_lines'))
    )
    op.create_table('payments',
    sa.Column('invoice_id', sa.UUID(), nullable=False),
    sa.Column('method', sa.Enum('PIX', 'CREDIT_CARD', 'RFID_SUBSCRIPTION', 'WALLET', name='payment_method_kind', native_enum=False), nullable=False),
    sa.Column('status', sa.Enum('PENDING', 'AUTHORIZED', 'CAPTURED', 'FAILED', 'REFUNDED', name='payment_status', native_enum=False), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('provider', sa.String(length=40), nullable=False),
    sa.Column('provider_ref', sa.String(length=120), nullable=True),
    sa.Column('idempotency_key', sa.String(length=80), nullable=True),
    sa.Column('qr_code', sa.Text(), nullable=True),
    sa.Column('failure_reason', sa.Text(), nullable=True),
    sa.Column('authorized_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('captured_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('raw_response', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['invoice_id'], ['invoices.id'], name=op.f('fk_payments_invoice_id_invoices'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_payments'))
    )
    op.create_index(op.f('ix_payments_idempotency_key'), 'payments', ['idempotency_key'], unique=True)
    op.create_index(op.f('ix_payments_provider_ref'), 'payments', ['provider_ref'], unique=False)
    op.create_index(op.f('ix_payments_status'), 'payments', ['status'], unique=False)
    # FK circular: sites.default_tariff_id -> tariffs.id, criada agora que
    # ambas as tabelas existem.
    op.create_foreign_key(
        op.f("fk_sites_default_tariff_id_tariffs"),
        "sites",
        "tariffs",
        ["default_tariff_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for nome, tabela, coluna in BRIN_INDEXES:
        op.execute(f"CREATE INDEX IF NOT EXISTS {nome} ON {tabela} USING BRIN ({coluna})")

    # Consulta mais quente do detalhe de sessao: telemetria de um ponto no tempo.
    op.create_index(
        "ix_telemetry_samples_cp_time",
        "telemetry_samples",
        ["charge_point_id", "recorded_at"],
        unique=False,
    )
    op.create_index(
        "ix_session_events_session_time",
        "session_events",
        ["session_id", "occurred_at"],
        unique=False,
    )
    # Um ponto nao pode ter duas sessoes ativas - garantia no banco, nao so no
    # codigo, porque dois requests simultaneos passam pela mesma checagem.
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_active_session_per_charge_point
        ON charging_sessions (charge_point_id)
        WHERE state IN ('authorizing', 'starting', 'charging', 'suspended', 'finishing')
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_active_session_per_charge_point")
    op.drop_index("ix_session_events_session_time", table_name="session_events")
    op.drop_index("ix_telemetry_samples_cp_time", table_name="telemetry_samples")
    for nome, _tabela, _coluna in BRIN_INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {nome}")
    op.drop_constraint(
        op.f("fk_sites_default_tariff_id_tariffs"), "sites", type_="foreignkey"
    )

    op.drop_index(op.f('ix_payments_status'), table_name='payments')
    op.drop_index(op.f('ix_payments_provider_ref'), table_name='payments')
    op.drop_index(op.f('ix_payments_idempotency_key'), table_name='payments')
    op.drop_table('payments')
    op.drop_table('invoice_lines')
    op.drop_table('telemetry_samples')
    op.drop_table('session_events')
    op.drop_index(op.f('ix_invoices_status'), table_name='invoices')
    op.drop_index(op.f('ix_invoices_code'), table_name='invoices')
    op.drop_table('invoices')
    op.drop_index(op.f('ix_charging_sessions_state'), table_name='charging_sessions')
    op.drop_index('ix_charging_sessions_started_at', table_name='charging_sessions')
    op.drop_index('ix_charging_sessions_cp_state', table_name='charging_sessions')
    op.drop_index(op.f('ix_charging_sessions_code'), table_name='charging_sessions')
    op.drop_table('charging_sessions')
    op.drop_index(op.f('ix_reservations_status'), table_name='reservations')
    op.drop_index('ix_reservations_cp_window', table_name='reservations')
    op.drop_index(op.f('ix_reservations_code'), table_name='reservations')
    op.drop_table('reservations')
    op.drop_index(op.f('ix_vehicles_vin'), table_name='vehicles')
    op.drop_index(op.f('ix_vehicles_plate'), table_name='vehicles')
    op.drop_table('vehicles')
    op.drop_index(op.f('ix_rfid_cards_uid'), table_name='rfid_cards')
    op.drop_table('rfid_cards')
    op.drop_table('command_logs')
    op.drop_table('charge_point_connections')
    op.drop_table('audit_logs')
    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_table('users')
    op.drop_table('tariff_windows')
    op.drop_table('site_payment_methods')
    op.drop_table('site_meter_readings')
    op.drop_index(op.f('ix_charge_points_status'), table_name='charge_points')
    op.drop_index(op.f('ix_charge_points_serial_number'), table_name='charge_points')
    op.drop_table('charge_points')
    op.drop_table('tariffs')
    op.drop_table('sites')
    for nome, _inicio in SEQUENCIAS:
        op.execute(f"DROP SEQUENCE IF EXISTS {nome}")
