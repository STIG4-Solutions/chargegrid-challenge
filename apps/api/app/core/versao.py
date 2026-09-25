"""De qual commit e' o codigo que esta' respondendo.

POR QUE ISTO EXISTE. A validacao da Fase 1 custou meia hora para responder uma
pergunta que deveria custar um GET: producao servia 18 buckets no passado, e a
correcao que os elimina ja' estava mergeada. Nao havia como distinguir "o deploy
nao saiu" de "o deploy saiu e a correcao nao funciona" - foi preciso excluir
cache (`cf-cache-status`), frota mista (nove requisicoes seguidas identicas) e
comparar bytes de mensagem de aviso com staging para inferir, indiretamente, que
producao tinha o commit anterior. Um campo teria dito isso.

POR QUE NAO VAI NO `/health`. O repositorio e' PUBLICO e `/health` responde 200
sem token - conferido. Um SHA ali aponta qualquer pessoa para o codigo-fonte
exato em execucao, e a partir dele para o que ainda nao foi corrigido nele. Para
quem ja' e' admin da rede o mesmo campo nao revela nada de novo. Entao a rota e'
`/api/v1/infra/versao`, com `AdminUser`, e `test_o_health_nao_diz_o_commit`
impede que alguem mova o campo de volta por conveniencia.

A ORDEM DAS VARIAVEIS importa. `GITHUB_SHA` pode estar ASSADO na imagem, gravado
no build; `RENDER_GIT_COMMIT` e' injetado pela plataforma no processo que esta'
rodando agora. Quando as duas existem, a segunda e' a que responde a pergunta -
a primeira pode descrever um build que nao e' este.
"""

from __future__ import annotations

import os

# Na ordem de confianca: quem e' injetado em tempo de EXECUCAO vem antes de quem
# pode ter sido gravado em tempo de build.
VARIAVEIS: tuple[str, ...] = (
    "RENDER_GIT_COMMIT",  # a plataforma injeta sozinha, sem configurar nada
    "GIT_COMMIT",  # convencao generica, util em docker run local
    "SOURCE_COMMIT",  # builders no estilo Docker Hub
    "GITHUB_SHA",  # Actions; pode ser de build, por isso e' o ultimo
)

# Quando nenhuma esta' preenchida. E' uma string, e nao `None` silencioso, para
# que a resposta diga que NAO SABE em vez de omitir o campo - campo ausente se
# confunde com versao antiga da API, que e' exatamente a duvida a resolver.
DESCONHECIDO = "desconhecido"

# O tamanho do SHA curto que o `git log --oneline` usa. So' para leitura humana;
# o campo longo continua inteiro.
CURTO = 7


def commit_em_execucao(ambiente: dict[str, str] | None = None) -> tuple[str | None, str | None]:
    """O commit e a variavel que o forneceu, na ordem de `VARIAVEIS`.

    Devolve `(None, None)` quando nenhuma esta' preenchida. Variavel definida e
    VAZIA nao conta: um `GIT_COMMIT=` no compose e' ausencia, nao valor, e
    devolve-lo faria a rota afirmar que roda o commit de nome "".
    """
    amb = os.environ if ambiente is None else ambiente
    for nome in VARIAVEIS:
        valor = (amb.get(nome) or "").strip()
        if valor:
            return valor, nome
    return None, None
