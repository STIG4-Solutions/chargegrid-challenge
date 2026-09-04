"""Autorizacao das rotas, pela porta da frente.

Todo o resto da suite chama servico ou handler direto e passa o usuario como
argumento - o que pula a resolucao do token e a guarda de papel. Estes testes
sobem a aplicacao inteira e falam HTTP, que e' a unica forma de provar quem
entra em cada rota.

O buraco que motivou este arquivo: um token de operador recebia 200 em todas as
rotas /app/*, e conseguia escrever nelas.
"""

import uuid

import pytest

ROTAS_DE_LEITURA = [
    "/api/v1/app/stations",
    "/api/v1/app/vehicles",
    "/api/v1/app/reservations",
    "/api/v1/app/invoices",
    "/api/v1/app/sessions",
    "/api/v1/app/sessions/active",
]


@pytest.mark.parametrize("rota", ROTAS_DE_LEITURA)
async def test_motorista_entra_nas_rotas_do_app(api, como_motorista, rota):
    r = await api.get(rota, headers=como_motorista)
    assert r.status_code == 200, r.text


@pytest.mark.parametrize("rota", ROTAS_DE_LEITURA)
async def test_operador_e_recusado_nas_rotas_do_app(api, como_operador, rota):
    r = await api.get(rota, headers=como_operador)
    assert r.status_code == 403, f"{rota} deixou o operador entrar: {r.text}"


@pytest.mark.parametrize("rota", ROTAS_DE_LEITURA)
async def test_admin_tambem_e_recusado(api, como_admin, rota):
    """Admin nao e' privilegio que falta: nao existe motorista por tras dele."""
    r = await api.get(rota, headers=como_admin)
    assert r.status_code == 403, f"{rota} deixou o admin entrar: {r.text}"


@pytest.mark.parametrize("rota", ROTAS_DE_LEITURA)
async def test_sem_token_nao_entra(api, rota):
    r = await api.get(rota)
    assert r.status_code == 401


async def test_token_invalido_nao_entra(api):
    r = await api.get(
        "/api/v1/app/stations", headers={"Authorization": "Bearer nao-e-um-jwt"}
    )
    assert r.status_code == 401


async def test_operador_nao_escreve_pelo_app(api, como_operador):
    """A escrita era o dano real: o operador criava veiculo, sessao, credito."""
    r = await api.post(
        "/api/v1/app/vehicles",
        headers=como_operador,
        json={"model": "Fantasma", "plate": "XXX0000", "battery_kwh": 50},
    )
    assert r.status_code == 403, r.text


async def test_operador_nao_credita_carteira_pelo_app(api, como_operador):
    r = await api.post(
        "/api/v1/app/wallet/topup", headers=como_operador, json={"amount": "100.00"}
    )
    assert r.status_code == 403, r.text


async def test_motorista_nao_entra_no_painel(api, como_motorista):
    """A contrapartida, que ja existia - aqui ganha teste."""
    for rota in ("/api/v1/power/overview", "/api/v1/sessions/kpis", "/api/v1/tariffs"):
        r = await api.get(rota, headers=como_motorista)
        assert r.status_code == 403, f"{rota} deixou o motorista entrar"


async def test_ponto_inexistente_devolve_404(api, como_motorista):
    r = await api.get(
        f"/api/v1/app/charge-points/by-code/{uuid.uuid4().hex[:6].upper()}-99",
        headers=como_motorista,
    )
    assert r.status_code == 404
