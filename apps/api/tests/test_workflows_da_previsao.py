"""Os workflows de previsao nao reescrevem a regra do portao.

POR QUE ISTO MORA NA SUITE DA API, e nao na do forecast - que e' o assunto. A
asserção le' arquivo em `.github/workflows/`, na RAIZ do repositorio. A imagem do
forecast copia so' `apps/forecast`, entao la' dentro esses arquivos nao existem e o
teste passaria por engano ou quebraria por caminho. A suite da API roda num checkout
completo, nativa - e' a unica que ve' a raiz.

O DEFEITO QUE ISTO PRENDE. A regra de decisao do portao - "o modelo entra quando mede
melhor que a MELHOR regua" - vivia dentro de `main()` do `exportar.py`, e o resumo do
job de previsao a reescrevia em YAML comparando so' com a media movel:

    modelo, regua = m.get("wape_mensal"), m.get("wape_mensal_baseline_m28")
    venceu = modelo is not None and regua is not None and modelo < regua

Enquanto havia uma regua so', as duas concordavam. Desde que a de ano-a-ano entrou,
divergem:

    modelo    m28   melhor   o resumo   o portao
     12,25  15,72    14,41     venceu     venceu
     15,00  15,72    14,41     venceu     PERDEU
     13,00  15,72    11,00     venceu     PERDEU

Em dois de tres casos plausiveis o resumo anunciava uma promocao que o exportador nao
fez - e quem abre a execucao le' o resumo, nao a tabela de metricas.

A regra passou a morar em `apps/forecast/modelo/portao.py`. `tests/test_portao.py`, na
suite do forecast, cobre o comportamento dela; aqui se cobre que os workflows a
IMPORTAM em vez de repeti-la.
"""

from __future__ import annotations

from pathlib import Path

import pytest

# `parents[3]`: este arquivo esta em apps/api/tests/, entao sao tres niveis ate a
# raiz - tests -> api -> apps -> raiz. `parents[2]` para em `apps/`, e foi o erro
# que `test_a_raiz_do_repositorio_esta_visivel` apanhou na primeira execucao.
RAIZ = Path(__file__).resolve().parents[3]
WORKFLOWS = RAIZ / ".github" / "workflows"

# Os workflows que resumem metrica de previsao. Se nascer um terceiro ambiente, ele
# entra aqui - e a lista explicita e' o que faz a omissao ser visivel.
DE_PREVISAO = ("forecast-staging.yml", "forecast-production.yml")

# A chave da metrica da media movel. Ela aparecer num workflow significa que a
# comparacao voltou a ser escrita la'.
CHAVE_DA_MEDIA_MOVEL = "wape_mensal_baseline_m28"


def test_a_raiz_do_repositorio_esta_visivel():
    """Se esta suite deixar de rodar num checkout completo, os testes abaixo viram
    falso positivo silencioso - e' o risco de afirmar coisas sobre arquivo distante."""
    assert WORKFLOWS.is_dir(), f"nao achei {WORKFLOWS} - a suite parou de ver a raiz"


@pytest.mark.parametrize("nome", DE_PREVISAO)
def test_o_workflow_existe(nome: str):
    """`forecast-production.yml` nasceu porque nao existia.

    Sem ele, `/power/demand/energy-forecast` respondia `disponivel: false` em producao:
    o pilar com modelo treinado nao aparecia no ambiente que representa o produto.
    """
    assert (WORKFLOWS / nome).is_file(), f"{nome} nao existe"


@pytest.mark.parametrize("nome", DE_PREVISAO)
def test_o_resumo_importa_o_portao(nome: str):
    """Ele decide pela funcao, e nao por uma comparacao propria."""
    texto = (WORKFLOWS / nome).read_text(encoding="utf-8")
    assert "from modelo.portao import" in texto, (
        f"{nome} nao importa o portao - a decisao do resumo pode divergir da do exportador"
    )


@pytest.mark.parametrize("nome", DE_PREVISAO)
def test_o_resumo_nao_cita_a_metrica_da_media_movel(nome: str):
    """A chave crua no YAML e' o sintoma da regra reescrita.

    Este e' o assert que teria pegado o defeito: ela estava la', e a comparacao com ela
    era a unica que o resumo fazia.
    """
    texto = (WORKFLOWS / nome).read_text(encoding="utf-8")
    assert CHAVE_DA_MEDIA_MOVEL not in texto, f"{nome} voltou a comparar so' com a media movel"


