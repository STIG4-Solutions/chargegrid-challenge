"""O gerador de historico do seed.

Testa as funcoes puras, sem banco. O `seed()` completo abre a propria sessao e
escreve fora da transacao do teste; o que decide a qualidade do historico nao
esta na escrita e sim aqui - quando cada sessao comeca, quanto tempo ocupa o
ponto e de quem ela e'.

Tres defeitos ja passaram por este caminho, e cada um tem um teste abaixo:
sessoes sobrepostas no mesmo conector, energia solar creditada de madrugada, e
motorista com mais recargas por dia do que qualquer pessoa faria.
"""

from __future__ import annotations

import random
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from app.seed import (
    DIAS_DE_HISTORICO,
    FOLGA_ENTRE_SESSOES,
    FUSO_DO_SITE,
    SEMENTE_DO_HISTORICO,
    SITES,
    _atribui_motoristas,
    _fracao_solar,
    _poisson,
    _sessoes_do_site,
)

# O modelo de previsao descarta qualquer local com menos que isto de energia.
# O numero mora no pipeline de modelagem (`MIN_HIST_DIAS`), e o seed existe em
# boa parte para atravessa-lo.
MINIMO_DE_DIAS_DO_MODELO = 150


def _montado(carater: str = "shopping", dias: int = DIAS_DE_HISTORICO) -> dict:
    """Um site de mentira, com o minimo que o gerador le dele."""
    pontos = [
        SimpleNamespace(id=uuid.uuid4(), rated_kw=22.0),
        SimpleNamespace(id=uuid.uuid4(), rated_kw=11.0),
    ]
    return {
        "site": SimpleNamespace(id=uuid.uuid4()),
        "peak": SimpleNamespace(id=uuid.uuid4(), name="Tarifa Ponta"),
        "off_peak": SimpleNamespace(id=uuid.uuid4(), name="Tarifa Fora de Ponta"),
        "pontos": pontos,
        "carater": carater,
        "sessoes_dia": 12.0,
        "dias": dias,
    }


def _gera(carater: str = "shopping", dias: int = DIAS_DE_HISTORICO) -> list[dict]:
    return _sessoes_do_site(
        random.Random(SEMENTE_DO_HISTORICO), _montado(carater, dias), datetime.now(UTC)
    )


def test_nenhum_ponto_atende_dois_carros_ao_mesmo_tempo():
    """Regressao: a ocupacao do ponto era reiniciada a meia-noite.

    Uma sessao comecada as 23h50 seguia no conector depois da virada, mas o dia
    seguinte comecava sem saber disso e encaixava a primeira sessao da madrugada
    por cima. Deu 23 pares de carros plugados simultaneamente no mesmo conector
    em dois anos de historico.

    O banco nao acusaria: `uq_active_session_per_charge_point` so' cobre sessao
    ATIVA, e historico nasce faturado. Quem acusaria e' o relatorio de ocupacao,
    passando de 100% sem explicacao.
    """
    for carater in ("corporativo", "shopping", "rodovia", "condominio"):
        por_ponto: dict[uuid.UUID, list[dict]] = {}
        for sessao in _gera(carater):
            por_ponto.setdefault(sessao["charge_point_id"], []).append(sessao)

        for ponto, sessoes in por_ponto.items():
            sessoes.sort(key=lambda s: s["inicio"])
            for antes, depois in zip(sessoes, sessoes[1:], strict=False):
                assert depois["inicio"] >= antes["fim"], (
                    f"{carater}/{ponto}: sessao de {depois['inicio']} comeca antes"
                    f" de a anterior terminar, em {antes['fim']}"
                )


def test_folga_entre_sessoes_e_respeitada():
    """Desplugar, sair da vaga e outro carro plugar leva tempo.

    Sem esta margem o historico mostraria troca instantanea de carro, e o tempo
    medio entre sessoes - que o relatorio de retorno usa - sairia otimista.
    """
    por_ponto: dict[uuid.UUID, list[dict]] = {}
    for sessao in _gera("condominio"):
        por_ponto.setdefault(sessao["charge_point_id"], []).append(sessao)

    for sessoes in por_ponto.values():
        sessoes.sort(key=lambda s: s["inicio"])
        for antes, depois in zip(sessoes, sessoes[1:], strict=False):
            ocupado_ate = antes["fim"] + timedelta(minutes=antes["ocioso"])
            assert depois["inicio"] >= ocupado_ate + FOLGA_ENTRE_SESSOES


def test_ha_historico_suficiente_para_o_modelo_de_previsao():
    """Os sites de operacao completa atravessam o piso de 150 dias.

    E' a razao de o seed gerar dois anos em vez de uma semana. Abaixo disso o
    modelo descarta o local e a tela de previsao nao tem o que mostrar.
    """
    for carater in ("corporativo", "shopping", "rodovia"):
        dias_com_energia = {
            s["inicio"].astimezone(FUSO_DO_SITE).date() for s in _gera(carater) if s["kwh"] > 0
        }
        assert len(dias_com_energia) > MINIMO_DE_DIAS_DO_MODELO, carater


def test_o_site_novo_fica_abaixo_do_piso_de_proposito():
    """Um local recem-aberto tem que existir no banco.

    E' o unico jeito de exercitar a guarda que faz a tela dizer "sem historico
    suficiente" em vez de exibir uma previsao inventada. Se algum dia todos os
    sites do seed passarem dos 150 dias, essa guarda deixa de ser testada por
    qualquer demonstracao - e so' um cliente real descobriria.
    """
    novos = [spec for spec in SITES if spec[11] < MINIMO_DE_DIAS_DO_MODELO]
    assert novos, "nenhum site do seed exercita o fallback do modelo"


