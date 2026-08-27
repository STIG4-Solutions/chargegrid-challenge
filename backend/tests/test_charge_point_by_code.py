"""Resolucao do ponto pelo codigo do QR.

E' a porta de entrada do fluxo mais rapido do app: chegar no carregador,
apontar a camera e comecar. Um erro aqui manda o motorista para a vaga errada -
ou pior, deixa iniciar recarga num ponto desligado.
"""

import pytest
from fastapi import HTTPException

from app.api.v1.mobile import charge_point_by_code


async def test_encontra_pelo_codigo_exato(db, ponto, site, motorista):
    achado = await charge_point_by_code(ponto.code, db, motorista)
    assert achado.id == ponto.id
    assert achado.code == ponto.code
    assert achado.site_id == site.id
    assert achado.site_name == site.name


async def test_codigo_em_caixa_diferente_tambem_encontra(db, ponto, motorista):
    """Codigo digitado a mao chega de todo jeito; o QR pode vir minusculo."""
    achado = await charge_point_by_code(ponto.code.lower(), db, motorista)
    assert achado.id == ponto.id


async def test_espacos_em_volta_sao_ignorados(db, ponto, motorista):
    achado = await charge_point_by_code(f"  {ponto.code}  ", db, motorista)
    assert achado.id == ponto.id


async def test_codigo_desconhecido_devolve_404(db, motorista):
    with pytest.raises(HTTPException) as erro:
        await charge_point_by_code("CP-QUE-NAO-EXISTE", db, motorista)
    assert erro.value.status_code == 404


async def test_codigo_vazio_devolve_422(db, motorista):
    with pytest.raises(HTTPException) as erro:
        await charge_point_by_code("   ", db, motorista)
    assert erro.value.status_code == 422


async def test_ponto_desativado_nao_pode_ser_usado(db, ponto, motorista):
    """Sem esta guarda, o motorista tentaria iniciar recarga num ponto fora
    de operacao e so' descobiria no erro do POST /app/sessions."""
    ponto.enabled = False
    await db.flush()

    with pytest.raises(HTTPException) as erro:
        await charge_point_by_code(ponto.code, db, motorista)
    assert erro.value.status_code == 409


async def test_disponibilidade_reflete_o_status(db, ponto, motorista):
    from app.models.enums import ChargePointStatus

    achado = await charge_point_by_code(ponto.code, db, motorista)
    assert achado.available is True

    ponto.status = ChargePointStatus.CHARGING
    await db.flush()
    achado = await charge_point_by_code(ponto.code, db, motorista)
    assert achado.available is False
