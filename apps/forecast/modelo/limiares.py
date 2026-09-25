"""Um limiar de historico minimo, e nao dois que discordam.

O DEFEITO. `pipeline/features.py` usa `MIN_HIST_DIAS = 150` para decidir se uma
praca entra no dataset. `pipeline/schema.py` avisa quando uma praca tem menos de
`180` dias validos, e o texto do aviso diz "sera ignorada no treino".

Para uma praca com 160 dias as duas coisas acontecem: o aviso aparece E a praca
entra no treino. O aviso esta' simplesmente ERRADO, e errado do pior jeito - ele
afirma ao operador que um dado foi descartado quando nao foi.

A ESCOLHA. Alinhar para 180, e nao para 150. `schema.py` e' o arquivo que se
chama de CONTRATO do pipeline, e 180 e' o numero que ele documenta como minimo
recomendado. Alinhar para baixo faria o codigo contradizer o proprio contrato;
alinhar para cima faz o contrato passar a valer.

Custo medido no banco local: 8.960 -> 8.743 linhas de treino e 42 -> 41 meses,
2,4%. As MESMAS 7 pracas continuam entrando - o que 180 corta e' um mes de
aquecimento, nao uma praca. Quem 180 excluiria e 150 nao sao as pracas com menos
de seis meses, que caem no fallback de media movel de qualquer forma e que a tela
ja' declara como tal.

POR QUE PATCH, e nao edicao. Os dois arquivos sao copia do repositorio de
modelagem e ficam byte a byte iguais a ele de proposito. `features.py` le o
global do modulo dentro das funcoes (`construir_treino` e `construir_previsao`),
entao reescrever o atributo do modulo chega nos dois - e' o mesmo mecanismo pelo
qual `PARAMS` e' sobreposto. O `180` de `schema.py` e' literal no corpo da
funcao e nao precisa de patch: e' justamente o valor para o qual se esta'
alinhando.
"""

from __future__ import annotations

import pandas as pd

from pipeline import features as _features

# O numero que `pipeline/schema.py` documenta como minimo recomendado.
MIN_HIST_DIAS = 180


def alinhar_limiar_do_pipeline() -> int:
    """Faz `features.MIN_HIST_DIAS` concordar com o aviso de `schema.py`.

    Devolve o valor que estava antes, para quem quiser registrar a troca. E'
    idempotente: chamar duas vezes nao muda nada na segunda.
    """
    anterior = _features.MIN_HIST_DIAS
    _features.MIN_HIST_DIAS = MIN_HIST_DIAS
    return anterior


def pracas_elegiveis(painel: pd.DataFrame) -> list[str]:
    """As pracas com dias validos suficientes para o limiar em vigor.

    EXISTE POR UM DEFEITO HERDADO. `construir_treino` e `construir_previsao`
    terminam em `_tipar`, que faz `df["archetype"]` - num quadro vazio isso e'
    `KeyError: 'archetype'`, e nao um quadro vazio. Ou seja: quando NENHUMA praca
    qualifica, o que chega a quem roda nao e' a mensagem que explica o que fazer, e'
    um KeyError de dentro do pandas.

    Nao e' hipotetico. E' o caso de todo ambiente recem-criado, e subir o limiar de
    150 para 180 o torna mais provavel, nao menos.

    `pipeline/` e' copia fiel do repositorio de modelagem e nao se edita aqui, entao
    a conferencia vem antes da chamada. O criterio e' o MESMO de `construir_treino`:
    dias com kWh nao nulo, por praca.
    """
    validos = painel.groupby("location_id", observed=True)["kwh"].apply(lambda s: s.notna().sum())
    return sorted(str(p) for p in validos[validos >= _features.MIN_HIST_DIAS].index)


def recusar_se_nenhuma_praca_elegivel(painel: pd.DataFrame) -> list[str]:
    """Devolve as pracas elegiveis, ou levanta dizendo o que fazer."""
    elegiveis = pracas_elegiveis(painel)
    if not elegiveis:
        por_praca = painel.groupby("location_id", observed=True)["kwh"].apply(
            lambda s: s.notna().sum()
        )
        maior = int(por_praca.max()) if len(por_praca) else 0
        raise SystemExit(
            f"nenhuma praca tem {MIN_HIST_DIAS} dias de historico valido "
            f"(a mais antiga tem {maior}).\n"
            "\n"
            "O modelo precisa de ~6 meses de operacao por praca. Duas saidas:\n"
            "\n"
            "    npm run infra:down -- -v && npm run infra:up   # reseed completo\n"
            "    python -m app.historico --praca SLUG --carater shopping --dias 1460\n"
            "\n"
            "A segunda gera historico para UMA praca que ja' existe, sem tocar nas outras."
        )
    return elegiveis
