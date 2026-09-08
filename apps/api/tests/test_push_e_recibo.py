"""Notificacao push e recibo da recarga.

Os dois lidam com coisa que sai do sistema e vai para a mao de uma pessoa:
uma vibracao no bolso e um documento que vai para prestacao de contas. Errar
aqui nao aparece em log - aparece na conta de alguem, ou na notificacao que
chegou para a pessoa errada.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.models.enums import InvoiceStatus, SessionState, StopReason
from app.models.push_device import PushDevice
from app.models.session import SessionEvent
from app.services import notification_service as ns
from app.services import push_senders
from app.services import receipt_service as rs

# ------------------------------------------------------------------- push


class _SenderFalso(push_senders.PushSender):
    def __init__(self):
        self.enviadas: list[push_senders.Mensagem] = []

    def send(self, mensagens):
        self.enviadas.extend(mensagens)
        return len(mensagens)


class _SenderQuebrado(push_senders.PushSender):
    def send(self, mensagens):
        raise push_senders.PushError("servico fora do ar")


@pytest.fixture
def sender(monkeypatch):
    falso = _SenderFalso()
    monkeypatch.setattr(ns, "get_sender", lambda *a, **k: falso)
    return falso


@pytest.fixture
async def aparelho(db, motorista):
    d = PushDevice(
        id=uuid.uuid4(), user_id=motorista.id, token="ExponentPushToken[abc12345]",
        platform="android",
    )
    db.add(d)
    await db.flush()
    return d


@pytest.fixture
async def sessao(db, site, ponto, motorista, agora):
    from app.models.session import ChargingSession

    s = ChargingSession(
        id=uuid.uuid4(), code="SES-9001", site_id=site.id, charge_point_id=ponto.id,
        user_id=motorista.id, state=SessionState.FINISHED,
        started_at=agora - timedelta(hours=1), ended_at=agora,
        duration_s=3600, energy_kwh=18.5, estimated_cost=25.90, idle_minutes=0,
    )
    db.add(s)
    await db.flush()
    return s


def _evento(sessao, tipo, **kw):
    return SessionEvent(
        id=uuid.uuid4(), session_id=sessao.id, occurred_at=datetime.now(UTC),
        event_type=tipo, **kw,
    )


async def test_recarga_concluida_vira_notificacao(db, sessao, aparelho, sender):
    db.add(_evento(sessao, "state_change", to_state=str(SessionState.FINISHED)))
    await db.flush()

    r = await ns.enviar_pendentes(db)
    assert r["mensagens"] == 1
    m = sender.enviadas[0]
    assert m.titulo == "Recarga concluída"
    assert "18.5 kWh" in m.corpo
    assert "25.90" in m.corpo
    assert m.dados["code"] == "SES-9001"


async def test_promocao_na_fila_vira_notificacao(db, sessao, aparelho, sender):
    db.add(_evento(sessao, "queue_promoted", message="Esperou 12 min na fila"))
    await db.flush()

    await ns.enviar_pendentes(db)
    assert sender.enviadas[0].titulo == "Sua vez chegou"


async def test_falha_avisa_que_nao_se_paga_o_que_nao_recebeu(db, sessao, aparelho, sender):
    sessao.stop_reason = StopReason.FAULT
    db.add(_evento(sessao, "state_change", to_state=str(SessionState.FINISHED)))
    await db.flush()

    await ns.enviar_pendentes(db)
    assert sender.enviadas[0].titulo == "Recarga interrompida"
    assert "não paga" in sender.enviadas[0].corpo


async def test_transicao_do_meio_nao_notifica(db, sessao, aparelho, sender):
    """Notificar cada passo treina o motorista a ignorar todos.

    A transicao para CHARGING acontece com ele olhando o app. O evento e
    marcado como avaliado - nao fica voltando na fila para sempre -, mas
    nenhuma mensagem sai.
    """
    db.add(_evento(sessao, "state_change", to_state=str(SessionState.CHARGING)))
    await db.flush()

    r = await ns.enviar_pendentes(db)
    assert r["mensagens"] == 0
    assert r["eventos"] == 1
    assert sender.enviadas == []


async def test_evento_nao_e_notificado_duas_vezes(db, sessao, aparelho, sender):
    """O outbox e' o que garante isso: notified_at para de seleciona-lo."""
    db.add(_evento(sessao, "state_change", to_state=str(SessionState.FINISHED)))
    await db.flush()

    primeira = await ns.enviar_pendentes(db)
    segunda = await ns.enviar_pendentes(db)
    assert primeira["mensagens"] == 1
    assert segunda["mensagens"] == 0
    assert len(sender.enviadas) == 1


async def test_falha_no_envio_nao_marca_nada(db, sessao, aparelho, monkeypatch):
    """Marcar apos falha transformaria "nao entreguei" em "entreguei".

    A notificacao sumiria para sempre, sem erro visivel em lugar nenhum. Os
    eventos tem de voltar no ciclo seguinte.
    """
    monkeypatch.setattr(ns, "get_sender", lambda *a, **k: _SenderQuebrado())
    evento = _evento(sessao, "state_change", to_state=str(SessionState.FINISHED))
    db.add(evento)
    await db.flush()

    r = await ns.enviar_pendentes(db)
    assert r["mensagens"] == 0
    assert "erro" in r
    await db.refresh(evento)
    assert evento.notified_at is None


