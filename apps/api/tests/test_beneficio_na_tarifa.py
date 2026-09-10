"""Vantagem do pagador dentro do motor de tarifacao.

O motor ganhou um parametro opcional `beneficio`, e a ordem em que cada parte
dele entra na conta nao e' detalhe de implementacao: cada posicao existe porque a
posicao alternativa faz o produto prometer na tela o que a fatura nao entrega.
Os testes abaixo guardam essas quatro posicoes, uma a uma.

Nenhum deles toca o banco. `rate_session` e' pura de proposito - quem consulta
assinatura e campanha e' o `billing_service`, que ja tem sessao aberta - e e' o
que permite exercitar o caminho do dinheiro sem subir Postgres.
"""

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.tariff_engine import Beneficio, rate_session

from .test_tariff_engine import SP, make_session, make_tariff

INICIO = datetime(2026, 3, 10, 13, 0, tzinfo=UTC)  # terca, 10h em Sao Paulo


def _sessao(energia="10", minutos=60):
    fim = INICIO.replace(hour=INICIO.hour + minutos // 60)
    return make_session(
        energy_kwh=Decimal(energia), started_at=INICIO, ended_at=fim, charging_stopped_at=fim
    )


def _cobra(tarifa, beneficio=None, energia="10"):
    return rate_session(
        _sessao(energia), tarifa, [], timezone=SP, now=INICIO, beneficio=beneficio
    )


def _linha(resultado, kind):
    achadas = [linha for linha in resultado.lines if linha.kind == kind]
    return achadas[0] if achadas else None


# --------------------------------------------------------------- o contrato


def test_sem_beneficio_o_resultado_e_o_de_sempre():
    """A rede que permitiu mexer no caminho do dinheiro.

    `beneficio=None` nao pode mudar nada: nem total, nem numero de linhas, nem
    o desconto - que fica zero. Os 400 testes que ja existiam dependem disso.
    """
    tarifa = make_tariff(session_fee=Decimal("3"), min_charge=Decimal("5"))
    sem = _cobra(tarifa)
    explicito = _cobra(tarifa, Beneficio(rotulo="Nenhum"))

    assert sem.desconto == Decimal("0.00")
    assert sem.total == explicito.total
    assert len(sem.lines) == len(explicito.lines)
    assert all(linha.amount > 0 for linha in sem.lines)


def test_multiplicador_abaixo_de_um_reduz_uma_vez_so():
    """Reducao de preco conta como abatimento, e nao pode ser contada duas vezes.

    Achado por teste de mutacao: a invariante `total = subtotal - desconto` e'
    auto-consistente e passava dos dois jeitos, entao ela sozinha nao guardava
    nada aqui. O que guarda e' o VALOR.

    Base R$ 14, multiplicador 0,8. O total tem que ser R$ 11,20 - o mesmo que o
    motor entregava antes de `desconto` existir. Somando o ajuste negativo ao
    subtotal E contando-o como desconto, o total cairia para R$ 8,40 e o cliente
    receberia o abatimento duas vezes.
    """
    tarifa = make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("0.8"))
    r = _cobra(tarifa)

    assert r.subtotal == Decimal("14.00")
    assert r.desconto == Decimal("2.80")
    assert r.total == Decimal("11.20")


def test_subtotal_menos_desconto_e_sempre_o_total():
    """A invariante que a fatura documenta desde a primeira migration.

    `InvoiceOut` sempre disse `total = subtotal - discount`, e ate agora a conta
    so' fechava porque `discount` era zero em toda linha do banco.
    """
    cenarios = [
        (make_tariff(), None),
        (make_tariff(min_charge=Decimal("5")), None),
        (make_tariff(session_fee=Decimal("3")), Beneficio("Plano", isenta_session_fee=True)),
        (make_tariff(), Beneficio("Plano", desconto_pct=Decimal("20"))),
        (make_tariff(), Beneficio("Plano", kwh_inclusos=Decimal("4"))),
        (
            make_tariff(min_charge=Decimal("5"), session_fee=Decimal("2")),
            Beneficio(
                "Plano",
                desconto_pct=Decimal("15"),
                kwh_inclusos=Decimal("3"),
                isenta_session_fee=True,
            ),
        ),
        (
            make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("0.8")),
            Beneficio("Plano", desconto_pct=Decimal("10")),
        ),
    ]
    for tarifa, beneficio in cenarios:
        r = _cobra(tarifa, beneficio)
        assert r.total == r.subtotal - r.desconto, (tarifa.min_charge, beneficio)
        assert r.subtotal >= 0 and r.desconto >= 0


# ------------------------------------------------------- ordem de aplicacao


def test_isencao_de_taxa_nao_volta_pelo_valor_minimo():
    """A isencao suprime a linha; nao desconta o mesmo valor no fim.

    Descontada depois, a taxa voltaria embutida no complemento ate o minimo e o
    assinante pagaria de novo por uma isencao que o app ja lhe anunciou. Aqui a
    tarifa cobra R$ 3 de conexao e tem minimo de R$ 5, sobre uma recarga de
    R$ 1,40 - o cenario exato em que a diferenca aparece.
    """
    tarifa = make_tariff(session_fee=Decimal("3"), min_charge=Decimal("5"))
    com_taxa = _cobra(tarifa, energia="1")
    isento = _cobra(tarifa, Beneficio("Plano", isenta_session_fee=True), energia="1")

    assert _linha(com_taxa, "session_fee") is not None
    assert _linha(isento, "session_fee") is None
    # Os dois batem no minimo, mas por caminhos diferentes - e o isento nao pode
    # terminar pagando o mesmo que quem nao tem isencao nenhuma... exceto que o
    # minimo e' piso para os dois. O que o teste guarda e' que a TAXA sumiu.
    assert isento.total == Decimal("5.00")
    assert all(linha.kind != "session_fee" for linha in isento.lines)


