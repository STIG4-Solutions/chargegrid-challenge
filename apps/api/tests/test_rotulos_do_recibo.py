"""Todo tipo de linha que o motor emite precisa de rotulo legivel no recibo.

O recibo le `ROTULOS.get(kind, kind)` - chave sem rotulo cai no proprio kind e
imprime `session_fee` no campo "tipo" de um documento de prestacao de contas.
Era o que acontecia: `ROTULOS` trazia "session" e "minimum", que o motor nunca
emitiu, e nao trazia "dynamic" de jeito nenhum.

O teste NAO compara com uma lista escrita a mao. Ele roda o motor em cenarios
que produzem cada tipo de linha e cobra rotulo para o que sair de la - assim um
`kind` novo inventado no motor reprova aqui, em vez de aparecer cru na fatura de
alguem.
"""

from datetime import UTC, datetime
from decimal import Decimal

from app.services.receipt_service import ROTULOS, _brl
from app.services.tariff_engine import Beneficio, rate_session

from .test_tariff_engine import SP, make_session, make_tariff

INICIO = datetime(2026, 3, 10, 13, 0, tzinfo=UTC)


def _kinds_emitidos() -> set[str]:
    """Roda o motor ate ele emitir cada tipo de linha que sabe emitir."""
    fim = INICIO.replace(hour=19)
    cenarios = [
        # energia
        (make_tariff(), None),
        # tempo
        (make_tariff(price_per_min=Decimal("0.35")), None),
        # ociosidade
        (make_tariff(idle_fee_per_min=Decimal("0.20")), None),
        # taxa de conexao
        (make_tariff(session_fee=Decimal("3")), None),
        # complemento de minimo
        (make_tariff(min_charge=Decimal("50")), None),
        # ajuste dinamico
        (make_tariff(dynamic_enabled=True, dynamic_multiplier=Decimal("1.4")), None),
        # kWh do plano
        (make_tariff(), Beneficio("Plano", kwh_inclusos=Decimal("3"))),
        # desconto percentual
        (make_tariff(), Beneficio("Plano", desconto_pct=Decimal("10"))),
    ]

    kinds: set[str] = set()
    for tarifa, beneficio in cenarios:
        sessao = make_session(
            energy_kwh=Decimal("10"),
            started_at=INICIO,
            ended_at=fim,
            charging_stopped_at=INICIO.replace(hour=14),
        )
        resultado = rate_session(
            sessao, tarifa, [], timezone=SP, now=fim, beneficio=beneficio
        )
        kinds.update(linha.kind for linha in resultado.lines)
    return kinds


def test_todo_kind_emitido_tem_rotulo():
    emitidos = _kinds_emitidos()
    # Prova que os cenarios acima realmente exercitam o motor - um conjunto
    # vazio faria o teste passar sem verificar nada.
    assert len(emitidos) >= 7, emitidos

    sem_rotulo = sorted(kind for kind in emitidos if kind not in ROTULOS)
    assert not sem_rotulo, (
        f"o recibo imprimiria estes tipos crus: {sem_rotulo}. "
        "Sao os nomes que o motor usa, e nenhum deles e' legivel para quem "
        "presta contas."
    )


def test_valor_negativo_leva_o_sinal_antes_do_simbolo():
    """"R$ -5,60" se le como erro de formatacao; "-R$ 5,60" se le como credito.

    Nao dava para notar enquanto nenhuma linha podia ser negativa. As linhas de
    plano e de desconto sao, e este e' o documento que a empresa do motorista
    recebe para prestacao de contas.
    """
    assert _brl(5.6) == "R$ 5,60"
    assert _brl(-5.6) == "-R$ 5,60"
    assert _brl(-1234.5) == "-R$ 1.234,50"
    # Zero nao leva sinal.
    assert _brl(0.0) == "R$ 0,00"
    # O separador de milhar continua sendo ponto, e o decimal virgula.
    assert _brl(1234.5) == "R$ 1.234,50"


def test_nenhum_rotulo_e_igual_a_propria_chave():
    """Rotular "energy" como "energy" cumpriria o teste acima sem resolver nada."""
    for kind, rotulo in ROTULOS.items():
        assert rotulo != kind, kind


def test_rotulos_nao_guardam_chaves_que_o_motor_nao_emite():
    """Chave orfa e' rotulo que nunca aparece - e foi assim que o defeito passou.

    "session" e "minimum" ficaram anos em `ROTULOS` parecendo cobrir a taxa de
    conexao e o complemento de minimo. Cobriam nomes que nao existiam.
    """
    orfas = sorted(set(ROTULOS) - _kinds_emitidos())
    assert not orfas, (
        f"estes rotulos nao correspondem a nenhuma linha que o motor emite: {orfas}"
    )