async def test_motorista_sem_aparelho_nao_trava_a_fila(db, sessao, sender):
    """Conta que nunca abriu o app: sem isso a fila cresceria para sempre."""
    db.add(_evento(sessao, "state_change", to_state=str(SessionState.FINISHED)))
    await db.flush()

    r = await ns.enviar_pendentes(db)
    assert r["eventos"] == 1
    assert r["mensagens"] == 0


async def test_dois_aparelhos_recebem_os_dois(db, sessao, motorista, aparelho, sender):
    db.add(
        PushDevice(
            id=uuid.uuid4(), user_id=motorista.id,
            token="ExponentPushToken[segundo99]", platform="ios",
        )
    )
    db.add(_evento(sessao, "state_change", to_state=str(SessionState.FINISHED)))
    await db.flush()

    r = await ns.enviar_pendentes(db)
    assert r["mensagens"] == 2


def test_provedor_desconhecido_estoura():
    """Cair no simulador em silencio e' a licao do PAYMENT_PROVIDER=stripe."""
    with pytest.raises(push_senders.PushError):
        push_senders.get_sender("firebase")


async def test_ordem_e_cronologica(db, sessao, aparelho, sender):
    """Notificar "concluida" antes de "promovido" conta a historia ao contrario."""
    antigo = _evento(sessao, "queue_promoted", message="Esperou 5 min")
    antigo.occurred_at = datetime.now(UTC) - timedelta(minutes=10)
    novo = _evento(sessao, "state_change", to_state=str(SessionState.FINISHED))
    db.add_all([novo, antigo])
    await db.flush()

    await ns.enviar_pendentes(db)
    assert sender.enviadas[0].titulo == "Sua vez chegou"


async def test_evento_velho_nao_vira_notificacao(db, sessao, aparelho, sender):
    """Push aqui e' sempre sobre o agora.

    Se o worker ficou fora do ar, entregar "venha buscar o carro" duas horas
    depois e' pior que nao entregar: o motorista ja foi embora e a mensagem so'
    confunde. O evento e marcado como avaliado, nao reenviado para sempre.
    """
    velho = _evento(sessao, "state_change", to_state=str(SessionState.FINISHED))
    velho.occurred_at = datetime.now(UTC) - timedelta(hours=2)
    db.add(velho)
    await db.flush()

    r = await ns.enviar_pendentes(db)
    assert r["mensagens"] == 0
    assert r["eventos"] == 1
    await db.refresh(velho)
    assert velho.notified_at is not None, "evento velho tem de sair da fila"


async def test_encerramento_notifica_uma_vez_so(db, sessao, aparelho, sender):
    """A sequencia real de um encerramento, vista no aparelho.

    `finishing -> finished -> billed` gera tres eventos, e dois deles eram
    aceitos como notificaveis. O motorista recebia DUAS mensagens com texto
    identico - energia e custo ja estao fechados nas duas -, o que e pior que
    nao avisar: ele aprende que o app repete e para de ler.

    BILLED nunca pode ser o primeiro estado terminal: a maquina so permite
    `finished -> billed`, entao quem chega la ja foi avisado.
    """
    db.add_all([
        _evento(sessao, "state_change", to_state=str(SessionState.FINISHING)),
        _evento(sessao, "state_change", to_state=str(SessionState.FINISHED)),
        _evento(sessao, "state_change", to_state=str(SessionState.BILLED)),
    ])
    await db.flush()

    r = await ns.enviar_pendentes(db)
    assert r["eventos"] == 3, "os tres eventos saem da fila"
    assert r["mensagens"] == 1, "mas so' um vira notificacao"
    assert sender.enviadas[0].titulo == "Recarga concluída"


# ------------------------------------------------------------ push por HTTP


async def test_registro_de_aparelho(api, motorista, como_motorista, db):
    r = await api.post(
        "/api/v1/app/push-devices",
        json={"token": "ExponentPushToken[novo1234]", "platform": "android"},
        headers=como_motorista,
    )
    assert r.status_code == 204

    from sqlalchemy import select

    d = (
        await db.execute(
            select(PushDevice).where(PushDevice.token == "ExponentPushToken[novo1234]")
        )
    ).scalar_one()
    assert d.user_id == motorista.id


async def test_mesmo_aparelho_troca_de_dono(api, db, motorista, como_motorista, aparelho):
    """Celular emprestado: sem o reaponte, o segundo motorista receberia as
    notificacoes do primeiro — com codigo da recarga e valor."""
    from sqlalchemy import func, select

    r = await api.post(
        "/api/v1/app/push-devices",
        json={"token": aparelho.token, "platform": "android"},
        headers=como_motorista,
    )
    assert r.status_code == 204

    quantos = (
        await db.execute(
            select(func.count()).select_from(PushDevice).where(PushDevice.token == aparelho.token)
        )
    ).scalar_one()
    assert quantos == 1, "o registro repetido criou uma segunda linha"


