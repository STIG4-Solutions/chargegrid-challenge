"""Trilha de auditoria: quem fez o que, com dinheiro e com permissao.

`audit_logs` existe desde a migration `0001` - com ator, acao, entidade, antes,
depois e IP - e NADA nunca gravou uma linha. Uma tabela de auditoria vazia e'
pior que nenhuma: ela da a impressao de que ha rastro, e a pergunta so' aparece
no dia em que alguem precisa dele.

O QUE ENTRA, e a regra e' curta: acao de PESSOA que move dinheiro ou muda quem
pode o que. Fora disso e' ruido, e auditoria com ruido e' auditoria que ninguem
le.

  - move dinheiro: ajuste de carteira, estorno, baixa de cobranca da plataforma,
    cobranca de fatura;
  - muda o comercial: contratar e rescindir plano da plataforma, criar e
    encerrar campanha;
  - muda quem pode o que: metodo de pagamento do site, que carrega a credencial
    do PSP.

O QUE NAO ENTRA, de proposito:

  - o que o WORKER faz sozinho. Cashback concedido, mensalidade cobrada,
    cobranca vencida - sao consequencias de regra, nao decisoes de alguem. Ja
    tem log estruturado e linha propria no razao; repetir aqui encheria a
    tabela de linhas sem ator, que e' exatamente o que ela nao serve para
    guardar;
  - leitura. Auditar consulta transforma a tabela num log de acesso e afoga o
    que importa.

POR QUE NA ROTA, e nao no servico. O ator e o IP so' existem na borda HTTP, e o
mesmo servico e' chamado pelo worker - `_creditar` roda nos dois. Auditar
dentro do servico gravaria linha sem ator toda vez que o worker passasse.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.models.user import User

# Chaves cujo VALOR nunca vai para a tabela, casadas por pedaco do nome.
#
# `provider_config` do metodo de pagamento carrega `client_secret` e
# `webhook_secret`; auditar o "antes e depois" sem isto escreveria a credencial
# do PSP numa tabela que existe justamente para ser lida por gente. Auditoria
# que vaza segredo e' um segundo problema, nao meia solucao do primeiro.
SIGILOSAS = ("secret", "senha", "password", "token", "chave_privada", "authorization")

MASCARA = "***"


def esconder(valor: Any) -> Any:
    """Devolve a estrutura com os valores sigilosos trocados por `***`.

    Recursivo porque `provider_config` e' um dicionario dentro do corpo, e uma
    versao que so' olhasse o primeiro nivel deixaria passar exatamente o caso
    que motivou a funcao.
    """
    if isinstance(valor, dict):
        return {
            k: MASCARA if any(s in k.lower() for s in SIGILOSAS) else esconder(v)
            for k, v in valor.items()
        }
    if isinstance(valor, list):
        return [esconder(v) for v in valor]
    return valor


async def registrar(
    db: AsyncSession,
    *,
    ator: User | None,
    ip: str | None,
    acao: str,
    entidade: str,
    entidade_id: Any = None,
    antes: dict | None = None,
    depois: dict | None = None,
) -> AuditLog:
    """Grava a linha. NAO commita.

    Sem commit proprio de propósito: a auditoria entra na MESMA transacao da
    operacao auditada. Ou as duas acontecem, ou nenhuma - uma trilha que
    registra o que foi desfeito por rollback mente, e uma que perde o registro
    de algo que aconteceu mente igual.

    `actor_email` fica gravado alem do `actor_id` porque a FK e' SET NULL: a
    conta apagada leva o id junto, e sem o e-mail a linha vira "alguem fez".
    """
    linha = AuditLog(
        occurred_at=datetime.now(UTC),
        actor_id=ator.id if ator else None,
        actor_email=ator.email if ator else None,
        action=acao,
        entity_type=entidade,
        entity_id=str(entidade_id) if entidade_id is not None else None,
        before=esconder(antes or {}),
        after=esconder(depois or {}),
        ip_address=ip,
    )
    db.add(linha)
    await db.flush()
    return linha


async def listar(
    db: AsyncSession, *, limite: int = 100, acao: str | None = None, entidade: str | None = None
) -> list[dict]:
    """As ultimas linhas, do mais novo ao mais antigo.

    Uma trilha que ninguem consegue ler e' meio caminho do defeito que ela veio
    consertar - o dado existiria no banco e a pergunta continuaria dependendo de
    alguem com acesso a producao.
    """
    consulta = select(AuditLog).order_by(AuditLog.occurred_at.desc()).limit(limite)
    if acao:
        consulta = consulta.where(AuditLog.action == acao)
    if entidade:
        consulta = consulta.where(AuditLog.entity_type == entidade)

    return [
        {
            "id": str(linha.id),
            "quando": linha.occurred_at.isoformat(),
            "quem": linha.actor_email,
            "quem_id": str(linha.actor_id) if linha.actor_id else None,
            "acao": linha.action,
            "entidade": linha.entity_type,
            "entidade_id": linha.entity_id,
            "antes": linha.before,
            "depois": linha.after,
            "ip": linha.ip_address,
        }
        for linha in (await db.execute(consulta)).scalars().all()
    ]


__all__ = ["esconder", "listar", "registrar"]
