"""Resolve a prioridade de cada ponto a partir das regras nomeadas do site.

O rateio de potencia serve as faixas de prioridade em ordem decrescente. Ate
aqui a faixa vinha de `charge_points.priority`, um inteiro fixo que ninguem
sabia explicar. Este modulo poe uma regra com nome entre o operador e o numero,
e devolve junto o nome da regra que decidiu - para o painel poder responder
"por que este ponto foi cortado e aquele nao".

Regra de desempate: as regras do site sao lidas em ordem crescente de `ordem` e
a PRIMEIRA que casa vence. Sem uma ordem explicita, duas regras conflitantes
dariam um resultado que depende de como o banco devolveu as linhas - estavel
nos testes, instavel em producao, e impossivel de explicar ao cliente.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, time
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charge_point import ChargePoint
from app.models.priority_rule import PriorityRule
from app.models.site import Site

# Fuso de referencia quando o site nao declarou o proprio. As janelas horarias
# sao escritas em hora local ("das 22h as 6h"), entao resolve-las em UTC
# deslocaria a regra em tres horas e a frota noturna comecaria as 19h.
FUSO_PADRAO = "America/Sao_Paulo"


def dentro_da_janela(inicio: time | None, fim: time | None, momento: time) -> bool:
    """A janela contem este horario?

    Sem janela, a regra vale o dia inteiro.

    Janela que cruza a meia-noite (22h -> 6h) e o caso comum da recarga noturna
    de frota. Com a comparacao ingenua `inicio <= t <= fim` ela nunca casaria -
    nenhum horario e simultaneamente >= 22h e <= 6h -, e a regra mais importante
    do site ficaria silenciosamente desligada. Por isso o caso invertido testa a
    uniao dos dois trechos em vez da intersecao.
    """
    if inicio is None or fim is None:
        return True
    if inicio <= fim:
        return inicio <= momento <= fim
    return momento >= inicio or momento <= fim


def _casa_criterio(regra: PriorityRule, ponto: ChargePoint) -> bool:
    if regra.criterio_tipo == "sempre":
        return True
    valor = (regra.criterio_valor or "").strip()
    if not valor:
        return False
    if regra.criterio_tipo == "ponto":
        codigos = {c.strip().upper() for c in valor.split(",") if c.strip()}
        return (ponto.code or "").upper() in codigos
    if regra.criterio_tipo == "conector":
        alvos = {c.strip().upper() for c in valor.split(",") if c.strip()}
        # O enum guarda o nome ("TYPE2"); aceitar tambem o valor evita que a
        # regra dependa de qual das duas grafias o operador digitou.
        atual = getattr(ponto.connector, "name", None) or str(ponto.connector)
        return atual.upper() in alvos or str(ponto.connector).upper() in alvos
    return False


@dataclass(slots=True)
class PrioridadeResolvida:
    prioridade: int
    regra: str | None  # None = nenhuma regra casou; vale o valor do proprio ponto


def resolver(
    regras: list[PriorityRule],
    pontos: list[ChargePoint],
    *,
    agora_local: time,
) -> dict[str, PrioridadeResolvida]:
    """Prioridade efetiva de cada ponto. Funcao pura - testavel sem banco."""
    ativas = sorted(
        (r for r in regras if r.ativo),
        key=lambda r: (r.ordem, str(r.id)),
    )
    resultado: dict[str, PrioridadeResolvida] = {}
    for ponto in pontos:
        escolhida: PriorityRule | None = None
        for regra in ativas:
            if not dentro_da_janela(regra.janela_inicio, regra.janela_fim, agora_local):
                continue
            if _casa_criterio(regra, ponto):
                escolhida = regra
                break
        resultado[str(ponto.id)] = (
            PrioridadeResolvida(prioridade=escolhida.prioridade, regra=escolhida.nome)
            if escolhida
            else PrioridadeResolvida(prioridade=int(ponto.priority), regra=None)
        )
    return resultado


async def resolver_para_site(
    db: AsyncSession,
    site: Site,
    pontos: list[ChargePoint],
    *,
    agora: datetime | None = None,
) -> dict[str, PrioridadeResolvida]:
    """Carrega as regras do site e resolve, na hora local dele."""
    regras = list(
        (
            await db.execute(
                select(PriorityRule)
                .where(PriorityRule.site_id == site.id)
                .order_by(PriorityRule.ordem)
            )
        )
        .scalars()
        .all()
    )
    if not regras:
        return {
            str(p.id): PrioridadeResolvida(prioridade=int(p.priority), regra=None) for p in pontos
        }

    try:
        fuso = ZoneInfo(site.timezone or FUSO_PADRAO)
    except Exception:
        # Fuso invalido no cadastro nao pode derrubar o rateio: sem potencia
        # distribuida, ninguem carrega. Cai no padrao e segue.
        fuso = ZoneInfo(FUSO_PADRAO)

    momento = (agora or datetime.now(fuso)).astimezone(fuso).time()
    return resolver(regras, pontos, agora_local=momento)


async def listar(db: AsyncSession, site_id: uuid.UUID) -> list[PriorityRule]:
    return list(
        (
            await db.execute(
                select(PriorityRule)
                .where(PriorityRule.site_id == site_id)
                .order_by(PriorityRule.ordem, PriorityRule.nome)
            )
        )
        .scalars()
        .all()
    )


def como_dict(r: PriorityRule) -> dict:
    return {
        "id": str(r.id),
        "nome": r.nome,
        "prioridade": r.prioridade,
        "ordem": r.ordem,
        "ativo": r.ativo,
        "criterio_tipo": r.criterio_tipo,
        "criterio_valor": r.criterio_valor,
        "janela_inicio": r.janela_inicio.strftime("%H:%M") if r.janela_inicio else None,
        "janela_fim": r.janela_fim.strftime("%H:%M") if r.janela_fim else None,
    }
