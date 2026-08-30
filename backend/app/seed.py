"""Carga inicial de dados.

Reproduz o cenario que o front ja usa em src/data/mockData.js (mesmos codigos de
ponto, tarifas e perfis), para trocar o mock pela API sem reescrever as telas.

    python -m app.seed
"""

from __future__ import annotations

import asyncio
import secrets
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.billing import Invoice, InvoiceLine, SitePaymentMethod
from app.models.charge_point import ChargePoint, ChargePointConnection
from app.models.enums import (
    AuthMethod,
    ChargePointStatus,
    ConnectorType,
    InvoiceStatus,
    PaymentMethodKind,
    PhaseType,
    SessionState,
    StopReason,
    TariffType,
    UserRole,
)
from app.models.session import ChargingSession
from app.models.site import Site, SiteMeterReading
from app.models.tariff import ALL_DAYS, WEEKDAYS, WEEKEND, Tariff, TariffWindow
from app.models.user import RfidCard, User, Vehicle

log = get_logger(__name__)

CHARGE_POINTS = [
    # code, nome, conector, kW nominal, fases, prioridade
    ("CP-01", "Ponto de Recarga 01", ConnectorType.CCS2, 22.0, PhaseType.THREE, 200),
    ("CP-02", "Ponto de Recarga 02", ConnectorType.TYPE2, 22.0, PhaseType.THREE, 100),
    ("CP-03", "Ponto de Recarga 03", ConnectorType.CHADEMO, 11.0, PhaseType.THREE, 100),
    ("CP-04", "Ponto de Recarga 04", ConnectorType.TYPE2, 7.0, PhaseType.SINGLE, 50),
]

def _senha(configurada: str | None, rotulo: str, sorteadas: dict[str, str]) -> str:
    """Senha do seed: a do ambiente, ou uma sorteada e anunciada uma unica vez.

    Nao ha valor embutido de proposito. Uma senha escrita no repositorio vale
    para toda instalacao que o clonar, e este seed cria contas de admin.
    """
    if configurada:
        return configurada
    gerada = secrets.token_urlsafe(12)
    sorteadas[rotulo] = gerada
    return gerada


DRIVERS = [
    ("joao.silva@email.com", "Joao Silva", "Nissan Leaf", "40 kWh", 40.0, 6.6),
    ("maria.souza@email.com", "Maria Souza", "BYD Dolphin", "44 kWh", 44.9, 11.0),
    ("carlos.lima@email.com", "Carlos Lima", "VW ID.4", "77 kWh", 77.0, 11.0),
    ("ana.costa@email.com", "Ana Costa", "Tesla Model 3", "60 kWh", 57.5, 11.0),
    ("pedro.alves@email.com", "Pedro Alves", "GWM Ora 03", "48 kWh", 48.0, 6.6),
]


