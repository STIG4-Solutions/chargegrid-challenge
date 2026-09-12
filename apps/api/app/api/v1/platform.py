"""Contrato do estabelecimento com a plataforma.

QUEM PODE O QUE, e a assimetria aqui e' deliberada:

- O OPERADOR ve o proprio contrato, contrata e pede rescisao. E' o dinheiro dele
  saindo, e a decisao e' dele.
- Marcar cobranca como PAGA e' de ADMIN. E' dinheiro entrando na rede, e deixar
  o proprio devedor declarar que pagou nao e' baixa manual - e' baixa nenhuma.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, HTTPException

from app.core.deps import AdminUser, Auditor, DbSession, OperatorUser, ScopedSiteId
from app.core.errors import Conflict, NotFound
from app.services import platform_service

router = APIRouter(prefix="/platform", tags=["plataforma"])


@router.get("/plans")
async def planos(db: DbSession, _: OperatorUser) -> list[dict]:
    """O que a GoodWe vende. Escopo de rede."""
    return [
        {
            "codigo": p.codigo,
            "nome": p.nome,
            "descricao": p.descricao,
            "preco_mensal_brl": float(p.preco_mensal_brl),
            "preco_por_ponto_brl": float(p.preco_por_ponto_brl),
            "pontos_inclusos": p.pontos_inclusos,
            "fee_percent_transacao": float(p.fee_percent_transacao),
            "meses_minimos": p.meses_minimos,
        }
        for p in await platform_service.planos_ativos(db)
    ]


@router.get("/contract")
async def contrato(db: DbSession, _: OperatorUser, site_id: ScopedSiteId) -> dict:
    """Contrato desta praca, com as ultimas cobrancas.

    Seguranca: `site_id` vem do escopo, que para operador comum e' sempre o site
    dele - trocar o parametro na URL nao mostra o contrato do vizinho.
    """
    return await platform_service.contrato_do_site(db, site_id)


@router.post("/contract", status_code=201)
async def contratar(
    payload: dict, db: DbSession, _: OperatorUser, site_id: ScopedSiteId, aud: Auditor
) -> dict:
    codigo = (payload or {}).get("codigo")
    if not codigo:
        raise HTTPException(status_code=422, detail="informe o código do plano")

    multa = payload.get("multa_percentual")
    try:
        await platform_service.contratar(
            db, site_id, str(codigo), Decimal(str(multa)) if multa is not None else None
        )
    except NotFound as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
    except Conflict as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro

    await aud.registrar(
        db, "contrato.criado", "site_subscription", entidade_id=site_id,
        depois={"plano": str(codigo)},
    )
    await db.commit()
    return await platform_service.contrato_do_site(db, site_id)


@router.post("/contract/terminate")
async def rescindir(
    db: DbSession, _: OperatorUser, site_id: ScopedSiteId, aud: Auditor
) -> dict:
    """Pede a rescisao. Dentro do prazo minimo, emite a multa junto.

    Nao e' DELETE: nao apaga nem encerra no ato. O contrato corre ate o fim do
    ciclo ja cobrado, e a resposta diz ate quando e quanto custa.
    """
    try:
        resultado = await platform_service.rescindir(db, site_id)
    except NotFound as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro
    except Conflict as erro:
        raise HTTPException(status_code=409, detail=str(erro)) from erro

    await aud.registrar(
        db, "contrato.rescindido", "site_subscription", entidade_id=site_id, depois=resultado
    )
    await db.commit()
    return resultado


@router.post("/invoices/{cobranca_id}/settle")
async def dar_baixa(
    cobranca_id: uuid.UUID, db: DbSession, _: AdminUser, aud: Auditor
) -> dict:
    """Baixa MANUAL, e so' de admin.

    Nao ha integracao bancaria: a cobranca nasce aberta e alguem da rede confirma
    o recebimento. Deixar o proprio estabelecimento declarar que pagou nao seria
    baixa manual, seria baixa nenhuma.
    """
    try:
        cobranca = await platform_service.marcar_como_paga(db, cobranca_id)
    except NotFound as erro:
        raise HTTPException(status_code=404, detail=str(erro)) from erro

    await aud.registrar(
        db, "cobranca_da_plataforma.baixada", "platform_invoice", entidade_id=cobranca.id,
        depois={
            "competencia": cobranca.competencia.isoformat(),
            "total_brl": float(cobranca.total_brl),
        },
    )
    await db.commit()
    return {
        "id": str(cobranca.id),
        "estado": cobranca.estado,
        "paga_em": cobranca.paga_em.isoformat() if cobranca.paga_em else None,
    }
