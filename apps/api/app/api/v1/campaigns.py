"""Gestao de campanhas pelo operador.

Rotas finas: validam quem pode o que, delegam ao servico e traduzem o erro de
dominio. A regra comercial toda mora em `campaign_service`.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import DbSession, OperatorUser, ScopedSiteId
from app.models.campaign import Campaign, Mission
from app.schemas.campanha import CampanhaIn, CampanhaOut, DesempenhoOut
from app.services import campaign_service

router = APIRouter(prefix="/campaigns", tags=["campanhas"])


async def _da_praca(db, campanha_id: uuid.UUID, site_id: uuid.UUID) -> Campaign:
    """Carrega a campanha conferindo que ela pertence a esta praca.

    Seguranca: `site_id` vem de `ScopedSiteId`, que para operador comum ignora o
    que a query pedir e devolve sempre o site dele. Sem esta checagem, trocar o
    id na URL editaria a campanha do vizinho.
    """
    campanha = (
        await db.execute(
            select(Campaign)
            .where(Campaign.id == campanha_id)
            .options(selectinload(Campaign.missions))
        )
    ).scalar_one_or_none()
    if campanha is None:
        raise HTTPException(status_code=404, detail="campanha não encontrada")
    if campanha.site_id != site_id:
        # Campanha de rede (site_id nulo) e' visivel mas nao editavel por
        # operador de praca: quem paga e' a rede.
        raise HTTPException(
            status_code=403, detail="esta campanha não pertence à sua praça"
        )
    return campanha


@router.get("", response_model=list[CampanhaOut])
async def listar(db: DbSession, _: OperatorUser, site_id: ScopedSiteId):
    return await campaign_service.listar_do_site(db, site_id)


@router.post("", response_model=CampanhaOut, status_code=201)
async def criar(payload: CampanhaIn, db: DbSession, _: OperatorUser, site_id: ScopedSiteId):
    # O site vem do escopo, nunca do corpo: aceitar `site_id` do payload deixaria
    # um operador criar campanha paga pelo vizinho.
    if payload.patrocinador == "site":
        dono = site_id
    else:
        dono = None

    campanha = Campaign(
        nome=payload.nome,
        descricao=payload.descricao,
        patrocinador=payload.patrocinador,
        site_id=dono,
        starts_at=payload.starts_at,
        ends_at=payload.ends_at,
        ativa=payload.ativa,
        beneficio_tipo=payload.beneficio_tipo,
        beneficio_valor=payload.beneficio_valor,
        teto_por_recompensa=payload.teto_por_recompensa,
        orcamento_brl=payload.orcamento_brl,
        limite_por_motorista=payload.limite_por_motorista,
    )
    db.add(campanha)
    await db.flush()

    for missao in payload.missoes:
        db.add(Mission(campaign_id=campanha.id, **missao.model_dump()))
    await db.commit()

    return (
        await db.execute(
            select(Campaign)
            .where(Campaign.id == campanha.id)
            .options(selectinload(Campaign.missions))
        )
    ).scalar_one()


@router.patch("/{campanha_id}", response_model=CampanhaOut)
async def atualizar(
    campanha_id: uuid.UUID,
    payload: dict,
    db: DbSession,
    _: OperatorUser,
    site_id: ScopedSiteId,
):
    campanha = await _da_praca(db, campanha_id, site_id)

    # Lista curta e fechada. O orcamento ja consumido e o patrocinador nao entram:
    # mudar quem paga depois de o dinheiro ter saido reescreveria a historia.
    editaveis = {
        "nome",
        "descricao",
        "ativa",
        "starts_at",
        "ends_at",
        "orcamento_brl",
        "teto_por_recompensa",
        "limite_por_motorista",
    }
    desconhecidos = set(payload) - editaveis
    if desconhecidos:
        raise HTTPException(
            status_code=422,
            detail=f"campos não editáveis: {', '.join(sorted(desconhecidos))}",
        )
    for campo, valor in payload.items():
        setattr(campanha, campo, valor)

    if campanha.ends_at <= campanha.starts_at:
        raise HTTPException(status_code=422, detail="o fim precisa ser depois do início")
    if float(campanha.orcamento_brl) < float(campanha.consumido_brl):
        raise HTTPException(
            status_code=422,
            detail="o orçamento não pode ficar abaixo do que já foi concedido",
        )

    await db.commit()
    await db.refresh(campanha)
    return campanha


@router.get("/{campanha_id}/desempenho", response_model=DesempenhoOut)
async def desempenho(
    campanha_id: uuid.UUID, db: DbSession, _: OperatorUser, site_id: ScopedSiteId
):
    campanha = (
        await db.execute(
            select(Campaign)
            .where(Campaign.id == campanha_id)
            .options(selectinload(Campaign.missions))
        )
    ).scalar_one_or_none()
    if campanha is None:
        raise HTTPException(status_code=404, detail="campanha não encontrada")
    # Leitura e' mais permissiva que escrita: campanha de rede age sobre as
    # recargas desta praca, entao o operador precisa poder ver o efeito dela.
    if campanha.site_id is not None and campanha.site_id != site_id:
        raise HTTPException(status_code=403, detail="esta campanha não pertence à sua praça")
    return await campaign_service.desempenho(db, campanha)


@router.delete(
    "/{campanha_id}", status_code=204, response_model=None, response_class=Response
)
async def encerrar(
    campanha_id: uuid.UUID, db: DbSession, _: OperatorUser, site_id: ScopedSiteId
):
    """Encerra a campanha. NAO apaga.

    Apagar levaria junto o progresso de quem estava no meio dela, e o RESTRICT em
    `rewards.campaign_id` recusaria a exclusao assim que a primeira recompensa
    tivesse sido concedida - com um erro de banco que ninguem sabe ler. Desativar
    e' o que o operador quer dizer com "encerrar", e preserva o rastro.
    """
    campanha = await _da_praca(db, campanha_id, site_id)
    campanha.ativa = False
    await db.commit()
    return Response(status_code=204)