async def seed() -> None:
    async with SessionLocal() as db:
        if (await db.execute(select(Site).limit(1))).scalar_one_or_none() is not None:
            log.info("seed.skipped", reason="ja existem dados")
            return

        site = Site(
            name="LAB FIAP Eco Station",
            address="Av. Lins de Vasconcelos, 1264 - Aclimacao, Sao Paulo",
            city="Sao Paulo",
            state="SP",
            latitude=-23.568500,
            longitude=-46.632200,
            grid_limit_kw=75.0,
            reserved_kw=20.0,
            main_breaker_current_a=150.0,
            allow_pv_kw=True,
            allow_battery_kw=True,
            battery_min_soc=20.0,
        )
        db.add(site)
        await db.flush()

        # ---- tarifas: ponta / fora de ponta / por tempo ----
        peak = Tariff(
            site_id=site.id,
            name="Tarifa Ponta",
            type=TariffType.TIME_OF_USE,
            # Preco base = fora de ponta: e o fallback caso algum instante
            # escape das janelas, e cobrar ponta por engano penaliza o cliente.
            price_per_kwh=1.40,
            idle_fee_per_min=0.20,
            free_minutes=5,
            min_charge=5.00,
        )
        peak.windows.append(
            TariffWindow(
                label="Ponta",
                day_mask=WEEKDAYS,
                starts_at=time(18, 0),
                ends_at=time(21, 0),
                price_per_kwh=1.50,
                idle_fee_per_min=0.20,
            )
        )
        peak.windows.append(
            TariffWindow(
                label="Fora de ponta",
                day_mask=ALL_DAYS,
                starts_at=time(21, 0),
                ends_at=time(18, 0),
                price_per_kwh=1.40,
                idle_fee_per_min=0.10,
            )
        )
        # A janela de ponta so vale em dia util, entao o intervalo 18h-21h do
        # fim de semana ficaria descoberto e cairia no preco base.
        peak.windows.append(
            TariffWindow(
                label="Fora de ponta",
                day_mask=WEEKEND,
                starts_at=time(18, 0),
                ends_at=time(21, 0),
                price_per_kwh=1.40,
                idle_fee_per_min=0.10,
            )
        )

        off_peak = Tariff(
            site_id=site.id,
            name="Tarifa Fora de Ponta",
            type=TariffType.PER_KWH,
            price_per_kwh=1.40,
            idle_fee_per_min=0.10,
            free_minutes=5,
        )
        by_time = Tariff(
            site_id=site.id,
            name="Sessão por Tempo",
            type=TariffType.PER_TIME,
            price_per_min=0.35,
            active=False,
        )
        db.add_all([peak, off_peak, by_time])
        await db.flush()
        site.default_tariff_id = peak.id

        # ---- pontos de recarga ----
        for code, name, connector, rated, phase, priority in CHARGE_POINTS:
            cp = ChargePoint(
                site_id=site.id,
                code=code,
                name=name,
                connector=connector,
                phase_type=phase,
                rated_kw=rated,
                # Piso do reg 10029: 1,4 kW monofasico / 4,2 kW trifasico.
                min_kw=1.4 if phase == PhaseType.SINGLE else 4.2,
                limit_kw=rated,
                priority=priority,
                status=ChargePointStatus.OFFLINE,
            )
            cp.connection = ChargePointConnection(
                protocol="modbus_tcp", host=None, port=502, unit_id=1
            )
            db.add(cp)

        # ---- metodos de pagamento (taxas tipicas do mercado brasileiro) ----
        db.add_all(
            [
                SitePaymentMethod(
                    site_id=site.id, kind=PaymentMethodKind.PIX, label="Pix", fee_percent=0.0
                ),
                SitePaymentMethod(
                    site_id=site.id,
                    kind=PaymentMethodKind.CREDIT_CARD,
                    label="Cartao de credito",
                    fee_percent=3.2,
                    fee_fixed=0.39,
                ),
                SitePaymentMethod(
                    site_id=site.id,
                    kind=PaymentMethodKind.RFID_SUBSCRIPTION,
                    label="Cartao RFID / assinatura",
                    fee_percent=0.0,
                ),
                SitePaymentMethod(
                    site_id=site.id,
                    kind=PaymentMethodKind.WALLET,
                    label="Carteira digital (app)",
                    fee_percent=1.0,
                    enabled=False,
                ),
            ]
        )

        # ---- usuarios ----
        cfg = get_settings()
        sorteadas: dict[str, str] = {}
        senha_admin = _senha(cfg.seed_admin_password, "admin@chargegrid.com.br", sorteadas)
        senha_operador = _senha(cfg.seed_operator_password, "operador@chargegrid.com.br", sorteadas)
        senha_motorista = _senha(cfg.seed_driver_password, "motoristas", sorteadas)

        db.add(
            User(
                email="admin@chargegrid.com.br",
                full_name="Administrador ChargeGrid",
                hashed_password=hash_password(senha_admin),
                role=UserRole.ADMIN,
                site_id=site.id,
            )
        )
        db.add(
            User(
                email="operador@chargegrid.com.br",
                full_name="Operador do Site",
                hashed_password=hash_password(senha_operador),
                role=UserRole.OPERATOR,
                site_id=site.id,
            )
        )

        for index, (email, full_name, model, _label, battery, max_ac) in enumerate(DRIVERS):
            driver = User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(senha_motorista),
                role=UserRole.DRIVER,
                wallet_balance=100.0,
            )
            db.add(driver)
            await db.flush()
            db.add(Vehicle(user_id=driver.id, model=model, battery_kwh=battery, max_ac_kw=max_ac))
            # Dois cartoes RFID por ponto e o limite pratico do HCA G2 (10 no total).
            if index < 2:
                db.add(
                    RfidCard(
                        uid=f"04A1B2C3D4E{index:03d}"[:14],
                        label=f"Cartao {full_name.split()[0]}",
                        user_id=driver.id,
                        site_id=site.id,
                        tariff_id=off_peak.id,
                    )
                )

        # ---- historico de recargas dos motoristas ----
        #
        # Sem isto o app do motorista abre com "Historico" e "Faturas" vazios, e
        # nao ha o que demonstrar. Sao sessoes ja encerradas e faturadas, dos
        # ultimos dias, com as linhas de fatura abertas por tipo - o mesmo
        # formato que o motor de tarifacao produz em operacao.
        agora = datetime.now(UTC)
        motoristas = (
            await db.execute(select(User).where(User.role == UserRole.DRIVER))
        ).scalars().all()
        veiculos = {
            v.user_id: v for v in (await db.execute(select(Vehicle))).scalars().all()
        }
        pontos_criados = (
            await db.execute(select(ChargePoint).order_by(ChargePoint.code))
        ).scalars().all()

        # Precos das janelas consultados de uma vez. Acessar tarifa.windows aqui
        # dispararia carregamento preguicoso dentro de contexto assincrono, e o
        # SQLAlchemy levanta MissingGreenlet.
        janelas = (await db.execute(select(TariffWindow))).scalars().all()
        preco_da_janela: dict[uuid.UUID, float] = {}
        for janela in janelas:
            preco_da_janela.setdefault(janela.tariff_id, float(janela.price_per_kwh))

        codigo_sessao = 1000
        codigo_fatura = 2000
        # (dias atras, hora local de inicio, kWh, minutos, ocioso, pago)
        HISTORICO = [
            (1, 19, 24.6, 78, 0, True),
            (2, 9, 11.2, 41, 0, True),
            (3, 14, 33.1, 96, 12, True),
            (5, 20, 8.4, 27, 0, False),
            (8, 11, 41.9, 132, 0, True),
        ]

        for indice, motorista in enumerate(motoristas[:3]):
            for passo, (dias, hora, kwh, minutos, ocioso, pago) in enumerate(HISTORICO):
                ponto = pontos_criados[(indice + passo) % len(pontos_criados)]
                # Janela de ponta local (18h-21h) usa a tarifa de horario.
                tarifa = peak if 18 <= hora < 21 else off_peak
                preco = preco_da_janela.get(tarifa.id, float(tarifa.price_per_kwh))

                inicio = agora - timedelta(days=dias)
                inicio = inicio.replace(hour=hora % 24, minute=0, second=0, microsecond=0)
                fim = inicio + timedelta(minutes=minutos)

                codigo_sessao += 1
                sessao = ChargingSession(
                    code=f"SES-{codigo_sessao}",
                    site_id=site.id,
                    charge_point_id=ponto.id,
                    user_id=motorista.id,
                    vehicle_id=(
                        veiculos[motorista.id].id if motorista.id in veiculos else None
                    ),
                    tariff_id=tarifa.id,
                    state=SessionState.BILLED,
                    auth_method=AuthMethod.APP,
                    stop_reason=StopReason.EV_DISCONNECTED,
                    authorized_at=inicio - timedelta(minutes=1),
                    started_at=inicio,
                    ended_at=fim,
                    charging_stopped_at=fim,
                    energy_kwh=kwh,
                    green_energy_kwh=round(kwh * 0.31, 3),
                    duration_s=minutos * 60,
                    idle_minutes=ocioso,
                    peak_power_kw=min(float(ponto.rated_kw), round(kwh / (minutos / 60), 1)),
                    estimated_cost=0,
                )
                db.add(sessao)
                await db.flush()

                energia = round(kwh * preco, 2)
                taxa_ociosa = round(ocioso * float(tarifa.idle_fee_per_min), 2)
                subtotal = round(energia + taxa_ociosa, 2)
                total = max(subtotal, float(tarifa.min_charge))
                sessao.estimated_cost = total

                codigo_fatura += 1
                fatura = Invoice(
                    code=f"INV-{codigo_fatura}",
                    site_id=site.id,
                    session_id=sessao.id,
                    user_id=motorista.id,
                    status=InvoiceStatus.PAID if pago else InvoiceStatus.OPEN,
                    subtotal=subtotal,
                    total=total,
                    processing_fee=round(total * 0.032 + 0.39, 2) if pago else 0,
                    net_amount=round(total - (total * 0.032 + 0.39), 2) if pago else total,
                    issued_on=fim.date(),
                    paid_at=fim + timedelta(minutes=2) if pago else None,
                    tariff_snapshot={"name": tarifa.name, "type": str(tarifa.type)},
                )
                db.add(fatura)
                await db.flush()

                linhas = [
                    InvoiceLine(
                        invoice_id=fatura.id, position=0, kind="energy",
                        description=f"Energia — {tarifa.name}", quantity=kwh,
                        unit="kWh", unit_price=preco, amount=energia,
                    )
                ]
                if taxa_ociosa > 0:
                    linhas.append(
                        InvoiceLine(
                            invoice_id=fatura.id, position=1, kind="idle",
                            description="Taxa de ociosidade", quantity=ocioso,
                            unit="min", unit_price=float(tarifa.idle_fee_per_min),
                            amount=taxa_ociosa,
                        )
                    )
                if total > subtotal:
                    linhas.append(
                        InvoiceLine(
                            invoice_id=fatura.id, position=len(linhas), kind="min_charge",
                            description="Complemento até o valor mínimo", quantity=1,
                            unit="un", unit_price=round(total - subtotal, 2),
                            amount=round(total - subtotal, 2),
                        )
                    )
                for linha in linhas:
                    db.add(linha)

        # ---- leitura inicial do medidor: sem ela o orcamento so ve a rede ----
        now = datetime.now(UTC)
        for minutes_ago in (10, 5, 0):
            db.add(
                SiteMeterReading(
                    site_id=site.id,
                    recorded_at=now - timedelta(minutes=minutes_ago),
                    grid_import_kw=32.0,
                    pv_kw=38.4,
                    battery_kw=12.0,
                    battery_soc=68.0,
                    building_load_kw=18.5,
                    ev_load_kw=0.0,
                )
            )

        await db.commit()
        log.info("seed.done", site=site.name, charge_points=len(CHARGE_POINTS))

        # Unica chance de ver as senhas sorteadas: elas nao ficam gravadas em
        # lugar nenhum em texto claro. Quem quiser senhas estaveis define
        # SEED_ADMIN_PASSWORD, SEED_OPERATOR_PASSWORD e SEED_DRIVER_PASSWORD.
        if sorteadas:
            log.warning("seed.senhas_sorteadas", contas=list(sorteadas))
            print()
            print("  Senhas sorteadas para este banco (anote agora):")
            for rotulo, senha in sorteadas.items():
                print(f"    {rotulo:32} {senha}")
            print("    Defina SEED_*_PASSWORD no .env para escolher as suas.")
            print()


async def create_schema() -> None:
    """Constroi o schema pelas migrations, nunca por Base.metadata.create_all.

    O create_all monta o schema a partir dos MODELOS, e nem tudo mora neles: os
    indices BRIN das tabelas de serie temporal, os indices compostos e os
    indices unicos parciais que impedem duas sessoes ativas no mesmo ponto
    existem so nas migrations. Um banco criado por create_all ficava com oito
    indices a menos que producao - entre eles a unica garantia de unicidade -,
    e `alembic check` nao acusava, porque ele compara modelos com migrations e
    esses indices nao estao nos modelos.

    O docker-compose ja rodava `alembic upgrade head` antes deste script; quem
    executasse `python -m app.seed` direto e' que acabava com o schema torto.
    Agora as duas rotas produzem o mesmo banco.
    """
    from alembic.config import Config

    from alembic import command

    raiz = Path(__file__).resolve().parent.parent
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "alembic"))
    # Numa thread propria: o env.py chama asyncio.run(), que recusa rodar dentro
    # de um laco de eventos ja em execucao - e este script abriu o dele.
    await asyncio.to_thread(command.upgrade, cfg, "head")


async def main() -> None:
    configure_logging()
    await create_schema()
    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
