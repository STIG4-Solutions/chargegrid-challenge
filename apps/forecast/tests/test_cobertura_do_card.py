"""O card grava a cobertura DELE, e nao a de outro grao.

O DEFEITO, achado disparando o job em staging. `exportar.py` fazia:

    medida = metricas.get("cobertura_p10_p90_mensal") or metricas.get("...diaria")

`or` nao distingue dois casos que sao diferentes:

  artefato ANTIGO   nao TEM a chave mensal. A diaria e' a melhor aproximacao
                    disponivel, e emprestar e' razoavel.
  artefato NOVO     TEM a chave, com valor `None`, quando a cobertura nao pode ser
                    medida. Em staging sao 3 pracas: a calibracao rolante de 6 meses
                    junta 18 residuos mensais contra o minimo de 30.

No segundo caso a diaria nao serve. O card saiu anunciando 81,2% de cobertura sobre
uma faixa mensal que ninguem mediu - e 81,2% era a cobertura DIARIA, de outro grao.

`in` no lugar de `or` separa os dois. E' a diferenca entre "nao sei" e "medi e nao deu".

    docker compose --profile forecast run --rm forecast python -m pytest tests -q
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import re  # noqa: E402


def _trecho_da_cobertura() -> str:
    """O bloco de `exportar.py` que decide o valor gravado.

    Lido do arquivo porque a decisao esta' dentro de `main()`, que abre conexao e
    carrega artefato - e o que precisa de teste aqui e' a escolha, nao a execucao.
    """
    fonte = (RAIZ / "exportar.py").read_text(encoding="utf-8")
    achado = re.search(r"metricas = artefato\.get\(.*?wape_modelo = ", fonte, re.DOTALL)
    assert achado, "o bloco da cobertura saiu de exportar.py"
    return achado.group(0)


def test_a_escolha_distingue_ausente_de_nao_medida():
    """`in` e nao `or`: e' a diferenca entre "nao sei" e "medi e nao deu".

    Com `or`, um `None` medido cai na diaria e o card anuncia cobertura de outro grao
    sobre uma faixa que ninguem aferiu. Esta e' a regressao, e ela chegou ao ambiente.
    """
    trecho = _trecho_da_cobertura()
    assert '"cobertura_p10_p90_mensal" in metricas' in trecho, (
        "a escolha voltou a usar `or` e deixou de distinguir chave ausente de valor None"
    )


def test_a_diaria_continua_sendo_reserva_para_artefato_antigo():
    """Nao e' para tirar a reserva - artefato 1.x nao tem a metrica mensal.

    Tirar a diaria faria o card de um artefato antigo ficar sem cobertura nenhuma, o
    que e' pior: perde informacao que existe.
    """
    trecho = _trecho_da_cobertura()
    assert 'metricas.get("cobertura_p10_p90_diaria")' in trecho


def test_a_mensal_e_a_preferida():
    """Ela e' a que descreve o card: a linha gravada e' um TOTAL de mes.

    A cobertura de uma faixa diaria nao vale para a soma de trinta dias - os erros
    diarios se cancelam parcialmente na soma, e a faixa mensal e' relativamente mais
    estreita.
    """
    trecho = _trecho_da_cobertura()
    mensal = trecho.index("cobertura_p10_p90_mensal")
    diaria = trecho.index("cobertura_p10_p90_diaria")
    assert mensal < diaria, "a diaria passou a ser consultada antes da mensal"
