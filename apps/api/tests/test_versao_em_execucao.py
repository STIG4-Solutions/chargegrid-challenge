"""`/infra/versao` responde as duas perguntas que a Fase 1 nao conseguiu fazer.

O EPISODIO. Producao devolvia 18 buckets no passado em
`/power/demand/energy-forecast/series`, e a correcao que os filtra ja' estava na
main. Tres explicacoes cabiam nos dados, e nenhuma rota as separava:

    1. o deploy nao tinha saido
    2. o deploy tinha saido e o `now()` do BANCO estava horas atras
    3. a correcao estava errada

Excluir (1) exigiu comparar bytes de mensagens de aviso com staging; (2) ficou
sem poder ser excluida, porque nenhuma rota de leitura expoe um carimbo
preenchido pelo banco. Esta rota responde as duas em um GET.

O COMMIT NAO VAI NO `/health`. O repositorio e' publico e `/health` responde 200
sem token. `test_o_health_continua_sem_dizer_o_commit` e' o que impede o campo de
migrar para la' por conveniencia de quem nao tem token de admin a mao.
"""

from __future__ import annotations

import pytest
from sqlalchemy import func, select

from app.core.versao import DESCONHECIDO, VARIAVEIS, commit_em_execucao

URL = "/api/v1/infra/versao"

# Um valor que nao aparece por acaso em resposta nenhuma - e' o que torna o
# assert de ausencia no `/health` confiavel.
SENTINELA = "0123456789abcdef0123456789abcdef01234567"


@pytest.fixture
def sem_commit_no_ambiente(monkeypatch):
    """Apaga TODAS as variaveis de `VARIAVEIS`.

    O CI e' GitHub Actions, que define `GITHUB_SHA` sozinho: sem isto, os testes
    de ausencia passariam na minha maquina e falhariam la' - ou, pior, o de
    presenca passaria sem que o monkeypatch tivesse efeito nenhum.
    """
    for nome in VARIAVEIS:
        monkeypatch.delenv(nome, raising=False)


def test_a_ordem_prefere_o_que_a_plataforma_injeta():
    """`GITHUB_SHA` pode estar assado na imagem; `RENDER_GIT_COMMIT`, nao.

    Quando as duas existem, so' a segunda descreve o processo que esta' rodando.
    Inverter a ordem de `VARIAVEIS` faria a rota afirmar com confianca o commit
    do BUILD - que e' o erro mais caro possivel numa rota cuja unica funcao e'
    dizer qual codigo responde.
    """
    sha, origem = commit_em_execucao({"GITHUB_SHA": "do-build", "RENDER_GIT_COMMIT": "do-processo"})
    assert (sha, origem) == ("do-processo", "RENDER_GIT_COMMIT")


def test_variavel_definida_e_vazia_e_ausencia():
    """`GIT_COMMIT=` num compose e' ausencia, nao valor.

    Sem o `.strip()`, a rota anunciaria rodar o commit de nome "" - e um campo
    preenchido com vazio le'-se como resposta, nao como falta dela.
    """
    assert commit_em_execucao({"GIT_COMMIT": "   "}) == (None, None)
    assert commit_em_execucao({"GIT_COMMIT": "", "SOURCE_COMMIT": "vale"}) == (
        "vale",
        "SOURCE_COMMIT",
    )


def test_sem_variavel_nenhuma_ele_nao_inventa():
    assert commit_em_execucao({}) == (None, None)


async def test_a_rota_diz_o_commit_e_de_onde_ele_veio(
    api, como_admin, monkeypatch, sem_commit_no_ambiente
):
    monkeypatch.setenv("RENDER_GIT_COMMIT", SENTINELA)
    corpo = (await api.get(URL, headers=como_admin)).json()
    assert corpo["commit"] == SENTINELA
    assert corpo["commit_curto"] == SENTINELA[:7]
    # A origem e' metade da resposta: um SHA sem ela nao distingue build de
    # execucao, que e' justamente a duvida.
    assert corpo["commit_origem"] == "RENDER_GIT_COMMIT"


async def test_sem_variavel_a_rota_diz_que_NAO_SABE(api, como_admin, sem_commit_no_ambiente):
    """Campo ausente se confundiria com API velha, que e' a propria duvida."""
    corpo = (await api.get(URL, headers=como_admin)).json()
    assert corpo["commit"] == DESCONHECIDO
    assert corpo["commit_origem"] is None


async def test_o_relogio_vem_do_BANCO_e_nao_do_PROCESSO(api, como_admin, db):
    """O assert decisivo, e ele se apoia numa propriedade do Postgres.

    `now()` e' estavel dentro da TRANSACAO: chamado duas vezes na mesma, devolve
    o mesmo instante. A rota roda na transacao deste teste (o `api` sobrescreve
    `get_db` com esta sessao), entao o valor tem de bater EXATAMENTE com o que
    se le' aqui.

    Trocar `select(func.now())` por `datetime.now(timezone.utc)` - a simplifica-
    cao obvia - nunca produz igualdade exata com um valor lido microssegundos
    antes. E' o que faz este teste medir a origem do numero, e nao so' que ha'
    um numero.
    """
    do_banco = (await db.execute(select(func.now()))).scalar_one()
    corpo = (await api.get(URL, headers=como_admin)).json()
    assert corpo["banco_agora"] == do_banco.isoformat()
    assert corpo["api_agora"] != corpo["banco_agora"]


async def test_o_desvio_e_a_diferenca_entre_os_dois(api, como_admin):
    """Positivo = banco atrasado. O sinal e' o que se le' na hora do incidente."""
    from datetime import datetime

    corpo = (await api.get(URL, headers=como_admin)).json()
    esperado = (
        datetime.fromisoformat(corpo["api_agora"]) - datetime.fromisoformat(corpo["banco_agora"])
    ).total_seconds()
    assert corpo["desvio_s"] == pytest.approx(esperado, abs=1e-3)


async def test_so_admin_ve(api, como_operador, como_motorista):
    """O commit conta a quem o le' qual codigo-fonte publico esta' em execucao.

    O operador ja' e' barrado por papel; o motorista tambem. Sem token e' 401.
    """
    assert (await api.get(URL, headers=como_operador)).status_code == 403
    assert (await api.get(URL, headers=como_motorista)).status_code == 403
    assert (await api.get(URL)).status_code == 401


async def test_o_health_continua_sem_dizer_o_commit(api, monkeypatch, sem_commit_no_ambiente):
    """A guarda de exposicao, e ela e' comportamental.

    Com a variavel preenchida, o `/health` SEM TOKEN nao pode conter o valor em
    lugar nenhum da resposta. Acrescentar o commit la' - que era a primeira
    ideia - faz este teste ficar vermelho.
    """
    monkeypatch.setenv("RENDER_GIT_COMMIT", SENTINELA)
    resposta = await api.get("/health")
    assert resposta.status_code == 200, "o /health deixou de ser publico"
    assert SENTINELA not in resposta.text, "o commit vazou para uma rota sem autenticacao"
