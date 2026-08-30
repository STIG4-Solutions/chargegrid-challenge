"""Reconcilia bancos criados antes por Base.metadata.create_all.

Ate a correcao do seed, `python -m app.seed` montava o schema pelos MODELOS.
Nem tudo mora neles: os BRIN das series temporais e os indices compostos vivem
so nas migrations. Um banco assim ficava com sete indices a menos - e, como as
0001 a 0004 constam como aplicadas nele, nunca seriam criados.

Toda instrucao aqui e' IF NOT EXISTS: num banco que veio pelas migrations, esta
revisao nao faz nada. Ela existe para os que ja estao tortos.

Revision ID: 0008_reconcilia_indices
Revises: 0007_indices_de_sessao_ativa
Create Date: 2026-08-30
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_reconcilia_indices"
down_revision: str | None = "0007_indices_de_sessao_ativa"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

BRIN = [
    ("ix_telemetry_samples_recorded_at_brin", "telemetry_samples", "recorded_at"),
    ("ix_site_meter_readings_recorded_at_brin", "site_meter_readings", "recorded_at"),
    ("ix_command_logs_sent_at_brin", "command_logs", "sent_at"),
    ("ix_audit_logs_occurred_at_brin", "audit_logs", "occurred_at"),
]

COMPOSTOS = [
    ("ix_telemetry_samples_cp_time", "telemetry_samples", "charge_point_id, recorded_at"),
    ("ix_session_events_session_time", "session_events", "session_id, occurred_at"),
]


def upgrade() -> None:
    for nome, tabela, coluna in BRIN:
        op.execute(f"CREATE INDEX IF NOT EXISTS {nome} ON {tabela} USING BRIN ({coluna})")

    for nome, tabela, colunas in COMPOSTOS:
        op.execute(f"CREATE INDEX IF NOT EXISTS {nome} ON {tabela} ({colunas})")

    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_charging_sessions_queue
        ON charging_sessions (site_id, queued_at)
        WHERE state = 'QUEUED'
        """
    )


def downgrade() -> None:
    # Nao remove nada: os indices pertencem as revisoes que os criaram, e o
    # papel desta e' so preencher o que faltou. Desfaze-la nao deve tirar de um
    # banco correto o que ele sempre teve.
    pass
