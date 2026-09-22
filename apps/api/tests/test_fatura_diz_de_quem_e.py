"""A lista de faturas passa a dizer de quem e' cada cobranca.

Antes vinha so' `user_id`, um UUID. A consequencia nao era estetica: a lista de
faturas e' o UNICO lugar do painel onde um motorista aparece, entao nem o
operador sabia de quem era a cobranca em aberto, nem havia como oferecer com
seguranca qualquer acao sobre o dinheiro dessa pessoa - "ajustar o saldo de
3f2a-..." nao e' uma pergunta que alguem deva responder.

O que estes testes fixam:

- o e-mail chega na lista;
- fatura sem dono (recarga por cartao RFID sem conta) continua valendo, com
  `user_email` nulo, em vez de estourar;
- e a consulta NAO faz uma ida ao banco por fatura. O relacionamento e'
  `lazy="raise"`, entao um `selectinload` esquecido vira erro aqui em vez de
  virar lentidao invisivel numa pagina de duzentas linhas.
"""

from datetime import date
from decimal import Decimal

from app.models.billing import Invoice
from app.models.enums import InvoiceStatus


async def _fatura(db, site, dono, *, codigo: str, total: str = "50.00") -> Invoice:
    fatura = Invoice(
        code=codigo,
        site_id=site.id,
        user_id=dono.id if dono is not None else None,
        status=InvoiceStatus.OPEN,
        total=Decimal(total),
        subtotal=Decimal(total),
        net_amount=Decimal(total),
        issued_on=date.today(),
    )
    db.add(fatura)
    await db.flush()
    return fatura


async def test_a_lista_traz_o_email_do_motorista(api, db, site, motorista, como_operador):
    await _fatura(db, site, motorista, codigo="F-COM-DONO")

    resposta = await api.get("/api/v1/invoices", headers=como_operador)

    assert resposta.status_code == 200
    linha = next(i for i in resposta.json()["items"] if i["code"] == "F-COM-DONO")
    assert linha["user_email"] == motorista.email
    assert linha["user_id"] == str(motorista.id)


async def test_fatura_sem_dono_nao_estoura(api, db, site, como_operador):
    """Cobranca de sessao iniciada por cartao RFID sem conta atrelada existe.

    `user_id` sempre foi anulavel; tratar o nulo como erro derrubaria a lista
    inteira por causa de uma linha.
    """
    await _fatura(db, site, None, codigo="F-SEM-DONO")

    resposta = await api.get("/api/v1/invoices", headers=como_operador)

    assert resposta.status_code == 200
    linha = next(i for i in resposta.json()["items"] if i["code"] == "F-SEM-DONO")
    assert linha["user_email"] is None
    assert linha["user_id"] is None


async def test_o_motorista_vem_carregado_junto(api, db, site, motorista, como_operador):
    """Uma consulta por fatura nao aparece em teste - aparece em producao.

    `lazy="raise"` no relacionamento faz o acesso nao carregado LEVANTAR, entao
    este teste falha com erro explicito se alguem tirar o `selectinload` - em
    vez de a pagina simplesmente ficar lenta.
    """
    for i in range(5):
        await _fatura(db, site, motorista, codigo=f"F-N-MAIS-UM-{i}")

    resposta = await api.get("/api/v1/invoices", headers=como_operador)

    assert resposta.status_code == 200
    nossas = [i for i in resposta.json()["items"] if i["code"].startswith("F-N-MAIS-UM-")]
    assert len(nossas) == 5
    assert all(i["user_email"] == motorista.email for i in nossas)
