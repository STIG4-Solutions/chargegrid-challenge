"""Quando compensa comecar a recarga.

O motorista chega no ponto e ve um preco. O que ele nao ve e' que daqui a duas
horas o mesmo kWh custa 30% menos, porque a tarifa tem janela horaria - e essa
informacao existe inteira no banco, do lado do operador.

O conselho so' e' honesto se a conta for a mesma que vai ser cobrada. Por isso
este modulo caminha a sessao minuto a minuto pelo `resolve_rates` do proprio
motor de tarifacao, em vez de comparar precos de tabela: uma recarga de tres
horas iniciada as 21h atravessa a virada da janela no meio, e o preco medio que
ela paga nao e' o preco de nenhuma das duas pontas.

Duas honestidades que a tela precisa carregar junto:

  esperar atrasa. Economizar R$ 8 comecando quatro horas depois so' vale se o
  carro puder ficar. A resposta devolve o horario de termino das duas opcoes.

  o preco nao e' o unico custo. Se o ponto estiver ocupado agora, esperar pode
  nao ser escolha - e a tela precisa dizer isso em vez de sugerir "comece
  agora" para quem vai entrar na fila.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charge_point import ChargePoint
from app.models.enums import ACTIVE_SESSION_STATES, ChargePointStatus
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.tariff import Tariff
from app.services.tariff_engine import resolve_rates

# Passo da simulacao. O motor cobra por minuto, mas varrer 24 h de inicios
# possiveis minuto a minuto seria 1440 simulacoes de ate 1440 passos cada. Em
# 15 minutos o erro e' menor que a granularidade de qualquer janela real -
# nenhuma tarifa muda de preco as 22h07.
PASSO_MIN = 15

# Quanto de economia justifica sugerir que alguem espere. Abaixo disso o
# conselho custa mais atencao do que vale: ninguem adia a recarga por R$ 0,40.
ECONOMIA_MINIMA_BRL = 1.0
ECONOMIA_MINIMA_PCT = 0.05

# Potencia assumida quando o ponto nao declara nada util. So afeta a DURACAO
# estimada, e as duas opcoes usam a mesma - o comparativo continua valendo.
POTENCIA_PADRAO_KW = 7.4


@dataclass(slots=True)
class Opcao:
    inicio: datetime
    fim: datetime
    custo_brl: float
    label: str

    def as_dict(self, fuso: ZoneInfo) -> dict:
        return {
            "inicio": self.inicio.astimezone(fuso).isoformat(),
            "fim": self.fim.astimezone(fuso).isoformat(),
            "hora": self.inicio.astimezone(fuso).strftime("%H:%M"),
            "hora_fim": self.fim.astimezone(fuso).strftime("%H:%M"),
            "custo_brl": round(self.custo_brl, 2),
            "janela": self.label,
        }


def _custo_de(
    tariff: Tariff, inicio: datetime, kwh: float, potencia_kw: float, fuso: ZoneInfo
) -> tuple[float, datetime, str]:
    """Simula uma recarga de `kwh` comecando em `inicio`.

    Caminha em passos de PASSO_MIN atribuindo a energia daquele trecho ao preco
    da janela vigente nele. E' a mesma resolucao que o faturamento usa, entao o
    numero mostrado antes e o numero cobrado depois vem da mesma regra.
    """
    if potencia_kw <= 0 or kwh <= 0:
        return 0.0, inicio, ""

    horas_totais = kwh / potencia_kw
    fim = inicio + timedelta(hours=horas_totais)

    total = Decimal("0")
    rotulos: list[str] = []
    cursor = inicio
    while cursor < fim:
        proximo = min(cursor + timedelta(minutes=PASSO_MIN), fim)
        horas_trecho = (proximo - cursor).total_seconds() / 3600.0
        rates = resolve_rates(tariff, cursor.astimezone(fuso))
        energia = Decimal(str(horas_trecho * potencia_kw))
        total += energia * rates.per_kwh
        # Tempo tambem e cobrado em algumas tarifas; ignorar inflaria a
        # diferenca entre janelas que so' mudam o preco por minuto.
        total += Decimal(str((proximo - cursor).total_seconds() / 60.0)) * rates.per_min
        if not rotulos or rotulos[-1] != rates.label:
            rotulos.append(rates.label)
        cursor = proximo

    return float(total), fim, " → ".join(rotulos)


async def quando_comecar(
    db: AsyncSession,
    charge_point_id: uuid.UUID,
    *,
    kwh: float = 30.0,
    horas: int = 12,
    agora: datetime | None = None,
) -> dict:
    """Compara comecar agora com o melhor horario das proximas `horas`."""
    from app.services import session_service

    agora = agora or datetime.now(UTC)

    cp = (
        await db.execute(select(ChargePoint).where(ChargePoint.id == charge_point_id))
    ).scalar_one_or_none()
    if cp is None:
        return {"disponivel": False, "motivo": "ponto não encontrado"}

    site = (await db.execute(select(Site).where(Site.id == cp.site_id))).scalar_one()
    try:
        fuso = ZoneInfo(site.timezone or "America/Sao_Paulo")
    except Exception:
        fuso = ZoneInfo("America/Sao_Paulo")

    tariff = await session_service.resolve_tariff(db, cp, None)
    if tariff is None or not tariff.windows:
        # Sem janelas o preco nao muda com a hora, e nao ha conselho a dar. Dizer
        # isso e' melhor que devolver "o melhor horario e agora", que soa como
        # uma analise quando e' a ausencia dela.
        return {
            "disponivel": False,
            "motivo": "tarifa sem janelas horárias",
            "timezone": site.timezone,
        }

    potencia = float(cp.rated_kw or 0) or POTENCIA_PADRAO_KW
    # O ponto nunca entrega mais que o teto que o operador definiu.
    if cp.operator_max_kw:
        potencia = min(potencia, float(cp.operator_max_kw))

    custo_agora, fim_agora, rot_agora = _custo_de(tariff, agora, kwh, potencia, fuso)
    melhor = Opcao(inicio=agora, fim=fim_agora, custo_brl=custo_agora, label=rot_agora)

    passos = int(horas * 60 / PASSO_MIN)
    for i in range(1, passos + 1):
        inicio = agora + timedelta(minutes=i * PASSO_MIN)
        custo, fim, rotulo = _custo_de(tariff, inicio, kwh, potencia, fuso)
        if custo < melhor.custo_brl:
            melhor = Opcao(inicio=inicio, fim=fim, custo_brl=custo, label=rotulo)

    economia = custo_agora - melhor.custo_brl
    fracao = economia / custo_agora if custo_agora > 0 else 0.0
    # Duas barreiras, não uma: 5% de R$ 3 continua sendo troco, e R$ 1 de
    # economia numa recarga de R$ 200 não justifica esperar.
    vale = (
        melhor.inicio > agora
        and economia >= ECONOMIA_MINIMA_BRL
        and fracao >= ECONOMIA_MINIMA_PCT
    )

    ocupado = cp.status not in {ChargePointStatus.AVAILABLE}
    fila = (
        await db.execute(
            select(ChargingSession.id).where(
                ChargingSession.charge_point_id == cp.id,
                ChargingSession.state.in_(ACTIVE_SESSION_STATES),
            )
        )
    ).first() is not None

    return {
        "disponivel": True,
        "timezone": site.timezone,
        "kwh": round(kwh, 1),
        "potencia_kw": round(potencia, 1),
        "horizonte_horas": horas,
        "agora": Opcao(agora, fim_agora, custo_agora, rot_agora).as_dict(fuso),
        "melhor": melhor.as_dict(fuso),
        "economia_brl": round(max(0.0, economia), 2),
        "economia_pct": round(max(0.0, fracao) * 100, 1),
        "vale_esperar": vale,
        "esperar_minutos": (
            int((melhor.inicio - agora).total_seconds() // 60) if melhor.inicio > agora else 0
        ),
        "ponto_ocupado": ocupado or fila,
        "tarifa": tariff.name,
    }
