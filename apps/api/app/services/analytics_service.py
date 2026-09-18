"""Serie diaria da operacao: o que as outras rotas nao conseguem responder.

Todo agregado do painel ate aqui e' TOTAL DE JANELA - `revenue/summary` dos
ultimos 30 dias, `utilization/by-point` dos ultimos 30 dias. Isso responde
"quanto", e nao responde "para onde esta indo", que e' a pergunta executiva:
duas quinzenas com a mesma receita total sao negocios diferentes se uma esta
subindo e a outra caindo.

Tres decisoes aqui mudam o que o grafico diz, e nenhuma e' cosmetica.

DIA SEM SESSAO APARECE, COM ZERO. `GROUP BY` so' devolve dia que teve
movimento. Desenhar so' esses pontos encosta segunda-feira em quinta-feira e
some com o buraco - a linha fica continua e a queda desaparece. A serie e'
preenchida dia a dia, e o zero e' informacao.

FUSO DO SITE, NAO UTC. Sessao das 22h em Sao Paulo cai no dia seguinte em UTC.
Agrupando em UTC, todo fim de noite migra para o dia errado e o perfil semanal
sai torto - justamente o que se olha para decidir turno e manutencao.

A JANELA NAO PASSA DA IDADE DO SITE. Pedir 90 dias de um site com 20 e'
legitimo, mas os 70 dias anteriores nao sao "dias parados": sao dias em que nao
havia o que medir. Vem `janela_completa: false`, e a tela avisa - mesmo criterio
que `utilization_service` ja' usa.

RECEITA ANCORADA NA SESSAO, e nao na data da fatura. A pergunta e' quanto a
operacao daquele dia rendeu; fatura emitida no dia 5 por recarga do dia 3
pertence ao dia 3. Por isso o join, e nao uma soma solta de `issued_on`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import Date, case, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice
from app.models.enums import InvoiceStatus
from app.models.session import ChargingSession
from app.models.site import Site

# Teto do que se pode pedir. Um ano ja' e' mais do que qualquer leitura
# executiva usa, e evita que a serie vire uma resposta de megabytes.
DIAS_MAXIMO = 365


def _dia_local(coluna, timezone: str):
    """A data local do site a partir de um timestamp com fuso.

    `AT TIME ZONE` no Postgres converte para o fuso pedido; o `cast` corta a
    hora. Feito no banco de proposito: trazer as linhas e agrupar em Python
    custaria uma volta inteira de dados para chegar ao mesmo lugar.
    """
    return cast(func.timezone(timezone, coluna), Date)


async def serie_diaria(db: AsyncSession, site_id: uuid.UUID, dias: int = 30) -> dict:
    """Sessoes, energia e receita de cada dia da janela, sem buraco."""
    dias = max(1, min(int(dias), DIAS_MAXIMO))
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    fuso = ZoneInfo(site.timezone)

    agora = datetime.now(UTC)
    hoje = agora.astimezone(fuso).date()
    primeiro_pedido = hoje - timedelta(days=dias - 1)

    # A janela nao pode comecar antes de existir o que medir.
    primeira_sessao = (
        await db.execute(
            select(func.min(ChargingSession.started_at)).where(ChargingSession.site_id == site_id)
        )
    ).scalar_one()
    nascimento = (
        primeira_sessao.astimezone(fuso).date() if primeira_sessao is not None else primeiro_pedido
    )
    inicio = max(primeiro_pedido, nascimento)
    janela_completa = inicio <= primeiro_pedido

    dia = _dia_local(ChargingSession.started_at, site.timezone)
    linhas = (
        await db.execute(
            select(
                dia.label("dia"),
                func.count(ChargingSession.id),
                func.coalesce(func.sum(ChargingSession.energy_kwh), 0),
                func.coalesce(func.sum(ChargingSession.green_energy_kwh), 0),
            )
            .where(
                ChargingSession.site_id == site_id,
                ChargingSession.started_at.is_not(None),
                dia >= inicio,
                dia <= hoje,
            )
            .group_by(dia)
        )
    ).all()
    por_dia = {
        linha[0]: {
            "sessoes": int(linha[1]),
            "energia_kwh": round(float(linha[2]), 2),
            "verde_kwh": round(float(linha[3]), 2),
        }
        for linha in linhas
    }

    # Receita pelo dia da SESSAO que a originou, nao pelo dia da emissao.
    # Pago e a receber separados: somar os dois chamaria de receita dinheiro que
    # ainda pode nao entrar, e e' esse o numero que vai para decisao.
    dia_da_fatura = _dia_local(ChargingSession.started_at, site.timezone)
    faturas = (
        await db.execute(
            select(
                dia_da_fatura.label("dia"),
                func.coalesce(
                    func.sum(case((Invoice.status == InvoiceStatus.PAID, Invoice.total), else_=0)),
                    0,
                ),
                func.coalesce(
                    func.sum(case((Invoice.status == InvoiceStatus.OPEN, Invoice.total), else_=0)),
                    0,
                ),
            )
            .join(ChargingSession, Invoice.session_id == ChargingSession.id)
            .where(
                ChargingSession.site_id == site_id,
                ChargingSession.started_at.is_not(None),
                dia_da_fatura >= inicio,
                dia_da_fatura <= hoje,
            )
            .group_by(dia_da_fatura)
        )
    ).all()
    receita_por_dia = {
        linha[0]: {
            "receita_brl": round(float(linha[1]), 2),
            "a_receber_brl": round(float(linha[2]), 2),
        }
        for linha in faturas
    }

    serie = []
    cursor = inicio
    while cursor <= hoje:
        movimento = por_dia.get(cursor, {"sessoes": 0, "energia_kwh": 0.0, "verde_kwh": 0.0})
        dinheiro = receita_por_dia.get(cursor, {"receita_brl": 0.0, "a_receber_brl": 0.0})
        serie.append({"dia": cursor.isoformat(), **movimento, **dinheiro})
        cursor += timedelta(days=1)

    energia = sum(d["energia_kwh"] for d in serie)
    sessoes = sum(d["sessoes"] for d in serie)
    receita = sum(d["receita_brl"] for d in serie)

    return {
        "dias": dias,
        "timezone": site.timezone,
        "desde": inicio.isoformat(),
        "ate": hoje.isoformat(),
        # Falso quando o site e' mais novo que a janela pedida. A tela precisa
        # dizer isso: media diaria sobre dias que nao existiram e' media falsa.
        "janela_completa": janela_completa,
        "dias_na_serie": len(serie),
        "serie": serie,
        "totais": {
            "sessoes": sessoes,
            "energia_kwh": round(energia, 2),
            "verde_kwh": round(sum(d["verde_kwh"] for d in serie), 2),
            "receita_brl": round(receita, 2),
            "a_receber_brl": round(sum(d["a_receber_brl"] for d in serie), 2),
            # Divisor e' o tamanho REAL da serie, nao `dias`. Com site novo os
            # dois diferem, e usar `dias` diluiria a media em dias inexistentes.
            "media_diaria_kwh": round(energia / len(serie), 2) if serie else 0.0,
            "media_diaria_brl": round(receita / len(serie), 2) if serie else 0.0,
            "ticket_medio_brl": round(receita / sessoes, 2) if sessoes else 0.0,
            "verde_pct": round(sum(d["verde_kwh"] for d in serie) / energia * 100, 1)
            if energia
            else 0.0,
        },
    }
