"""As consultas do painel ordenam, e sem isso os numeros nao se reproduzem.

O DEFEITO, e ele explica um mistero que este repositorio tinha registrado como
irresolvido. `banco._SESSOES` agrupava com `GROUP BY 1, 2` e nao ordenava. Ordem de
linha sem `ORDER BY` nao e' garantida no PostgreSQL: ela sai do plano, e o plano muda
com estatistica de tabela, `work_mem` e paralelismo.

Medido na base local, resumindo SO' a ordem das linhas devolvidas:

    enable_hashagg = on                          c6dbaf56dc88e17e
    enable_hashagg = off                         6da352e7d2d396ee
    enable_hashagg = on + 4 workers paralelos    c6f3d7d7651f5141

    com ORDER BY 1, 2 (qualquer um dos tres)     6da352e7d2d396ee

Tres planos, tres ordens. E ordem de linha muda o MODELO: o LightGBM soma em ponto
flutuante para montar histograma, e soma de ponto flutuante nao e' associativa.

O MISTERIO. `treinar.py` registrava: "o WAPE mensal saiu 8,31 de manha e 9,94 a tarde,
com a MESMA janela, as mesmas 1.647 linhas e a MESMA regua... Nao ha' o que
reinvestigar de novo". A impressao digital do treino ORDENA antes de hashear - de
proposito, para detectar mudanca de dado - e por isso ela provava que o conjunto era o
mesmo e escondia que a ordem nao era.

Reproduzido em escala pequena ao trazer `staging`: as migracoes do assistente e da
bandeira mudaram a estatistica das tabelas, o plano mudou, e a cobertura diaria foi de
80,0% para 79,8% com impressao digital IDENTICA. Duas corridas seguidas sempre dao o
mesmo numero; o que o move e' o plano mudar.

POR QUE UM TESTE DE TEXTO DE SQL. Estes testes nao tocam banco - e' o contrato desta
suite ("nao precisam do banco"). Conferir a ordem de verdade exigiria Postgres com
dado e dois planos forcados, o que e' medicao, nao teste de regressao. O que se prende
aqui e' o que basta: a consulta declara a ordem.

    docker compose --profile forecast run --rm forecast python -m pytest tests -q
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import pytest  # noqa: E402

# (arquivo, nome da consulta). Toda consulta que AGRUPA e cujo resultado vira linha de
# treino ou de regua entra aqui.
CONSULTAS = [
    ("banco.py", "_SESSOES"),
    ("banco.py", "_ESTACOES"),
    ("janelas/painel.py", "_SESSOES_POR_HORA"),
]


def _sql(arquivo: str, nome: str) -> str:
    """O corpo SQL daquela constante, lido do proprio arquivo.

    Lido e nao importado: importar `banco` exige `sqlalchemy` e a string de conexao, e
    este teste nao quer nem um nem outro.
    """
    texto = (RAIZ / arquivo).read_text(encoding="utf-8")
    achado = re.search(rf"{nome}\s*=\s*text\(\s*\"\"\"(.*?)\"\"\"", texto, re.DOTALL)
    assert achado, f"{nome} nao encontrada em {arquivo} - a constante foi renomeada?"
    # Comentario FORA, e o proprio teste ensinou por que: a primeira versao dele
    # partia no primeiro "ORDER BY" do texto e caiu num comentario que explicava por
    # que ordenar. Pior que o falso negativo seria o falso positivo - um comentario
    # citando `ORDER BY` faria a consulta passar por ordenada sem ordenar nada.
    sem_comentario = [linha.split("--", 1)[0] for linha in achado.group(1).splitlines()]
    return "\n".join(sem_comentario)


@pytest.mark.parametrize(("arquivo", "nome"), CONSULTAS)
def test_consulta_que_agrupa_tambem_ordena(arquivo: str, nome: str):
    """O assert que fecha a irreprodutibilidade.

    `GROUP BY` sem `ORDER BY` deixa a ordem a cargo do plano. Com ela declarada, duas
    execucoes sobre o mesmo dado dao o mesmo modelo - e o numero do README volta a ser
    conferivel por quem le.
    """
    sql = _sql(arquivo, nome)
    if "GROUP BY" not in sql.upper():
        pytest.skip(f"{nome} nao agrupa")
    assert "ORDER BY" in sql.upper(), (
        f"{nome} em {arquivo} agrupa e nao ordena. A ordem das linhas passa a sair do "
        "plano do PostgreSQL, e ordem muda o modelo - ver o cabecalho deste arquivo."
    )


def test_a_ordem_do_painel_diario_cobre_a_chave_inteira():
    """Ordenar por menos que a chave nao resolve.

    A chave do painel e' (praca, dia). `ORDER BY 1` deixaria a ordem dos DIAS dentro de
    cada praca a cargo do plano - que e' o mesmo defeito, um nivel abaixo, e daria a
    mesma variacao de metrica sem nada denunciar.
    """
    sql = _sql("banco.py", "_SESSOES").upper()
    ordem = sql.split("ORDER BY", 1)[1].strip().splitlines()[0]
    assert "1" in ordem and "2" in ordem, f"ORDER BY nao cobre (praca, dia): {ordem!r}"


def test_a_impressao_digital_do_treino_continua_ordenando():
    """E ela deve MESMO ordenar - o que faltava era a consulta, nao o hash.

    A impressao existe para detectar mudanca de DADO entre corridas, e para isso tem de
    ser invariante a ordem. Tirar o `sort_values` dela para "pegar a ordem tambem"
    trocaria um diagnostico bom por dois ruins: ela passaria a mudar por reordenacao
    inofensiva e deixaria de responder a pergunta que motivou a sua criacao.
    """
    treinar = (RAIZ / "treinar.py").read_text(encoding="utf-8")
    trecho = treinar.split("impressao = hashlib.sha256(", 1)[1][:300]
    assert "sort_values" in trecho, "a impressao digital deixou de ordenar"
