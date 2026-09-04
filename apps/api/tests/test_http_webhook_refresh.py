"""Duas rotas sensiveis que nao tinham teste nenhum.

O webhook e' a porta por onde um PSP marca fatura como paga - sem assinatura
valida, qualquer um quitaria a propria conta. O refresh e' o que mantem a sessao
do motorista viva.
"""

import hashlib
import hmac
import json

from app.core.config import settings
from app.core.security import create_access_token, create_refresh_token

WEBHOOK = "/api/v1/payments/webhook"
REFRESH = "/api/v1/auth/refresh"


def _assinar(corpo: bytes) -> str:
    return hmac.new(settings.payment_webhook_secret.encode(), corpo, hashlib.sha256).hexdigest()


# ------------------------------------------------------------------- webhook


async def test_webhook_sem_assinatura_e_recusado(api):
    r = await api.post(WEBHOOK, json={"provider_ref": "x", "status": "paid"})
    assert r.status_code == 401


async def test_webhook_com_assinatura_errada_e_recusado(api):
    corpo = json.dumps({"provider_ref": "x", "status": "paid"}).encode()
    r = await api.post(
        WEBHOOK,
        content=corpo,
        headers={"x-signature": "0" * 64, "content-type": "application/json"},
    )
    assert r.status_code == 401


async def test_assinatura_valida_passa_da_barreira(api):
    """Com assinatura boa o evento e' processado: o 404 vem da referencia, nao
    da autenticacao. E' a diferenca entre 401 e 404 que prova a checagem."""
    corpo = json.dumps({"provider_ref": "inexistente", "status": "paid"}).encode()
    r = await api.post(
        WEBHOOK,
        content=corpo,
        headers={"x-signature": _assinar(corpo), "content-type": "application/json"},
    )
    assert r.status_code == 404, r.text
    assert "referência" in r.json()["detail"]


async def test_assinatura_e_do_corpo_cru_nao_do_json(api):
    """Reordenar o JSON invalida a assinatura - e' isso que impede a forja."""
    original = json.dumps({"provider_ref": "abc", "status": "paid"}).encode()
    adulterado = json.dumps({"status": "paid", "provider_ref": "abc"}).encode()

    r = await api.post(
        WEBHOOK,
        content=adulterado,
        headers={"x-signature": _assinar(original), "content-type": "application/json"},
    )
    assert r.status_code == 401


# ------------------------------------------------------------------- refresh


async def test_refresh_devolve_par_novo(api, motorista):
    r = await api.post(REFRESH, json={"refresh_token": create_refresh_token(str(motorista.id))})
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["access_token"] and corpo["refresh_token"]


async def test_token_de_acesso_nao_serve_para_renovar(api, motorista):
    """Trocar os tipos deixaria um access token virar sessao eterna."""
    r = await api.post(REFRESH, json={"refresh_token": create_access_token(str(motorista.id))})
    assert r.status_code == 401


async def test_refresh_de_usuario_desativado_e_recusado(api, motorista, db):
    token = create_refresh_token(str(motorista.id))
    motorista.is_active = False
    await db.flush()

    r = await api.post(REFRESH, json={"refresh_token": token})
    assert r.status_code == 401


async def test_refresh_com_lixo_e_recusado(api):
    r = await api.post(REFRESH, json={"refresh_token": "nao-e-um-jwt"})
    assert r.status_code == 401