def test_energia_solar_nao_aparece_de_madrugada():
    """Regressao: a fracao verde era um percentual fixo de 31%.

    Com ele, uma recarga as tres da manha era anunciada como 31% solar. Alem de
    falso no recibo, premiaria o horario errado em qualquer missao de energia
    limpa: carregar de madrugada pontuaria como carregar ao meio-dia.
    """
    for hora in (0, 1, 2, 3, 4, 5, 19, 20, 21, 22, 23):
        assert _fracao_solar(hora) == 0.0, hora
    assert _fracao_solar(12) > _fracao_solar(8) > 0.0

    for sessao in _gera("condominio"):
        hora = sessao["inicio"].astimezone(FUSO_DO_SITE).hour
        if hora < 6 or hora > 18:
            assert sessao["verde"] == 0.0


def test_motorista_nao_carrega_em_dois_lugares_ao_mesmo_tempo():
    """A atribuicao percorre a rede em ordem cronologica por este motivo.

    Cada site e' gerado isoladamente; so' depois as sessoes viram uma lista unica
    ordenada. Atribuir antes de ordenar colocaria a mesma pessoa em dois sites
    simultaneos - impossivel, e visivel no historico do app.
    """
    rng = random.Random(SEMENTE_DO_HISTORICO)
    sessoes = _gera("shopping") + _gera("rodovia")
    sessoes.sort(key=lambda s: s["inicio"])

    motoristas = [SimpleNamespace(id=uuid.uuid4()) for _ in range(5)]
    veiculos = {m.id: SimpleNamespace(id=uuid.uuid4()) for m in motoristas}
    _atribui_motoristas(rng, sessoes, motoristas, veiculos)

    por_motorista: dict[uuid.UUID, list[dict]] = {}
    for sessao in sessoes:
        if "user_id" in sessao:
            por_motorista.setdefault(sessao["user_id"], []).append(sessao)

    assert por_motorista, "nenhuma sessao foi atribuida"
    for atribuidas in por_motorista.values():
        atribuidas.sort(key=lambda s: s["inicio"])
        for antes, depois in zip(atribuidas, atribuidas[1:], strict=False):
            assert depois["inicio"] >= antes["fim"]


def test_motorista_recarrega_num_ritmo_humano():
    """Sem intervalo pessoal, uma missao com prazo nao significa nada.

    "Recarregue 5 vezes este mes" precisa custar um mes. Com varias recargas por
    dia estaria cumprida na primeira semana, e a missao viraria enfeite.
    """
    rng = random.Random(SEMENTE_DO_HISTORICO)
    sessoes = _gera("shopping")
    sessoes.sort(key=lambda s: s["inicio"])
    motoristas = [SimpleNamespace(id=uuid.uuid4()) for _ in range(5)]
    veiculos = {m.id: SimpleNamespace(id=uuid.uuid4()) for m in motoristas}
    _atribui_motoristas(rng, sessoes, motoristas, veiculos)

    por_motorista: dict[uuid.UUID, list[datetime]] = {}
    for sessao in sessoes:
        if "user_id" in sessao:
            por_motorista.setdefault(sessao["user_id"], []).append(sessao["inicio"])

    for inicios in por_motorista.values():
        inicios.sort()
        # Duas a quatro recargas por semana: nunca duas no mesmo dia.
        for antes, depois in zip(inicios, inicios[1:], strict=False):
            assert (depois - antes) >= timedelta(days=1)


def test_gerador_e_deterministico():
    """Duas maquinas, o mesmo banco.

    E' o que permite treinar o modelo de previsao numa e usar o artefato na
    outra. Sem isto, cada reseed produziria uma rede diferente e o artefato
    passaria a prever tudo por fallback - sem erro, sem aviso.
    """
    agora = datetime.now(UTC)
    montado = _montado()
    uma = _sessoes_do_site(random.Random(SEMENTE_DO_HISTORICO), montado, agora)
    outra = _sessoes_do_site(random.Random(SEMENTE_DO_HISTORICO), montado, agora)

    assert len(uma) == len(outra)
    for a, b in zip(uma, outra, strict=True):
        assert (a["inicio"], a["kwh"], a["minutos"], a["ocioso"]) == (
            b["inicio"],
            b["kwh"],
            b["minutos"],
            b["ocioso"],
        )


def test_poisson_nunca_devolve_negativo():
    """Arredondar uma normal devolveria numero negativo nos dias fracos.

    Sao justamente os dias que dao carater a serie - fim de semana em predio
    corporativo, ferias de janeiro. Uma contagem negativa viraria zero por
    acidente e apagaria a sazonalidade que o modelo precisa aprender.
    """
    rng = random.Random(SEMENTE_DO_HISTORICO)
    assert _poisson(rng, 0.0) == 0
    assert _poisson(rng, -3.0) == 0
    for media in (0.05, 0.5, 3.0, 12.0):
        amostras = [_poisson(rng, media) for _ in range(400)]
        assert min(amostras) >= 0
        # A media amostral fica perto da media pedida; folga larga de proposito,
        # porque o teste guarda o sinal, nao a qualidade do sorteio.
        assert abs(sum(amostras) / len(amostras) - media) < max(0.5, media * 0.35)