def test_producao_e_staging_leem_segredos_DIFERENTES():
    """Um copiar-e-colar que esquece o segredo escreveria previsao de producao no banco
    de staging - ou o contrario, que e' pior."""
    staging = (WORKFLOWS / "forecast-staging.yml").read_text(encoding="utf-8")
    producao = (WORKFLOWS / "forecast-production.yml").read_text(encoding="utf-8")
    assert "secrets.STAGING_DATABASE_URL" in staging
    assert "secrets.PRODUCTION_DATABASE_URL" in producao
    assert "secrets.STAGING_DATABASE_URL" not in producao
    assert "secrets.PRODUCTION_DATABASE_URL" not in staging


def test_os_dois_nao_compartilham_grupo_de_concorrencia():
    """Grupo igual faria o treino de um ambiente esperar pelo do outro sem razao.

    Grupo proprio por ambiente: dois treinos do MESMO ambiente ainda se serializam, que
    e' o que importa - eles gravam a mesma competencia.
    """
    staging = (WORKFLOWS / "forecast-staging.yml").read_text(encoding="utf-8")
    producao = (WORKFLOWS / "forecast-production.yml").read_text(encoding="utf-8")
    assert "group: staging-forecast" in staging
    assert "group: production-forecast" in producao


# Os dois passos que o gancho de historico acrescentou a `migrate-production.yml`, e
# que so' podem rodar por dispatch com a praca preenchida.
PASSOS_DO_HISTORICO = ("Install the whole package", "Generate history for one site")

# A condicao que os prende. Ela aparece nos DOIS passos, e foi por isso que a primeira
# versao destes testes era fraca: `"..." in texto` passava com um dos dois mutado.
GUARDA = "inputs.historico_praca != ''"


def _blocos_de_passo(texto: str) -> dict[str, str]:
    """O texto de cada passo, indexado pelo `name`.

    Divide em `- name:`, que e' como todo passo destes workflows comeca. Sem `pyyaml`
    de proposito: ele esta' instalado por transitividade, nao esta' no `pyproject`, e
    teste apoiado em acidente de resolucao de dependencia quebra sem avisar.
    """
    blocos = {}
    atual = None
    for linha in texto.splitlines():
        despida = linha.strip()
        if despida.startswith("- name:"):
            atual = despida.removeprefix("- name:").strip()
            blocos[atual] = ""
        elif atual is not None:
            blocos[atual] += linha + "\n"
    return blocos


def test_producao_pode_gerar_historico_por_dispatch():
    """Sem historico, `treinar.py` recusa e o job de previsao de producao fica vermelho.

    `migrate-staging.yml` ja' tinha esse gancho; producao nao, e era o que faltava para
    o ciclo fechar.

    O assert e' sobre a INVOCACAO, e nao sobre o nome do modulo: `"app.historico" in
    texto` sobrevivia a trocar o comando por um comentario que o cita - a mutacao
    mostrou isso.
    """
    texto = (WORKFLOWS / "migrate-production.yml").read_text(encoding="utf-8")
    assert "python -m app.historico" in texto, "producao nao tem como gerar historico"


def test_cada_passo_do_historico_exige_a_praca_preenchida():
    """Em branco, o workflow so' migra - senao ele geraria dado em todo push para main.

    Verifica CADA passo, e nao a presenca da condicao no arquivo: ela aparece nos dois,
    e a primeira versao deste teste passava com um deles desguardado.
    """
    blocos = _blocos_de_passo((WORKFLOWS / "migrate-production.yml").read_text(encoding="utf-8"))
    for nome in PASSOS_DO_HISTORICO:
        assert nome in blocos, f"o passo '{nome}' saiu de migrate-production.yml"
        assert GUARDA in blocos[nome], (
            f"o passo '{nome}' nao exige a praca preenchida - ele rodaria em todo push "
            "para main, gerando historico sem ninguem pedir"
        )
        assert "workflow_dispatch" in blocos[nome], (
            f"o passo '{nome}' nao esta' restrito a dispatch"
        )
