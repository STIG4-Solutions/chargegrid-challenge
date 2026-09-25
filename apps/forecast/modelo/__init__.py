"""O modelo do ChargeGrid, construido SOBRE o pipeline vendorizado.

POR QUE ESTE PACOTE EXISTE. `pipeline/` e' copia do repositorio de modelagem e
`ruff.toml` o exclui do lint justamente para poder ser reatualizado sem
conflito. Essa premissa estava quebrada: `pipeline/train.py` tinha divergido em
35 linhas em dois commits deste repositorio, e nada dizia isso.

Agora os cinco arquivos de `pipeline/` sao byte a byte iguais a origem, e tudo
que e' do ChargeGrid mora aqui - lintado, formatado e com teste proprio.

O QUE MUDA EM RELACAO AO PIPELINE, e o numero que justifica cada peca. Medido
com walk-forward de 12 meses sobre o banco local, 7 pracas, n=84 registros
mensais e 2.555 dias:

    previsor                                     mes      dia
    regua de media movel de 28 dias            13,95    36,31
    regua por dia da semana (hist_dow)         14,20    29,85
    o modelo como estava (razao sobre m28)     13,96    29,24
    regua de ano-a-ano                          8,67    34,67
    forma presa ao nivel                        8,67    27,50
    nivel por modelo mensal sobre a regua       8,06        -

Nenhuma regua ganha nos dois eixos, e e' por isso que as tres ficam medidas nos
dois: no mes ganha a de ano-a-ano, no dia ganha a por dia da semana.

Tres achados, nesta ordem:

1. `hist_ano_atras` APONTA PARA O MES ERRADO. `hist.tail(395).head(31)` com a
   origem no ultimo dia do mes M cobre origem-394..origem-364, que e' o mes
   ANTERIOR ao alvo, um ano antes. Dar essa janela como razao nao vale nada
   (14,01 contra 13,96); alinhada ao mes alvo vale 2 pontos.

2. A SOMA VAZA. O total do mes e' a soma de trinta razoes previstas: se a MEDIA
   dessas razoes desvia de 1,0, o nivel anda. Era por isso que o modelo
   normalizado pela regua de ano-a-ano PIORAVA o numero dela (12,20 contra
   8,67). Prender a razao a propria media no mes alvo fecha a fuga e melhora os
   DOIS eixos - o diario cai de 29,24 para 27,50.

3. NIVEL E FORMA TEM VENCEDORES DIFERENTES. No nivel mensal ganha um modelo
   pequeno no grao mensal; na forma diaria ganha o modelo diario, por 2,3 pontos
   sobre a melhor regua. Um modelo so' para os dois eixos era o que fazia cada um
   estragar o outro.

O QUE ISTO NAO ATINGIU, dito junto. O plano pedia bater a melhor regua por >= 1
ponto no mes; o ganho medido e' 0,61. A tela serve o modelo porque ele ganha, e a
`fonte` o declara, mas 0,61 ponto sobre 84 observacoes nao e' uma vitoria
folgada - e' uma vantagem pequena que o proximo retreino pode perder.

A REPRODUTIBILIDADE DESTES NUMEROS depende de uma coisa que nao era obvia: a ordem
das linhas do painel. `banco._SESSOES` agrupava sem `ORDER BY`, e ordem sem `ORDER BY`
sai do plano do PostgreSQL - que muda com estatistica de tabela e paralelismo. Medido:
tres planos, tres ordens diferentes. E ordem muda o modelo, porque o LightGBM soma em
ponto flutuante para montar histograma e soma de ponto flutuante nao e' associativa.

Era a explicacao do mistero que `treinar.py` registrava como irresolvido - o WAPE
saindo 8,31 de manha e 9,94 a tarde com as mesmas linhas. A impressao digital ordena
antes de hashear, entao ela provava que o CONJUNTO era o mesmo e escondia que a ORDEM
nao era. Com `ORDER BY`, duas corridas seguidas dao o mesmo numero.

LIMITE DA EVIDENCIA, dito antes e nao depois: o seed repete `PESOS_MENSAIS` ano
a ano por construcao, entao ano-a-ano e' generoso aqui de um jeito que nao se
repete em rede real. O MECANISMO - demanda de recarga tem sazonalidade anual -
e' real; a MAGNITUDE do ganho e' circular, como todo numero medido sobre dado
sintetico. Vale para as metricas do pipeline original tambem, e o README dele
diz o mesmo.
"""

from __future__ import annotations

from .ano_a_ano import LIMITE_DE_CRESCIMENTO, colunas_de_ano
from .faixa import COBERTURA_DECLARADA, QUANTIS, aplicar_faixa, fatores_conformes
from .forma import prender_ao_nivel, prever_forma, treinar_forma
from .limiares import MIN_HIST_DIAS, alinhar_limiar_do_pipeline
from .nivel import FEATURES_MENSAIS, painel_mensal, prever_nivel, tipar_mensal, treinar_nivel
from .perda import PARAMS, PARAMS_NIVEL, treinar_um

__all__ = [
    "COBERTURA_DECLARADA",
    "FEATURES_MENSAIS",
    "LIMITE_DE_CRESCIMENTO",
    "MIN_HIST_DIAS",
    "PARAMS",
    "PARAMS_NIVEL",
    "QUANTIS",
    "alinhar_limiar_do_pipeline",
    "aplicar_faixa",
    "colunas_de_ano",
    "fatores_conformes",
    "painel_mensal",
    "prender_ao_nivel",
    "prever_forma",
    "prever_nivel",
    "treinar_forma",
    "tipar_mensal",
    "treinar_nivel",
    "treinar_um",
]