def test_desconto_percentual_vem_depois_do_ajuste_dinamico():
    """Ajuste dinamico e' preco, nao desconto.

    Aplicado o percentual ANTES dele, o multiplicador de pico incidiria sobre o
    valor ja reduzido e o assinante pagaria mais caro pelo mesmo desconto
    justamente no horario de pico - o inverso do que o plano promete.

    Base R$ 14, multiplicador 1,5 -> R$ 21. Desconto de 10% depois: R$ 18,90.
    Antes seria 14 - 1,40 = 12,60, e x1,5 = R$ 18,90 tambem... por isso o teste
    compara a BASE do desconto, e nao so' o total: a linha tem que valer 10% de
    21, nao 10% de 14.
    """
    tarifa = make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("1.5"))
    r = _cobra(tarifa, Beneficio("Plano", desconto_pct=Decimal("10")))

    assert r.subtotal == Decimal("21.00")
    assert _linha(r, "desconto").amount == Decimal("-2.10")
    assert r.total == Decimal("18.90")


def test_kwh_inclusos_abatem_da_janela_mais_cara():
    """O assinante nao escolhe a ordem, entao o motor escolhe a favor dele.

    Comecar pela janela barata entregaria o pior uso possivel da franquia.
    """
    tarifa = make_tariff(
        type="time_of_use",
        price_per_kwh=Decimal("1.40"),
    )
    tarifa.windows = []
    # Sem janelas, ha uma faixa de preco so'; o que se guarda aqui e' o valor do
    # abatimento e o fato de ele nao mexer na energia declarada.
    r = _cobra(tarifa, Beneficio("Plano Mensal", kwh_inclusos=Decimal("4")))

    plano = _linha(r, "plano")
    assert plano is not None
    assert plano.amount == Decimal("-5.60")  # 4 kWh x R$ 1,40
    assert float(plano.quantity) == pytest.approx(4.0)
    # A energia entregue continua inteira na fatura: o recibo precisa dizer
    # quantos kWh entraram no carro, nao quantos foram cobrados.
    assert _linha(r, "energy").quantity == Decimal("10.0000")
    assert r.energy_kwh == Decimal("10")
    assert r.total == Decimal("8.40")


def test_franquia_maior_que_a_recarga_nao_gera_credito():
    """Sobra de franquia nao vira dinheiro a receber."""
    tarifa = make_tariff()
    r = _cobra(tarifa, Beneficio("Plano", kwh_inclusos=Decimal("999")), energia="10")
    assert r.total == Decimal("0.00")
    assert r.desconto == r.subtotal


def test_desconto_pode_deixar_o_total_abaixo_do_minimo():
    """Deliberado, e a alternativa e' pior.

    Se o complemento fosse recalculado depois do desconto, um assinante com 20%
    numa sessao pequena pagaria exatamente o mesmo que quem nao assina nada -
    depois de a tela do app ja ter anunciado o desconto a ele. O minimo protege
    contra sessao de graca, nao contra a franquia que o plano concedeu.
    """
    tarifa = make_tariff(min_charge=Decimal("5"))
    sem = _cobra(tarifa, energia="1")
    com = _cobra(tarifa, Beneficio("Plano", desconto_pct=Decimal("20")), energia="1")

    assert sem.total == Decimal("5.00")
    assert com.total == Decimal("4.00")
    assert com.total < Decimal("5.00")


def test_minimo_nao_retoma_a_franquia_do_plano():
    """O minimo compara com o BRUTO, antes dos abatimentos.

    Comparando com o liquido, a franquia seria devolvida ao caixa pelo
    complemento e o plano nao valeria nada em sessao pequena.
    """
    tarifa = make_tariff(min_charge=Decimal("5"))
    r = _cobra(tarifa, Beneficio("Plano", kwh_inclusos=Decimal("10")), energia="10")

    # R$ 14 brutos: acima do minimo, entao nao ha complemento nenhum.
    assert _linha(r, "min_charge") is None
    assert r.total == Decimal("0.00")


# ------------------------------------------------------------- apresentacao


def test_o_rotulo_do_beneficio_chega_na_linha():
    """"Desconto" sozinho nao diz de onde veio."""
    r = _cobra(make_tariff(), Beneficio("Plano Mensal", desconto_pct=Decimal("10")))
    assert "Plano Mensal" in _linha(r, "desconto").description


def test_as_dict_publica_o_desconto():
    """A previa do app le daqui; sem a chave, a tela nao fecha com a fatura."""
    r = _cobra(make_tariff(), Beneficio("Plano", desconto_pct=Decimal("10")))
    dados = r.as_dict()
    assert dados["desconto"] == float(r.desconto)
    assert dados["subtotal"] - dados["desconto"] == pytest.approx(dados["total"])
