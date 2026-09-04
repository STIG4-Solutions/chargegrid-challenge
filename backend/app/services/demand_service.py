"""Previsao de estouro de demanda e custo evitado.

Por que isto existe, e por que em kW e nao em kWh:

No Grupo A a conta de luz tem duas partes. A energia (kWh) e' o que se consome;
a DEMANDA (kW) e' o quanto se puxa no pico, e ela e' contratada. A distribuidora
mede a media de 15 minutos, pega a MAIOR do mes e compara com o contrato. Passar
disso e' ultrapassagem, e a penalidade nao e' proporcional - o excedente e'
cobrado ao dobro da tarifa.

Um pico de quinze minutos, uma vez no mes, e' o que define a conta. Por isso
avisar ANTES vale mais que relatar depois: depois de medido, ja foi.

E' tambem o que torna o rateio defensavel em reais. Sem esta conta o controle de
demanda e' uma promessa; com ela, e' um numero.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from statistics import median
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charge_point import ChargePoint
from app.models.enums import ACTIVE_SESSION_STATES
from app.models.session import ChargingSession
from app.models.site import Site, SiteMeterReading

# A distribuidora integra a demanda em janelas de 15 minutos. Usar outro passo
# aqui daria um numero que nao corresponde ao que vai ser faturado.
JANELA_MIN = 15

# Tolerancia regulatoria antes de caracterizar ultrapassagem, e o multiplicador
# aplicado ao excedente (REN 1.000/2021). Sao da norma, nao escolha nossa.
TOLERANCIA = 0.05
MULTIPLICADOR_ULTRAPASSAGEM = 2.0


@dataclass
class FatiaPrevista:
    inicio: datetime
    demanda_prevista_kw: float
    predio_kw: float
    solar_kw: float
    bateria_kw: float
    ev_kw: float
    excede: bool

    def as_dict(self) -> dict:
        return {
            "inicio": self.inicio.isoformat(),
            "demanda_prevista_kw": round(self.demanda_prevista_kw, 2),
            "predio_kw": round(self.predio_kw, 2),
            "solar_kw": round(self.solar_kw, 2),
            "bateria_kw": round(self.bateria_kw, 2),
            "ev_kw": round(self.ev_kw, 2),
            "excede": self.excede,
        }


@dataclass
class Previsao:
    contratada_kw: float
    teto_com_tolerancia_kw: float
    ev_atual_kw: float
    fatias: list[FatiaPrevista] = field(default_factory=list)
    dias_de_historico: int = 0

    @property
    def primeira_excedente(self) -> FatiaPrevista | None:
        return next((f for f in self.fatias if f.excede), None)

    @property
    def pico_previsto_kw(self) -> float:
        return max((f.demanda_prevista_kw for f in self.fatias), default=0.0)

    def as_dict(self) -> dict:
        alerta = self.primeira_excedente
        return {
            "contratada_kw": round(self.contratada_kw, 2),
            "teto_com_tolerancia_kw": round(self.teto_com_tolerancia_kw, 2),
            "ev_atual_kw": round(self.ev_atual_kw, 2),
            "pico_previsto_kw": round(self.pico_previsto_kw, 2),
            "dias_de_historico": self.dias_de_historico,
            "risco": alerta is not None,
            "primeiro_estouro_em": alerta.inicio.isoformat() if alerta else None,
            "margem_kw": round(self.teto_com_tolerancia_kw - self.pico_previsto_kw, 2),
            "fatias": [f.as_dict() for f in self.fatias],
        }


def _fatia_do_dia(momento: datetime, fuso: ZoneInfo) -> int:
    """Indice da janela de 15 min dentro do dia local (0..95)."""
    local = momento.astimezone(fuso)
    return (local.hour * 60 + local.minute) // JANELA_MIN


async def _perfil_por_fatia(
    db: AsyncSession, site_id: uuid.UUID, fuso: ZoneInfo, dias: int
) -> tuple[dict[int, tuple[float, float, float]], int]:
    """Perfil tipico de predio, solar e bateria por janela do dia.

    Mediana, nao media: um dia atipico - feriado, manutencao, um pico isolado -
    desloca a media e nao desloca a mediana. Previsao de demanda que se assusta
    com outlier vira alarme que o operador aprende a ignorar.
    """
    desde = datetime.now(UTC) - timedelta(days=dias)
    leituras = (
        (
            await db.execute(
                select(SiteMeterReading)
                .where(
                    SiteMeterReading.site_id == site_id,
                    SiteMeterReading.recorded_at >= desde,
                )
                .order_by(SiteMeterReading.recorded_at)
            )
        )
        .scalars()
        .all()
    )

    baldes: dict[int, list[tuple[float, float, float]]] = {}
    dias_vistos: set = set()
    for leitura in leituras:
        fatia = _fatia_do_dia(leitura.recorded_at, fuso)
        baldes.setdefault(fatia, []).append(
            (
                float(leitura.building_load_kw),
                float(leitura.pv_kw),
                float(leitura.battery_kw),
            )
        )
        dias_vistos.add(leitura.recorded_at.astimezone(fuso).date())

    perfil = {
        fatia: (
            median([v[0] for v in vs]),
            median([v[1] for v in vs]),
            median([v[2] for v in vs]),
        )
        for fatia, vs in baldes.items()
    }
    return perfil, len(dias_vistos)


async def prever_demanda(
    db: AsyncSession, site: Site, *, horizonte_horas: int = 6, dias_de_historico: int = 7
) -> Previsao:
    """Projeta a demanda das proximas horas e diz se ela estoura o contrato.

    A carga dos eletropostos e' mantida no valor de agora, de proposito. Nao e'
    previsao de quantos carros vao chegar - e' a resposta a uma pergunta
    concreta: "com o que esta carregando neste momento, eu estouro?". Projetar
    chegadas exigiria um modelo que nao temos como validar, e erraria justamente
    no caso que importa.

    O que varia na projecao e' o resto: o predio segue seu perfil de dia util e
    o solar cai a tarde. E' essa queda que causa o estouro tipico - a carga
    continua e a geracao que a sustentava vai embora.
    """
    fuso = ZoneInfo(site.timezone or "America/Sao_Paulo")
    perfil, dias = await _perfil_por_fatia(db, site.id, fuso, dias_de_historico)

    contratada = float(site.contracted_demand_kw or site.grid_limit_kw)
    teto = contratada * (1 + TOLERANCIA)

    # Carga EV agora: soma do que os pontos com sessao ativa estao puxando.
    ev_atual = (
        (
            await db.execute(
                select(ChargePoint.current_kw)
                .join(
                    ChargingSession,
                    (ChargingSession.charge_point_id == ChargePoint.id)
                    & ChargingSession.state.in_(ACTIVE_SESSION_STATES),
                )
                .where(ChargePoint.site_id == site.id)
            )
        )
        .scalars()
        .all()
    )
    ev_kw = float(sum(float(v) for v in ev_atual))

    agora = datetime.now(UTC)
    passo = timedelta(minutes=JANELA_MIN)
    # Alinha ao inicio da janela corrente: e' assim que a distribuidora integra.
    inicio = agora - timedelta(
        minutes=agora.minute % JANELA_MIN, seconds=agora.second, microseconds=agora.microsecond
    )

    fatias: list[FatiaPrevista] = []
    for n in range(int(horizonte_horas * 60 / JANELA_MIN)):
        momento = inicio + passo * n
        predio, solar, bateria = perfil.get(_fatia_do_dia(momento, fuso), (0.0, 0.0, 0.0))
        if not site.allow_pv_kw:
            solar = 0.0
        if not site.allow_battery_kw:
            bateria = 0.0

        # O que sai da rede e' o que o predio e os carros pedem, menos o que
        # solar e bateria entregam. Nunca negativo: injecao na rede nao reduz
        # demanda contratada.
        demanda = max(0.0, predio + ev_kw - solar - bateria)
        fatias.append(
            FatiaPrevista(
                inicio=momento,
                demanda_prevista_kw=demanda,
                predio_kw=predio,
                solar_kw=solar,
                bateria_kw=bateria,
                ev_kw=ev_kw,
                excede=demanda > teto,
            )
        )

    return Previsao(
        contratada_kw=contratada,
        teto_com_tolerancia_kw=teto,
        ev_atual_kw=ev_kw,
        fatias=fatias,
        dias_de_historico=dias,
    )


@dataclass
class CustoEvitado:
    desde: datetime
    ate: datetime
    contratada_kw: float
    tarifa_brl_por_kw: float
    pico_real_kw: float
    pico_sem_rateio_kw: float
    ultrapassagem_real_kw: float
    ultrapassagem_sem_rateio_kw: float
    custo_real_brl: float
    custo_sem_rateio_brl: float
    janelas_analisadas: int
    momento_do_pico: datetime | None = None

    @property
    def evitado_brl(self) -> float:
        return max(0.0, self.custo_sem_rateio_brl - self.custo_real_brl)

    def as_dict(self) -> dict:
        return {
            "desde": self.desde.isoformat(),
            "ate": self.ate.isoformat(),
            "contratada_kw": round(self.contratada_kw, 2),
            "tarifa_brl_por_kw": round(self.tarifa_brl_por_kw, 2),
            "pico_real_kw": round(self.pico_real_kw, 2),
            "pico_sem_rateio_kw": round(self.pico_sem_rateio_kw, 2),
            "ultrapassagem_real_kw": round(self.ultrapassagem_real_kw, 2),
            "ultrapassagem_sem_rateio_kw": round(self.ultrapassagem_sem_rateio_kw, 2),
            "custo_real_brl": round(self.custo_real_brl, 2),
            "custo_sem_rateio_brl": round(self.custo_sem_rateio_brl, 2),
            "evitado_brl": round(self.evitado_brl, 2),
            "janelas_analisadas": self.janelas_analisadas,
            "momento_do_pico": self.momento_do_pico.isoformat() if self.momento_do_pico else None,
            "tarifa_configurada": self.tarifa_brl_por_kw > 0,
        }


def _ultrapassagem(pico_kw: float, contratada_kw: float) -> float:
    """kW faturados como ultrapassagem, ja descontada a tolerancia."""
    return max(0.0, pico_kw - contratada_kw * (1 + TOLERANCIA))


async def custo_evitado(
    db: AsyncSession, site: Site, *, dias: int = 30
) -> CustoEvitado:
    """Quanto o rateio poupou de ultrapassagem no periodo.

    A conta compara dois mundos sobre o MESMO historico:

      real       - o que o medidor registrou, com o rateio agindo
      sem rateio - o que teria sido se cada ponto com sessao ativa tivesse
                   puxado a potencia nominal dele, sem teto nenhum

    O contrafactual e' conservador de proposito. Ele nao supoe mais carros do
    que houve, nem sessoes mais longas: pega exatamente as sessoes que
    existiram e devolve a cada uma a potencia que o ponto entrega sem limite.
    E' o que aconteceria com um eletroposto comum, sem controle de demanda -
    que e' a lacuna que o desafio aponta.

    Demanda e' pico, nao soma: o numero que vira conta e' a MAIOR janela de 15
    minutos do periodo. Uma tarde de estouro custa o mes inteiro.
    """
    fuso = ZoneInfo(site.timezone or "America/Sao_Paulo")
    ate = datetime.now(UTC)
    desde = ate - timedelta(days=dias)

    contratada = float(site.contracted_demand_kw or site.grid_limit_kw)
    tarifa = float(site.demand_tariff_brl_per_kw)

    leituras = (
        (
            await db.execute(
                select(SiteMeterReading)
                .where(
                    SiteMeterReading.site_id == site.id,
                    SiteMeterReading.recorded_at >= desde,
                )
                .order_by(SiteMeterReading.recorded_at)
            )
        )
        .scalars()
        .all()
    )

    # Potencia nominal por ponto, para o contrafactual.
    pontos = (
        (await db.execute(select(ChargePoint).where(ChargePoint.site_id == site.id)))
        .scalars()
        .all()
    )
    nominal_por_ponto = {p.id: float(p.rated_kw) for p in pontos}

    # Sessoes do periodo, para saber quantos pontos estavam ocupados em cada
    # janela. Sem isso o contrafactual suporia o parque inteiro ligado o tempo
    # todo, o que inflaria o numero e o tornaria indefensavel.
    sessoes = (
        (
            await db.execute(
                select(ChargingSession).where(
                    ChargingSession.site_id == site.id,
                    ChargingSession.started_at.isnot(None),
                    ChargingSession.started_at <= ate,
                )
            )
        )
        .scalars()
        .all()
    )

    janelas: dict[datetime, list[SiteMeterReading]] = {}
    for leitura in leituras:
        marca = leitura.recorded_at.replace(
            minute=(leitura.recorded_at.minute // JANELA_MIN) * JANELA_MIN,
            second=0,
            microsecond=0,
        )
        janelas.setdefault(marca, []).append(leitura)

    pico_real = 0.0
    pico_sem = 0.0
    momento_pico = None

    for marca, amostras in sorted(janelas.items()):
        fim = marca + timedelta(minutes=JANELA_MIN)

        # Demanda faturada e' a MEDIA da janela, nao o instante de pico.
        real = sum(float(a.grid_import_kw) for a in amostras) / len(amostras)
        predio = sum(float(a.building_load_kw) for a in amostras) / len(amostras)
        solar = sum(float(a.pv_kw) for a in amostras) / len(amostras)
        bateria = sum(float(a.battery_kw) for a in amostras) / len(amostras)

        ocupados = {
            s.charge_point_id
            for s in sessoes
            if s.started_at
            and s.started_at < fim
            and (s.ended_at is None or s.ended_at > marca)
        }
        ev_sem_rateio = sum(nominal_por_ponto.get(cp, 0.0) for cp in ocupados)
        sem_rateio = max(0.0, predio + ev_sem_rateio - solar - bateria)

        if real > pico_real:
            pico_real = real
            momento_pico = marca.astimezone(fuso)
        pico_sem = max(pico_sem, sem_rateio)

    ultra_real = _ultrapassagem(pico_real, contratada)
    ultra_sem = _ultrapassagem(pico_sem, contratada)

    return CustoEvitado(
        desde=desde,
        ate=ate,
        contratada_kw=contratada,
        tarifa_brl_por_kw=tarifa,
        pico_real_kw=pico_real,
        pico_sem_rateio_kw=pico_sem,
        ultrapassagem_real_kw=ultra_real,
        ultrapassagem_sem_rateio_kw=ultra_sem,
        custo_real_brl=ultra_real * tarifa * MULTIPLICADOR_ULTRAPASSAGEM,
        custo_sem_rateio_brl=ultra_sem * tarifa * MULTIPLICADOR_ULTRAPASSAGEM,
        janelas_analisadas=len(janelas),
        momento_do_pico=momento_pico,
    )
