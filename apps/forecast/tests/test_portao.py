"""O portao compara com a MELHOR regua, e a regra tem uma casa so'.

O DEFEITO QUE ISTO PRENDE. A regra vivia dentro de `main()` do `exportar.py`, e o
resumo do job de previsao a reescrevia em YAML - comparando so' com a media movel:

    modelo, regua = m.get("wape_mensal"), m.get("wape_mensal_baseline_m28")
    venceu = modelo is not None and regua is not None and modelo < regua

Enquanto havia uma regua so', as duas versoes concordavam. Desde que a de ano-a-ano
entrou, elas DIVERGEM:

    caso                          modelo    m28   melhor   resumo   portao
    a corrida de 25/09             12,25  15,72    14,41   venceu   venceu
    modelo entre as duas reguas    15,00  15,72    14,41   venceu   PERDEU
    ano-a-ano muito melhor         13,00  15,72    11,00   venceu   PERDEU

Em dois de tres casos plausiveis o resumo anunciava uma promocao que o exportador nao
fez - e quem abre a execucao le' o resumo, nao a tabela.

    docker compose --profile forecast run --rm forecast python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from modelo.portao import (  # noqa: E402
    REGUA_PADRAO,
    melhor_regua,
    modelo_vence,
    reguas_medidas,
)

# Os numeros da corrida de staging de 25/09, para o teste falar da realidade.
STAGING = {
    "wape_mensal": 12.25,
    "wape_mensal_baseline_m28": 15.72,
    "wape_mensal_baseline_ano": 14.41,
}


def test_a_melhor_regua_e_a_de_menor_erro():
    """`ano_a_ano` com 14,41 ganha da media movel com 15,72."""
    assert melhor_regua(STAGING) == ("ano_a_ano", 14.41)


def test_o_caso_em_que_a_regra_duplicada_mentia():
    """O assert que separa as duas versoes.

    Um modelo com 15,00 bate a media movel (15,72) e PERDE da de ano-a-ano (14,41). A
    versao que comparava so' com a media movel diria que venceu.
    """
    metricas = {**STAGING, "wape_mensal": 15.00}
    assert metricas["wape_mensal"] < metricas["wape_mensal_baseline_m28"]
    assert modelo_vence(metricas) is False, "o portao voltou a comparar so' com a media movel"


def test_o_caso_de_hoje_continua_promovendo():
    """A correcao nao pode ter derrubado o modelo que realmente ganha."""
    assert modelo_vence(STAGING) is True


def test_empate_nao_promove():
    """Com o mesmo erro, a regua e' preferivel - ela se explica em tres linhas.

    `<` e nao `<=`: e' a diferenca entre "o modelo acrescenta" e "o modelo empata e
    cobra complexidade por isso".
    """
    assert modelo_vence({**STAGING, "wape_mensal": 14.41}) is False


def test_regua_nao_medida_fica_FORA_da_comparacao():
    """Artefato antigo nao tem a metrica de ano-a-ano.

    `None` dentro de um `min` seria erro de tipo aqui - e, em outra linguagem, o menor
    de todos os valores, o que faria uma regua inexistente ganhar de todas.
    """
    antigo = {"wape_mensal": 13.0, "wape_mensal_baseline_m28": 15.72}
    assert reguas_medidas(antigo) == {"media_movel": 15.72}
    assert melhor_regua(antigo) == ("media_movel", 15.72)
    assert modelo_vence(antigo) is True


def test_sem_metrica_nenhuma_o_modelo_NAO_entra():
    """O valor conservador: um artefato sem backtest nao provou nada.

    E a regua nomeada e' a media movel, porque a `fonte` da linha gravada precisa de um
    nome - e a conta mais simples e' a escolha certa quando nao se mediu nada.
    """
    assert melhor_regua({}) == (REGUA_PADRAO, None)
    assert modelo_vence({}) is False
    assert modelo_vence({"wape_mensal": 1.0}) is False


def test_sem_erro_do_modelo_ele_tambem_nao_entra():
    """Metrica de regua sem metrica de modelo nao promove."""
    assert modelo_vence({"wape_mensal_baseline_ano": 9.0}) is False


def test_o_exportador_usa_o_portao_e_nao_uma_copia():
    """O assert que impede a duplicacao de voltar.

    Se alguem reescrever a comparacao dentro do `exportar.py`, a chave da metrica
    aparece la' de novo - e foi assim que as duas versoes divergiram.
    """
    fonte = (RAIZ / "exportar.py").read_text(encoding="utf-8")
    assert "from modelo.portao import" in fonte
    assert "wape_mensal_baseline_m28" not in fonte, (
        "a regra do portao voltou a ser escrita dentro do exportador"
    )


# A asserção equivalente para os WORKFLOWS vive em
# `apps/api/tests/test_workflows_da_previsao.py`, e nao aqui. Ela le' arquivo em
# `.github/workflows/`, na raiz do repositorio - e a imagem deste app copia so'
# `apps/forecast`, entao la' dentro esses arquivos nao existem. Um teste que nao
# encontra o que afirma nao protege nada.
