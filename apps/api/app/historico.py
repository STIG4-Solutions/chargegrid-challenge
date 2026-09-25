"""Gera historico de recargas para uma praca que JA EXISTE.

    python -m app.historico --praca estabelecimento-a --carater shopping

POR QUE EXISTE. O `seed()` desiste inteiro na primeira praca que encontra - e'
tudo ou nada, e o "nada" e' o caso de todo ambiente que ja' rodou uma vez. Desde
que o painel ganhou "Nova praca", uma praca pode nascer pelo produto e ficar sem
historico para sempre: nao ha como recuar sessoes por rota, e a simulacao so' anda
para frente, em tempo real.

Foi exatamente o caso do staging: tres pracas, a mais antiga com treze dias de
operacao. Nem as reguas de previsao funcionam ali - a media movel pede 28 dias, e
o modelo pede 150.

NAO E' DESTRUTIVO. Nao toca identidade da praca, tarifas, contas, pontos nem
sessoes existentes. Acrescenta sessoes, faturas e linhas de fatura, e recua o
`created_at` da praca - porque uma praca nascida hoje com dois anos de sessoes e' a
contradicao que o proprio pipeline de previsao detecta (`dias_operacao` e' feature
dele).

O QUE NAO GERA, e de proposito: telemetria (seriam milhoes de amostras para
graficos que ninguem abre em datas de dois anos atras), progresso de missao e
leitura de medidor. Nada disso alimenta previsao, e o `seed()` os cria pelo caminho
dele quando roda em banco vazio.

O CARATER E' ARGUMENTO, e nao inferido aqui. A inferencia vive em
`forecast/banco.arquetipo_de`, que e' de outro app e de outra imagem - duplicar a
regra aqui seria criar duas versoes dela para divergirem. E quem popula um ambiente
de demonstracao sabe que tipo de praca quer.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import uuid
import zlib
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.logging import configure_logging, get_logger
from app.db.session import SessionLocal
from app.models.charge_point import ChargePoint
from app.models.enums import UserRole
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.tariff import Tariff
from app.models.user import User, Vehicle
from app.seed import (
    ENERGIA_POR_SESSAO,
    SEMENTE_DO_HISTORICO,
    _atribui_motoristas,
    _gravar_historico,
    _sessoes_do_site,
)

log = get_logger(__name__)

CARATERES = tuple(ENERGIA_POR_SESSAO)

# Acima disto a praca ja' tem operacao, e gerar por cima empilharia historico
# inventado sobre historico real. Exige `--forcar` para passar.
DIAS_QUE_JA_CONTAM = 60


async def _praca(db, slug: str) -> Site:
    site = (await db.execute(select(Site).where(Site.slug == slug))).scalar_one_or_none()
    if site is None:
        conhecidas = (await db.execute(select(Site.slug).order_by(Site.slug))).scalars().all()
        raise SystemExit(
            f"praca '{slug}' nao existe. Conhecidas: {', '.join(conhecidas) or 'nenhuma'}"
        )
    return site


async def _dias_com_energia(db, site_id: uuid.UUID) -> int:
    dia = func.date(ChargingSession.started_at)
    return (
        await db.execute(
            select(func.count(func.distinct(dia))).where(
                ChargingSession.site_id == site_id, ChargingSession.energy_kwh > 0
            )
        )
    ).scalar_one() or 0


async def _tarifas(db, site: Site) -> tuple[Tariff, Tariff]:
    """A tarifa de ponta e a de fora de ponta, para as linhas de fatura.

    Uma praca criada pelo produto costuma ter UMA tarifa, e ela serve para as duas
    pontas: a fatura sai com um preco so', que e' a verdade daquela praca. Zero
    tarifas e' erro - sem preco nao ha fatura, e sem fatura a receita da tela sai
    zero enquanto a energia aparece.
    """
    tarifas = (
        (
            await db.execute(
                select(Tariff).where(Tariff.site_id == site.id).order_by(Tariff.created_at)
            )
        )
        .scalars()
        .all()
    )
    if not tarifas:
        raise SystemExit(
            f"a praca '{site.slug}' nao tem tarifa. Cadastre uma antes: sem preco nao ha "
            "fatura, e a receita da tela sairia zero com a energia aparecendo."
        )
    padrao = next((t for t in tarifas if t.id == site.default_tariff_id), tarifas[0])
    ponta = next((t for t in tarifas if t.id != padrao.id), padrao)
    return ponta, padrao


async def _motoristas_e_veiculos(db) -> tuple[list[User], dict]:
    """Quem pode aparecer como dono de uma sessao.

    A maioria das sessoes fica sem dono de proposito (`PROPORCAO_SEM_DONO` no
    seed), entao uma base sem motorista nenhum nao impede o historico - so' o
    deixa todo anonimo, que e' o que acontece num eletroposto de passagem.
    """
    motoristas = (
        (await db.execute(select(User).where(User.role == UserRole.DRIVER))).scalars().all()
    )
    veiculos = (await db.execute(select(Vehicle))).scalars().all()
    por_dono = {v.user_id: v for v in veiculos}
    return list(motoristas), por_dono


def _semente(slug: str) -> int:
    """Semente estavel por praca.

    `hash()` de string e' aleatorizado por processo (PYTHONHASHSEED), entao usa-lo
    faria duas execucoes produzirem historicos diferentes - e a primeira versao
    disto prometia o contrario no comentario. `crc32` nao muda entre processos.
    """
    return SEMENTE_DO_HISTORICO + zlib.crc32(slug.encode()) % 10_000


async def gerar(db, slug: str, carater: str, dias: int, forcar: bool) -> int:
    """Gera e GRAVA. A sessao entra por parametro para poder ser testada.

    Abrindo a propria sessao aqui, um teste nao conseguiria preparar a praca: ele
    prepara dentro da transacao dele, e esta funcao nao a veria.
    """
    site = await _praca(db, slug)
    pontos = (
        (
            await db.execute(
                select(ChargePoint)
                .where(ChargePoint.site_id == site.id)
                .options(selectinload(ChargePoint.connection))
                .order_by(ChargePoint.code)
            )
        )
        .scalars()
        .all()
    )
    if not pontos:
        raise SystemExit(
            f"a praca '{slug}' nao tem ponto de recarga. Sessao exige ponto "
            "(`charge_point_id` e' NOT NULL), entao cadastre os pontos antes."
        )

    ja_tem = await _dias_com_energia(db, site.id)
    if ja_tem > DIAS_QUE_JA_CONTAM and not forcar:
        raise SystemExit(
            f"a praca '{slug}' ja' tem {ja_tem} dias com energia. Gerar por cima "
            "empilharia historico inventado sobre operacao real. Use --forcar se "
            "for isso mesmo."
        )

    ponta, fora_de_ponta = await _tarifas(db, site)
    motoristas, veiculos = await _motoristas_e_veiculos(db)

    agora = datetime.now(UTC)
    # Recua o nascimento da praca: `dias_operacao` e' feature do modelo, e uma
    # praca nascida hoje com dois anos de sessoes e' contradicao que o proprio
    # pipeline detecta.
    site.created_at = agora - timedelta(days=dias)

    montado = {
        "site": site,
        "pontos": list(pontos),
        "carater": carater,
        "sessoes_dia": _sessoes_por_dia(site, pontos),
        "dias": dias,
        "peak": ponta,
        "off_peak": fora_de_ponta,
    }

    # Mesma semente do seed, deslocada pelo slug: duas execucoes na mesma praca
    # produzem o mesmo historico (reprodutivel), e duas pracas diferentes nao
    # produzem a MESMA serie (o que faria o modelo achar que sao a mesma coisa).
    rng = random.Random(_semente(slug))
    sessoes = _sessoes_do_site(rng, montado, agora)
    sessoes.sort(key=lambda s: s["inicio"])
    _atribui_motoristas(rng, sessoes, motoristas, veiculos)
    gravadas = await _gravar_historico(db, sessoes, agora)
    await db.commit()

    log.info(
        "historico.gerado",
        praca=slug,
        carater=carater,
        dias=dias,
        sessoes=gravadas,
        nascimento=site.created_at.date().isoformat(),
    )
    return gravadas


def _sessoes_por_dia(site: Site, pontos: list[ChargePoint]) -> float:
    """Quantas recargas por dia, deduzido do tamanho da praca.

    O seed traz esse numero a mao em `SITES`, porque lá ele define a praca. Aqui a
    praca ja' existe e o numero tem de sair dela: duas por ponto por dia, limitado
    pelo que a rede aguenta.

    O teto pela rede importa - sem ele, uma praca com oito pontos DC de 150 kW
    numa rede de 75 kW geraria uma demanda que a instalacao nao entrega, e o
    proprio modulo de potencia passaria o tempo todo em rebalanceamento.
    """
    por_ponto = 2.0 * len(pontos)
    maior = max((float(p.rated_kw) for p in pontos), default=1.0)
    cabe = float(site.grid_limit_kw or 0) / maior if maior else len(pontos)
    return max(1.0, min(por_ponto, 2.0 * max(1.0, cabe)))


def main() -> int:
    configure_logging()
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--praca", required=True, help="slug da praca")
    ap.add_argument("--carater", required=True, choices=CARATERES)
    ap.add_argument(
        "--dias",
        type=int,
        default=1460,
        help="quantos dias de historico (padrao 1460, quatro anos)",
    )
    ap.add_argument(
        "--forcar",
        action="store_true",
        help="gera mesmo que a praca ja' tenha operacao",
    )
    args = ap.parse_args()

    async def _rodar() -> int:
        async with SessionLocal() as db:
            return await gerar(db, args.praca, args.carater, args.dias, args.forcar)

    gravadas = asyncio.run(_rodar())
    print(
        f"{gravadas} sessao(oes) gravada(s) em '{args.praca}' ({args.carater}, {args.dias} dias)."
    )
    print(
        "A previsao ainda precisa do job de `apps/forecast` para aparecer na tela:\n"
        "  npm run forecast"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
