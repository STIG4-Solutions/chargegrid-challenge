"""Credito na carteira pre-paga.

O valor viajava como parametro de query, em float, e nada impedia o duplo
envio - dois toques no botao viravam dois creditos, sem deixar rastro de
nenhum dos dois.
"""

import uuid

from sqlalchemy import select

from app.models.billing import WalletEntry

ROTA = "/api/v1/app/wallet/topup"


async def _saldo(api, cab) -> float:
    return (await api.get("/api/v1/auth/me", headers=cab)).json()["wallet_balance"]


async def test_credito_soma_ao_saldo(api, como_motorista):
    antes = await _saldo(api, como_motorista)
    r = await api.post(
        ROTA, headers=como_motorista, json={"amount": "50.00", "idempotency_key": uuid.uuid4().hex}
    )
    assert r.status_code == 200, r.text
    assert r.json()["wallet_balance"] == antes + 50


async def test_mesma_chave_nao_credita_duas_vezes(api, como_motorista, db):
    """O retry de uma resposta perdida na rede nao pode cobrar de novo."""
    chave = uuid.uuid4().hex
    corpo = {"amount": "30.00", "idempotency_key": chave}

    antes = await _saldo(api, como_motorista)
    primeira = await api.post(ROTA, headers=como_motorista, json=corpo)
    segunda = await api.post(ROTA, headers=como_motorista, json=corpo)

    assert primeira.status_code == 200
    assert segunda.status_code == 200
    assert primeira.json() == segunda.json(), "a repetida devolveu outro saldo"
    assert await _saldo(api, como_motorista) == antes + 30, "creditou duas vezes"

    registros = (
        (await db.execute(select(WalletEntry).where(WalletEntry.idempotency_key == chave)))
        .scalars()
        .all()
    )
    assert len(registros) == 1


async def test_chaves_diferentes_creditam_as_duas(api, como_motorista):
    antes = await _saldo(api, como_motorista)
    for _ in range(2):
        await api.post(
            ROTA,
            headers=como_motorista,
            json={"amount": "10.00", "idempotency_key": uuid.uuid4().hex},
        )
    assert await _saldo(api, como_motorista) == antes + 20


async def test_credito_deixa_rastro_com_saldo_resultante(api, como_motorista, motorista, db):
    """Sem a razao nao da para reconciliar um saldo depois."""
    await api.post(
        ROTA, headers=como_motorista, json={"amount": "25.00", "idempotency_key": uuid.uuid4().hex}
    )
    registro = (
        (
            await db.execute(
                select(WalletEntry).where(
                    WalletEntry.user_id == motorista.id, WalletEntry.origem == "topup"
                )
            )
        )
        .scalars()
        .one()
    )
    assert float(registro.amount) == 25.0
    assert float(registro.balance_after) == float(motorista.wallet_balance)


async def test_valor_negativo_e_recusado(api, como_motorista):
    r = await api.post(ROTA, headers=como_motorista, json={"amount": "-100.00"})
    assert r.status_code == 422


async def test_valor_zero_e_recusado(api, como_motorista):
    r = await api.post(ROTA, headers=como_motorista, json={"amount": "0"})
    assert r.status_code == 422


async def test_valor_nao_vai_mais_na_url(api, como_motorista):
    """Dinheiro em query string vaza para log de servidor e historico."""
    r = await api.post(f"{ROTA}?amount=999", headers=como_motorista)
    assert r.status_code == 422, "o valor ainda esta sendo aceito pela query"
