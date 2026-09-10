"""Site = estabelecimento comercial (shopping, varejo, estacionamento)."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class Site(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "sites"
    # O indice fica declarado aqui, e nao so' na migration: o que existe apenas
    # na migration some de um banco criado por `create_all`, e `alembic check`
    # nao percebe - ele compara modelos com migrations, e nao haveria o que
    # comparar. O nome e' escrito a mao para casar com o da 0014; deixar a
    # convencao nomear produziria `ix_sites_slug`, e seriam dois indices.
    __table_args__ = (Index("uq_sites_slug", "slug", unique=True),)

    name: Mapped[str] = mapped_column(String(160), nullable=False)
    # Identificador estavel entre reconstrucoes do banco. O `id` e' sorteado a
    # cada reseed; o modelo de previsao guarda dentro do artefato a lista de
    # locais que conhece, e cai em fallback silencioso quando ela nao bate.
    slug: Mapped[str] = mapped_column(String(40), nullable=False)
    address: Mapped[str | None] = mapped_column(Text)
    city: Mapped[str | None] = mapped_column(String(80))
    state: Mapped[str | None] = mapped_column(String(2))
    latitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[float | None] = mapped_column(Numeric(9, 6))
    timezone: Mapped[str] = mapped_column(String(64), default="America/Sao_Paulo", nullable=False)

    # ---- Orçamento de potência (base do Controle de Demanda) ----
    grid_limit_kw: Mapped[float] = mapped_column(
        Numeric(8, 2), default=0, nullable=False, doc="Capacidade contratada do ponto de entrega"
    )
    reserved_kw: Mapped[float] = mapped_column(
        Numeric(8, 2), default=0, nullable=False, doc="Reserva para cargas não-EV do prédio"
    )
    # Corrente do disjuntor de entrada — espelha o registrador 10026 do HCA G2.
    main_breaker_current_a: Mapped[float | None] = mapped_column(Numeric(8, 2))

    # Habilita PV/bateria no cálculo do orçamento (o HCA G2 aceita modos PV / PV+BAT).
    allow_pv_kw: Mapped[bool] = mapped_column(default=True, nullable=False)
    allow_battery_kw: Mapped[bool] = mapped_column(default=True, nullable=False)
    battery_min_soc: Mapped[float] = mapped_column(Numeric(5, 2), default=20, nullable=False)

    # Contrato de demanda com a distribuidora (Grupo A).
    #
    # `grid_limit_kw` e' o teto que o rateio respeita momento a momento;
    # `contracted_demand_kw` e' o que esta no contrato e vira conta no fim do
    # mes. Costumam ser iguais, mas nao precisam: da' para operar com folga
    # abaixo do contratado. Nulo cai no grid_limit_kw.
    contracted_demand_kw: Mapped[float | None] = mapped_column(Numeric(8, 2))
    demand_tariff_brl_per_kw: Mapped[float] = mapped_column(
        Numeric(10, 2), default=0, nullable=False, doc="R$/kW de demanda contratada"
    )

    default_tariff_id: Mapped[uuid.UUID | None] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("tariffs.id", ondelete="SET NULL")
    )

    users = relationship("User", back_populates="site")
    charge_points = relationship("ChargePoint", back_populates="site", cascade="all, delete-orphan")
    tariffs = relationship(
        "Tariff", back_populates="site", foreign_keys="Tariff.site_id", cascade="all, delete-orphan"
    )


class SiteMeterReading(UUIDMixin, Base):
    """Leitura do smart meter do site — insumo do controle dinâmico de carga.

    Série temporal: índice BRIN em (site_id, recorded_at) é criado na migration.
    """

    __tablename__ = "site_meter_readings"

    site_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True), ForeignKey("sites.id", ondelete="CASCADE"), nullable=False
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    grid_import_kw: Mapped[float] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    pv_kw: Mapped[float] = mapped_column(Numeric(8, 2), default=0, nullable=False)
    battery_kw: Mapped[float] = mapped_column(
        Numeric(8, 2), default=0, nullable=False, doc="positivo = descarregando"
    )
    battery_soc: Mapped[float | None] = mapped_column(Numeric(5, 2))
    building_load_kw: Mapped[float] = mapped_column(
        Numeric(8, 2), default=0, nullable=False, doc="consumo não-EV do prédio"
    )
    ev_load_kw: Mapped[float] = mapped_column(Numeric(8, 2), default=0, nullable=False)