async def test_remocao_ao_sair(api, como_motorista, aparelho):
    r = await api.delete(f"/api/v1/app/push-devices/{aparelho.token}", headers=como_motorista)
    assert r.status_code == 204
    # De novo: sair da conta nao pode falhar por um token que ja nao existe.
    de_novo = await api.delete(
        f"/api/v1/app/push-devices/{aparelho.token}", headers=como_motorista
    )
    assert de_novo.status_code == 204


async def test_operador_nao_registra_aparelho(api, como_operador):
    r = await api.post(
        "/api/v1/app/push-devices",
        json={"token": "ExponentPushToken[operador]"},
        headers=como_operador,
    )
    assert r.status_code == 403


# ----------------------------------------------------------------- recibo


@pytest.fixture
async def fatura(db, site, sessao, motorista, agora):
    from app.models.billing import Invoice, InvoiceLine, Payment
    from app.models.enums import PaymentMethodKind, PaymentStatus

    inv = Invoice(
        id=uuid.uuid4(), code="INV-7001", site_id=site.id, session_id=sessao.id,
        user_id=motorista.id, status=InvoiceStatus.PAID, currency="BRL",
        subtotal=25.90, discount=0, total=25.90,
        processing_fee=1.04, net_amount=24.86,
        issued_on=agora.date(), paid_at=agora,
        tariff_snapshot={"name": "Tarifa Ponta"},
    )
    db.add(inv)
    await db.flush()
    db.add_all([
        InvoiceLine(
            id=uuid.uuid4(), invoice_id=inv.id, position=0, kind="energy",
            description="Energia · Fora de ponta", quantity=18.5, unit="kWh",
            unit_price=1.40, amount=25.90,
        ),
        Payment(
            id=uuid.uuid4(), invoice_id=inv.id, method=PaymentMethodKind.WALLET,
            status=PaymentStatus.CAPTURED, amount=25.90,
        ),
    ])
    await db.flush()
    return inv


async def test_recibo_traz_o_que_o_motorista_pagou(db, fatura, motorista):
    r = await rs.montar(db, fatura.id, motorista)
    assert r is not None
    assert r["codigo"] == "INV-7001"
    assert r["total"] == 25.90
    assert r["pago"] is True
    assert r["linhas"][0]["tipo"] == "Energia"
    assert r["recarga"]["energia_kwh"] == 18.5


async def test_taxa_do_adquirente_fica_fora_do_recibo(db, fatura, motorista):
    """`net_amount = total - processing_fee`: quem paga a taxa e o
    estabelecimento, descontada do que ele recebe. Mostrar no recibo do
    motorista diria que ele pagou algo que nao pagou — e o documento vai para
    prestacao de contas."""
    r = await rs.montar(db, fatura.id, motorista)
    plano = str(r)
    assert "1.04" not in plano
    assert "24.86" not in plano
    assert "processing_fee" not in r
    assert "net_amount" not in r


async def test_fatura_de_outro_motorista_nao_abre(db, fatura, segundo_motorista):
    """None nos dois casos — inexistente e alheia. Distinguir confirmaria a
    existencia de faturas de terceiros para quem sondar identificadores."""
    assert await rs.montar(db, fatura.id, segundo_motorista) is None
    assert await rs.montar(db, uuid.uuid4(), segundo_motorista) is None


async def test_html_do_recibo_fecha_e_traz_os_numeros(db, fatura, motorista):
    r = await rs.montar(db, fatura.id, motorista)
    html = rs.como_html(r)
    assert html.startswith("<!doctype html>")
    assert html.rstrip().endswith("</html>")
    assert "INV-7001" in html
    assert "R$ 25,90" in html
    assert "Energia" in html
    # A taxa do adquirente tambem nao pode vazar no documento.
    assert "1,04" not in html


async def test_html_escapa_o_que_vem_do_banco(db, fatura, motorista, site):
    """Nome de estabelecimento e' texto que alguem digitou."""
    site.name = '<script>alert("x")</script>'
    await db.flush()

    r = await rs.montar(db, fatura.id, motorista)
    html = rs.como_html(r)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html


async def test_rota_do_recibo(api, fatura, como_motorista):
    dados = await api.get(f"/api/v1/app/invoices/{fatura.id}/receipt", headers=como_motorista)
    assert dados.status_code == 200
    assert dados.json()["codigo"] == "INV-7001"

    doc = await api.get(f"/api/v1/app/invoices/{fatura.id}/receipt.html", headers=como_motorista)
    assert doc.status_code == 200
    assert doc.headers["content-type"].startswith("text/html")
    assert "INV-7001" in doc.text


async def test_rota_do_recibo_alheio_da_404(api, fatura, como_segundo_motorista):
    r = await api.get(f"/api/v1/app/invoices/{fatura.id}/receipt", headers=como_segundo_motorista)
    assert r.status_code == 404
