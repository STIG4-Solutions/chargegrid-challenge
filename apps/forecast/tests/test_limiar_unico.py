"""Um limiar de historico minimo, e o aviso ao operador passa a ser verdade.

O DEFEITO. `pipeline/features.py` usava `MIN_HIST_DIAS = 150` para decidir quem
entra no dataset. `pipeline/schema.py` avisa quando uma praca tem menos de 180
dias validos, e o texto diz "sera ignorada no treino".

Para uma praca com 160 dias as duas coisas aconteciam: o aviso aparecia E a praca
entrava no treino. O aviso estava errado do pior jeito possivel - afirmava ao
operador que um dado foi descartado quando nao foi.

Alinhado para 180, que e' o numero que `schema.py` - o arquivo que se chama de
CONTRATO do pipeline - documenta como minimo recomendado. Alinhar para 150 faria o
codigo contradizer o proprio contrato.

    docker compose --profile forecast run --rm forecast python -m pytest tests -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

from modelo.limiares import MIN_HIST_DIAS, alinhar_limiar_do_pipeline  # noqa: E402
from pipeline import features as _features  # noqa: E402


def _limiar_do_schema() -> int:
    """O numero que o aviso de `schema.py` cita, lido do proprio arquivo.

    Lido e nao digitado: e' o unico jeito de este teste falhar se alguem editar o
    contrato sem alinhar o codigo. `schema.py` e' vendorizado e o valor e' literal
    no corpo da funcao, entao nao ha' constante para importar.
    """
    texto = (RAIZ / "pipeline" / "schema.py").read_text(encoding="utf-8")
    achado = re.search(r"minimo recomendado (\d+)", texto)
    assert achado, "o aviso de historico minimo saiu de schema.py"
    return int(achado.group(1))


def test_o_limiar_do_codigo_e_o_mesmo_que_o_aviso_cita():
    """O assert que fecha a contradicao.

    Sem ele, mudar um dos dois numeros volta a produzir a faixa em que a praca
    recebe o aviso de exclusao e e' treinada de qualquer forma.
    """
    assert MIN_HIST_DIAS == _limiar_do_schema() == 180


def test_o_patch_alcanca_features_e_e_idempotente():
    """`features.py` le o global do modulo DENTRO das funcoes.

    E' o que faz reescrever o atributo chegar em `construir_treino` e em
    `construir_previsao` sem editar o arquivo vendorizado. Chamar duas vezes nao
    pode mudar nada na segunda.
    """
    _features.MIN_HIST_DIAS = 150
    assert alinhar_limiar_do_pipeline() == 150
    assert _features.MIN_HIST_DIAS == MIN_HIST_DIAS
    assert alinhar_limiar_do_pipeline() == MIN_HIST_DIAS
    assert _features.MIN_HIST_DIAS == MIN_HIST_DIAS


def test_features_le_o_limiar_em_tempo_de_chamada():
    """O mecanismo do patch, provado em vez de suposto.

    Se `features.py` tivesse capturado o valor num default de argumento, o patch nao
    teria efeito e o treino continuaria em 150 sem nenhum sinal.

    A praca `curta` tem 165 dias antes do mes alvo: e' exatamente a faixa em que os
    dois limiares discordavam - dentro com 150, fora com 180. A praca `longa` esta'
    ali para o quadro nao ficar VAZIO, porque `construir_treino` estoura nesse caso
    (ver `test_quadro_vazio...` abaixo).
    """
    import pandas as pd

    curtas = pd.date_range("2024-01-18", "2024-07-31", freq="D")
    longas = pd.date_range("2022-01-01", "2024-07-31", freq="D")
    painel = pd.concat(
        [
            pd.DataFrame({"location_id": "curta", "date": curtas, "kwh": 10.0}),
            pd.DataFrame({"location_id": "longa", "date": longas, "kwh": 10.0}),
        ],
        ignore_index=True,
    )
    estacoes = pd.DataFrame(
        [
            {
                "location_id": local,
                "location_name": local,
                "archetype": "shopping",
                "power_type": "dc",
                "n_connectors": 2,
                "opened_at": abertura,
            }
            for local, abertura in [
                ("curta", pd.Timestamp("2024-01-18")),
                ("longa", pd.Timestamp("2022-01-01")),
            ]
        ]
    )
    dias_antes_do_alvo = (pd.Timestamp("2024-07-01") - pd.Timestamp("2024-01-18")).days
    assert 150 <= dias_antes_do_alvo < 180, dias_antes_do_alvo

    julho = pd.Timestamp("2024-07-01")
    try:
        _features.MIN_HIST_DIAS = 150
        com_150 = _features.construir_treino(painel, estacoes)
        alinhar_limiar_do_pipeline()
        com_180 = _features.construir_treino(painel, estacoes)
    finally:
        alinhar_limiar_do_pipeline()

    def pracas_no_alvo(ds):
        return set(ds[ds["mes_alvo"] == julho]["location_id"].astype(str))

    assert pracas_no_alvo(com_150) == {"curta", "longa"}, "150 deveria aceitar 165 dias"
    assert pracas_no_alvo(com_180) == {"longa"}, "180 deveria recusar 165 dias"


def test_quadro_vazio_recusa_com_mensagem_em_vez_de_KeyError():
    """O defeito herdado que o teste acima destapou.

    `construir_treino` termina em `_tipar`, que faz `df["archetype"]`: num quadro
    vazio isso e' `KeyError: 'archetype'`, nao um quadro vazio. E' o que um ambiente
    recem-criado recebe hoje no lugar da mensagem que explica o que fazer - e subir o
    limiar para 180 torna o caso mais provavel, nao menos.

    `pipeline/` nao se edita aqui, entao a conferencia vem antes da chamada.
    """
    import pandas as pd
    import pytest

    from modelo.limiares import pracas_elegiveis, recusar_se_nenhuma_praca_elegivel

    curto = pd.DataFrame(
        {
            "location_id": "nova",
            "date": pd.date_range("2026-06-01", periods=40, freq="D"),
            "kwh": 5.0,
        }
    )
    assert pracas_elegiveis(curto) == []
    with pytest.raises(SystemExit, match="dias de historico valido"):
        recusar_se_nenhuma_praca_elegivel(curto)


def test_pracas_elegiveis_conta_dias_VALIDOS_e_nao_linhas():
    """Dia fora do ar entra no painel com `kwh` nulo, e nao pode contar.

    `construir_treino` usa `hist.notna().sum()`; contar linhas aqui faria a
    conferencia aceitar uma praca que a construcao das features depois recusaria - e
    o KeyError voltaria, agora depois de a conferencia ter dito que estava tudo bem.
    """
    import numpy as np
    import pandas as pd

    from modelo.limiares import pracas_elegiveis

    datas = pd.date_range("2024-01-01", periods=400, freq="D")
    # 400 linhas, mas so' 100 com energia.
    painel = pd.DataFrame(
        {
            "location_id": "p",
            "date": datas,
            "kwh": [10.0 if i < 100 else np.nan for i in range(len(datas))],
        }
    )
    assert pracas_elegiveis(painel) == []
