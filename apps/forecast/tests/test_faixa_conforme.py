"""A faixa cobre o que declara.

O DEFEITO. A faixa saia de dois `LGBMRegressor(objective="quantile")`. Cobertura
nao e' propriedade garantida dessa perda, e nao foi: cobriu 64,8% anunciando 80%,
e mes a mes 12 de 12 ficaram abaixo de 75% -

    61,4  70,5  59,0  62,2  62,7  68,4  56,2  68,6  73,7  67,1  64,5  63,1

Doze de doze abaixo do declarado e' vies, nao azar.

A conforme multiplicativa faz da cobertura uma PROPRIEDADE do conjunto de
calibracao: os fatores sao os percentis 10 e 90 dos residuos `real / previsto`,
entao por construcao 80% dos residuos de calibracao cabem na faixa. Estes testes
prendem essa construcao e os tres casos em que ela precisa se recusar.

    docker compose --profile forecast run --rm forecast python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

from modelo.faixa import (  # noqa: E402
    COBERTURA_DECLARADA,
    MINIMO_DE_RESIDUOS,
    QUANTIS,
    aplicar_faixa,
    cobertura,
    fatores_conformes,
    residuos,
)


def test_a_cobertura_declarada_bate_com_os_quantis():
    """O que este assert prova, e o que ele NAO prova.

    Prova: o valor declarado e' 80,0 e os quantis sao 0,10 e 0,90 - coerentes entre
    si. Se alguem trocar `QUANTIS` para (0,05 ; 0,95) sem mexer no declarado, o
    assert cai, porque a distancia deixa de dar 80.

    Nao prova: que o codigo DERIVA um do outro em vez de repetir o numero. O teste
    de mutacao confirmou isso - substituir a expressao por `80.0` literal nao mata
    nenhum teste, e nenhum teste consegue matar, porque a constante de modulo ja'
    esta' avaliada quando o teste importa. A derivacao fica porque e' o codigo certo,
    nao porque ha' teste para ela.
    """
    assert COBERTURA_DECLARADA == 80.0
    assert (QUANTIS[1] - QUANTIS[0]) * 100 == COBERTURA_DECLARADA


def test_a_faixa_cobre_80_por_cento_do_conjunto_que_a_calibrou():
    """A propriedade que a conforme da' e a de quantil nao dava.

    Residuos lognormais, que e' a forma do erro aqui: 1.000 dias com o mesmo
    previsto. A cobertura no proprio conjunto de calibracao tem de ficar em 80%.
    """
    rng = np.random.default_rng(7)
    previsto = np.full(1000, 100.0)
    real = previsto * rng.lognormal(0.0, 0.5, 1000)
    f = fatores_conformes(residuos(real, previsto))
    p10, p90 = aplicar_faixa(previsto, f)
    medida = cobertura(real, p10, p90)
    assert abs(medida - COBERTURA_DECLARADA) <= 1.5, medida


def test_a_faixa_e_multiplicativa_e_nao_aditiva():
    """Duas pracas de portes muito diferentes, o MESMO erro relativo.

    Uma faixa aditiva calibrada nas duas juntas ficaria larguissima para o
    condominio e estreita para a rodovia. A multiplicativa escala com o previsto,
    e a cobertura fica igual nas duas - e' o mesmo motivo pelo qual o alvo do
    pipeline e' razao.
    """
    rng = np.random.default_rng(3)
    previsto = np.concatenate([np.full(500, 20.0), np.full(500, 2000.0)])
    real = previsto * rng.lognormal(0.0, 0.4, 1000)
    f = fatores_conformes(residuos(real, previsto))
    p10, p90 = aplicar_faixa(previsto, f)
    pequena = cobertura(real[:500], p10[:500], p90[:500])
    grande = cobertura(real[500:], p10[500:], p90[500:])
    assert abs(pequena - grande) < 6, (pequena, grande)


def test_sem_residuos_suficientes_nao_ha_faixa():
    """Com 5 pontos, o percentil 10 e' o menor deles - uma faixa inventada.

    Devolver `None` faz a ausencia de faixa ser uma decisao visivel: a coluna vai
    nula para o banco, que a migracao 0028 permite, e a tela esconde a faixa.
    """
    poucos = pd.Series([0.9, 1.0, 1.1, 1.2, 0.8])
    assert len(poucos) < MINIMO_DE_RESIDUOS
    assert fatores_conformes(poucos) is None


def test_sem_fatores_a_faixa_vira_NaN_e_nao_zero():
    """NaN e nao `None` nem 0: a coluna entra num DataFrame.

    `None` daria coluna de objetos, em que `>=` compara errado calado; zero
    gravaria uma faixa que vai de zero a zero. E a cobertura de uma faixa ausente
    e' `None`, nao 0% - dizer 0% afirmaria que a faixa erra sempre.
    """
    p10, p90 = aplicar_faixa(np.array([10.0, 20.0]), None)
    assert np.isnan(p10).all() and np.isnan(p90).all()
    assert cobertura(np.array([10.0, 20.0]), p10, p90) is None


def test_a_ponta_de_baixo_nunca_fica_negativa():
    """E' propriedade do residuo, e nao de uma guarda.

    Havia um `max(f10, 0.0)` em `fatores_conformes`, e o teste de mutacao mostrou que
    ele era inalcancavel: o residuo e' `real / previsto`, energia entregue nunca e'
    negativa e previsto e' positivo, entao nenhum residuo e' negativo. A guarda saiu.

    O teste fica, medindo a PROPRIEDADE: num painel cheio de dias zerados - o pior
    caso para a cauda esquerda - o fator de baixo tem de ser exatamente zero, e nao
    negativo.
    """
    rng = np.random.default_rng(5)
    previsto = np.full(200, 50.0)
    real = np.where(rng.random(200) < 0.3, 0.0, previsto * 1.1)
    f = fatores_conformes(residuos(real, previsto))
    assert f is not None
    assert f[0] == 0.0, f


def test_faixa_de_largura_zero_nao_e_faixa():
    """Uma serie constante da' os dois percentis iguais.

    Uma faixa de largura zero cobriria 0% dos casos anunciando 80%, e e' pior que
    faixa nenhuma: ela aparece na tela com ares de incerteza medida. `None` faz a
    ausencia ser visivel.
    """
    constante = pd.Series([1.0] * 100)
    assert fatores_conformes(constante) is None


def test_previsto_zero_nao_entra_nos_residuos():
    """`real / 0` e' infinito, e zero vezes qualquer fator continua zero.

    Sem descartar esses casos, um unico dia de previsao zero levaria o percentil 90
    para infinito e a faixa cobriria tudo - cobertura de 100% que nao informa nada.

    O assert e' sobre o RESULTADO e nao sobre o mecanismo: havia duas defesas para
    este caso (trocar o denominador zero por NaN, e filtrar infinito depois), e o
    teste de mutacao mostrou que a segunda pega sozinha. Ficou uma.
    """
    real = np.array([10.0, 12.0, 11.0, 5.0, 0.0])
    previsto = np.array([10.0, 12.0, 11.0, 0.0, 0.0])
    r = residuos(real, previsto)
    assert len(r) == 3, r.tolist()
    assert np.isfinite(r).all()
