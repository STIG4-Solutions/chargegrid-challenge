"""O arquetipo deduzido do equipamento instalado.

Era um mapa de SLUG para arquetipo, escrito a mao. Bastava enquanto so' o seed
criava praca. Desde que o painel ganhou "Nova praca", qualquer praca nascida pelo
produto caia em "corporativo" por omissao - e em silencio, porque um padrao nao
avisa. Aconteceu no staging: duas pracas novas que o modelo leria como
corporativas, herdando a sazonalidade errada.

O que estes testes prendem:

1. Os quatro arquetipos sao alcancaveis, e cada um pela razao certa.
2. O hardware que o SEED instala e' classificado corretamente - sem isso a
   sazonalidade por arquetipo, que o gerador aplica, deixaria de valer no treino.
3. A fronteira entre rodovia e shopping, que e' onde a decisao vive.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pytest  # noqa: E402

from banco import LIMITE_DC_DE_RODOVIA_KW, arquetipo_de  # noqa: E402
from pipeline.schema import ARQUETIPOS_VALIDOS  # noqa: E402

# O que o seed instala em cada carater, na forma que `_ESTACOES` devolve:
# (tem_dc, tem_trifasico, maior kW do parque). `tem_dc` e' `rated_kw >= 50`.
HARDWARE_DO_SEED = {
    "rodovia": (True, True, 150.0),
    "shopping": (True, True, 60.0),
    "corporativo": (False, True, 22.0),
    "condominio": (False, False, 7.4),
}


@pytest.mark.parametrize("esperado,hardware", list(HARDWARE_DO_SEED.items()))
def test_o_hardware_do_seed_e_classificado_no_carater_certo(esperado, hardware):
    """A ponte entre o gerador e o modelo.

    O gerador aplica sazonalidade, energia e perfil horario POR CARATER. Se a
    inferencia ler o carater errado, o modelo aprende a curva de outro tipo de
    local - e isso nao aparece como erro em lugar nenhum, so' como previsao pior.
    """
    assert arquetipo_de(*hardware) == esperado


def test_os_quatro_arquetipos_sao_alcancaveis():
    """Um arquetipo inalcancavel e' um perfil do gerador que ninguem usa."""
    obtidos = {arquetipo_de(*h) for h in HARDWARE_DO_SEED.values()}
    assert obtidos == ARQUETIPOS_VALIDOS


def test_dc_grande_e_rodovia_e_dc_pequeno_e_shopping():
    """A fronteira e' onde o NEGOCIO muda, nao onde o numero e' redondo.

    Ninguem para tres horas na estrada: um DC de 150 kW existe para encher o
    tanque em quinze minutos. Abaixo do limite, o carro fica enquanto a pessoa faz
    outra coisa - e a curva do dia e' outra.
    """
    limite = LIMITE_DC_DE_RODOVIA_KW
    assert arquetipo_de(True, True, limite) == "rodovia"
    assert arquetipo_de(True, True, limite - 0.1) == "shopping"
    assert arquetipo_de(True, True, 350.0) == "rodovia"


def test_sem_dc_o_que_decide_e_a_fase():
    """Trifasico e' predio comercial; monofasico e' vaga de morador.

    A potencia NAO entra aqui: um condominio com 7,4 kW e um escritorio com 22 kW
    se distinguem pela instalacao, e um unico ponto trifasico num predio faria a
    inferencia le-lo como escritorio - razao de o seed instalar so' monofasico
    em condominio.
    """
    assert arquetipo_de(False, True, 22.0) == "corporativo"
    assert arquetipo_de(False, True, 7.4) == "corporativo"
    assert arquetipo_de(False, False, 7.4) == "condominio"
    assert arquetipo_de(False, False, 22.0) == "condominio"


def test_a_potencia_nao_desempata_quando_nao_ha_dc():
    """Um parque AC potente continua sendo AC.

    Sem isto, um escritorio com muitos pontos de 22 kW poderia escorregar para
    rodovia pela soma - e a soma nao e' o sinal: o sinal e' o MAIOR ponto ser DC.
    """
    assert arquetipo_de(False, True, 99.0) == "corporativo"
    assert arquetipo_de(False, False, 99.0) == "condominio"


def test_toda_saida_e_um_arquetipo_que_o_pipeline_conhece():
    """`schema.ARQUETIPOS_VALIDOS` e' quem valida o painel.

    Devolver um rotulo fora dessa lista faria o painel ser recusado na validacao,
    depois de o treino inteiro ja' ter sido montado.
    """
    for dc in (True, False):
        for tri in (True, False):
            for kw in (0.0, 7.4, 22.0, 60.0, 150.0, 400.0):
                assert arquetipo_de(dc, tri, kw) in ARQUETIPOS_VALIDOS
