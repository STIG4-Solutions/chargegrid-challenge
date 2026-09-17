"""A trilha de auditoria: quem fez o que, com dinheiro e com permissao.

`audit_logs` existia desde a migration `0001` - ator, acao, entidade, antes,
depois, IP - e NADA nunca gravou uma linha. Tabela de auditoria vazia e' pior
que nenhuma: da a impressao de que ha rastro, e a pergunta so' aparece no dia em
que alguem precisa dele.

O que estes testes fixam nao e' "grava alguma coisa". Sao tres coisas que
separam uma trilha util de uma tabela cheia:

  - o que ENTRA e o que NAO entra. Acao de pessoa que move dinheiro entra; o
    que o worker faz sozinho, nao - senao a tabela enche de linha sem ator;
  - que ela nao vaza segredo. `provider_config` carrega `client_secret`, e
    auditar o "antes e depois" cru trocaria um defeito por outro pior;
  - que ela vive na MESMA transacao do que auditou. Registrar o que foi
    desfeito por rollback mente tanto quanto perder o registro do que aconteceu.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.audit import AuditLog
from app.models.billing import Invoice, SitePaymentMethod
from app.models.enums import InvoiceStatus, PaymentMethodKind
from app.services import audit_service, payment_service


async def _linhas(db, acao: str | None = None) -> list[AuditLog]:
    consulta = select(AuditLog).order_by(AuditLog.occurred_at.desc())
    if acao:
        consulta = consulta.where(AuditLog.action == acao)
    return list((await db.execute(consulta)).scalars().all())


# ------------------------------------------------------------------ mascara


@pytest.mark.parametrize(
    "chave",
    ["client_secret", "webhook_secret", "password", "senha", "api_token", "chave_privada"],
)
def test_valor_sigiloso_nao_vai_para_a_tabela(chave):
    escondido = audit_service.esconder({chave: "nao-pode-vazar", "base_url": "https://psp"})
    assert escondido[chave] == "***"
    assert escondido["base_url"] == "https://psp", "mascarou o que nao devia"


def test_mascara_desce_nos_aninhados():
    """`provider_config` e' um dicionario DENTRO do corpo.

    Uma versao que so' olhasse o primeiro nivel deixaria passar exatamente o
    caso que motivou a funcao.
    """
    escondido = audit_service.esconder(
        {"provider_config": {"client_secret": "segredo", "base_url": "https://psp"}}
    )
    assert escondido["provider_config"]["client_secret"] == "***"
    assert escondido["provider_config"]["base_url"] == "https://psp"


def test_mascara_desce_nas_listas():
    escondido = audit_service.esconder({"metodos": [{"webhook_secret": "s"}, {"kind": "pix"}]})
    assert escondido["metodos"][0]["webhook_secret"] == "***"
    assert escondido["metodos"][1]["kind"] == "pix"


# ------------------------------------------------------------------ gravacao


async def test_ajuste_de_carteira_deixa_rastro(api, como_admin, motorista, db, administrador):
    r = await api.post(
        f"/api/v1/wallets/{motorista.id}/adjust",
        headers=como_admin,
        json={"valor": "15.00", "motivo": "Cortesia por queda do ponto"},
    )
    assert r.status_code == 200, r.text

    linha = (await _linhas(db, "carteira.ajustada"))[0]
    assert linha.actor_id == administrador.id
    assert linha.actor_email == administrador.email, "sem o e-mail, conta apagada vira 'alguem fez'"
    assert linha.entity_id == str(motorista.id)
    assert linha.after["motivo"] == "Cortesia por queda do ponto"
    assert linha.before["saldo"] != linha.after["saldo"]


async def test_estorno_deixa_rastro(api, como_admin, db, site, motorista):
    fatura = Invoice(
        id=uuid.uuid4(),
        code=f"INV-{uuid.uuid4().hex[:6].upper()}",
        site_id=site.id,
        user_id=motorista.id,
        status=InvoiceStatus.OPEN,
        issued_on=datetime.now(UTC).date(),
        subtotal=20,
        total=20,
    )
    db.add(
        SitePaymentMethod(
            id=uuid.uuid4(),
            site_id=site.id,
            kind=PaymentMethodKind.WALLET,
            label="Carteira",
            enabled=True,
        )
    )
    db.add(fatura)
    await db.flush()
    await payment_service.charge_invoice(db, fatura, PaymentMethodKind.WALLET, payer=motorista)

    r = await api.post(f"/api/v1/invoices/{fatura.id}/refund", headers=como_admin)
    assert r.status_code == 200, r.text

    linha = (await _linhas(db, "fatura.estornada"))[0]
    assert linha.entity_id == str(fatura.id)
    assert linha.after["valor"] == 20.0


async def test_metodo_de_pagamento_nao_vaza_a_credencial(api, como_operador_do_site, db, site):
    """O caso que exigiu a mascara.

    `provider_config` carrega `client_secret`. Auditar o antes e depois cru
    escreveria a credencial do PSP numa tabela feita para ser lida por gente.

    A credencial entra pelo BANCO, e nao pelo corpo: `PaymentMethodIn` nao tem
    `provider_config` - hoje so' o seed ou um UPDATE a definem. Por isso o
    segredo aparece no `antes`, que e' onde o vazamento aconteceria ao alterar
    um metodo ja configurado.
    """
    db.add(
        SitePaymentMethod(
            id=uuid.uuid4(),
            site_id=site.id,
            kind=PaymentMethodKind.PIX,
            label="Pix",
            enabled=True,
            provider="pix",
            provider_config={
                "base_url": "https://psp.exemplo",
                "client_secret": "NAO-PODE-VAZAR",
            },
        )
    )
    await db.flush()

    r = await api.put(
        "/api/v1/payment-methods",
        headers=como_operador_do_site,
        json={"kind": "pix", "label": "Pix", "enabled": False, "provider": "pix"},
    )
    assert r.status_code == 200, r.text

    linha = (await _linhas(db, "metodo_de_pagamento.alterado"))[0]
    assert linha.before["provider_config"]["client_secret"] == "***"
    assert linha.before["provider_config"]["base_url"] == "https://psp.exemplo"
    assert "NAO-PODE-VAZAR" not in str(linha.before) + str(linha.after)
    assert linha.before["enabled"] is True and linha.after["enabled"] is False


async def test_ip_do_cliente_fica_registrado(api, como_admin, motorista, db):
    """`x-forwarded-for` antes de `client.host`: em producao ha proxy na frente,
    e sem isso todo acesso ficaria com o IP dele."""
    await api.post(
        f"/api/v1/wallets/{motorista.id}/adjust",
        headers={**como_admin, "x-forwarded-for": "203.0.113.7, 10.0.0.1"},
        json={"valor": "5.00", "motivo": "Teste de IP"},
    )
    linha = (await _linhas(db, "carteira.ajustada"))[0]
    assert linha.ip_address == "203.0.113.7", "guardou o salto do proxy no lugar do cliente"


# --------------------------------------------------- o que NAO e' auditado


async def test_o_que_o_worker_faz_sozinho_nao_entra(db, ponto, motorista, tarifa):
    """Cashback concedido, mensalidade cobrada, cobranca vencida: sao
    consequencias de regra, nao decisoes de alguem.

    Auditar isso encheria a tabela de linha sem ator - exatamente o que ela nao
    serve para guardar. O rastro deles ja existe: log estruturado e linha
    propria no razao.
    """
    from app.services import campaign_service

    antes = len(await _linhas(db))
    await campaign_service.conceder_pendentes(db)
    assert len(await _linhas(db)) == antes


async def test_leitura_nao_e_auditada(api, como_admin, db):
    """Auditar consulta transforma a tabela num log de acesso e afoga o que
    importa."""
    antes = len(await _linhas(db))
    await api.get("/api/v1/audit", headers=como_admin)
    await api.get("/api/v1/invoices", headers=como_admin)
    assert len(await _linhas(db)) == antes


# ---------------------------------------------------------- mesma transacao


async def test_operacao_recusada_nao_deixa_rastro(api, como_admin, motorista, db):
    """A auditoria entra na MESMA transacao do que auditou.

    Um ajuste que o servico recusa nao pode deixar linha dizendo que aconteceu -
    uma trilha que registra o que foi desfeito mente tanto quanto uma que perde
    o que aconteceu.
    """
    antes = len(await _linhas(db, "carteira.ajustada"))
    r = await api.post(
        f"/api/v1/wallets/{motorista.id}/adjust",
        headers=como_admin,
        json={"valor": "-99999.00", "motivo": "Deixaria o saldo negativo"},
    )
    assert r.status_code == 402, r.text
    assert len(await _linhas(db, "carteira.ajustada")) == antes


async def test_rollback_leva_a_auditoria_junto(db, administrador):
    """`registrar` NAO commita, e e' isso que amarra a trilha a operacao.

    O teste de mutacao mostrou que o teste acima nao provava isto: naquele
    caminho o servico estoura ANTES de auditar, entao a linha nunca chega a ser
    criada e trocar `flush` por `commit` passava despercebido.

    Aqui a linha e' criada e a transacao e' desfeita em seguida. Com commit
    proprio, ela sobreviveria - e a trilha passaria a registrar coisa que nao
    aconteceu, que e' a unica forma de uma auditoria ser pior que nenhuma.
    """
    await audit_service.registrar(
        db, ator=administrador, ip=None, acao="teste.rollback", entidade="none"
    )
    assert len(await _linhas(db, "teste.rollback")) == 1, "nem chegou a ser gravada"

    await db.rollback()

    assert await _linhas(db, "teste.rollback") == []


# ------------------------------------------------------------------ leitura


async def test_a_trilha_pode_ser_lida_por_admin(api, como_admin, motorista):
    await api.post(
        f"/api/v1/wallets/{motorista.id}/adjust",
        headers=como_admin,
        json={"valor": "8.00", "motivo": "Cortesia"},
    )
    r = await api.get("/api/v1/audit", headers=como_admin, params={"action": "carteira.ajustada"})

    assert r.status_code == 200, r.text
    assert r.json()[0]["acao"] == "carteira.ajustada"
    assert r.json()[0]["quem"] is not None


async def test_operador_nao_le_a_trilha(api, como_operador_do_site):
    """A trilha diz quem mexeu em que e de qual IP - nao e' assunto de praca."""
    assert (await api.get("/api/v1/audit", headers=como_operador_do_site)).status_code == 403


async def test_motorista_nao_le_a_trilha(api, como_motorista):
    assert (await api.get("/api/v1/audit", headers=como_motorista)).status_code == 403


async def test_registro_sem_ator_e_possivel_mas_identificavel(db):
    """Nem toda linha precisa de ator - mas a ausencia tem de ser legivel, e nao
    um campo vazio que parece defeito."""
    linha = await audit_service.registrar(
        db, ator=None, ip=None, acao="teste.sem_ator", entidade="none"
    )
    assert linha.actor_id is None
    assert linha.actor_email is None
