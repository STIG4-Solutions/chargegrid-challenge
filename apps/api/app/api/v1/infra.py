"""As duas perguntas que a validacao de um deploy faz, numa requisicao so'.

QUAL CODIGO ESTA' RODANDO e QUE HORAS SAO PARA O BANCO. Sao as duas que a
apuracao da Fase 1 nao conseguiu responder, e as duas respostas juntas separam
as tres explicacoes possiveis para "a rota devolve periodo que ja' passou":

    commit antigo          -> o deploy nao saiu; nada a investigar no codigo
    commit novo, relogios  -> o deploy saiu, o filtro esta' la', e o `now()` do
      distantes               banco e' que esta' atrasado
    commit novo, relogios  -> e' defeito de verdade, e ai' vale abrir o codigo
      juntos

O relogio do BANCO e nao o do processo porque e' o `now()` do Postgres que
decide o filtro de `previsao_em_serie` - `SiteForecast.bucket_inicio > func.now()`
roda no servidor. Nenhuma rota de leitura expunha um carimbo preenchido pelo
banco (`created_at` e `updated_at` tem `server_default`, mas nao sao serializados
em lugar nenhum), e foi por isso que essa hipotese ficou sem poder ser excluida.

TUDO AQUI E' DE ADMIN. Ver a versao deste modulo em `app/core/versao.py`.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter
from sqlalchemy import func, select

from app.core.config import settings
from app.core.deps import AdminUser, DbSession
from app.core.versao import CURTO, DESCONHECIDO, commit_em_execucao

router = APIRouter(prefix="/infra", tags=["infra"])


@router.get("/versao")
async def versao(db: DbSession, _: AdminUser) -> dict:
    """Que commit responde, e o quanto o relogio do banco difere do da API.

    `desvio_s` e' POSITIVO quando o banco esta' ATRASADO em relacao ao processo.
    Alguns segundos sao latencia da propria consulta; horas sao o defeito que
    esta rota existe para tornar visivel.
    """
    banco_agora: datetime = (await db.execute(select(func.now()))).scalar_one()
    api_agora = datetime.now(UTC)

    commit, origem = commit_em_execucao()
    return {
        "env": settings.env,
        "commit": commit or DESCONHECIDO,
        "commit_curto": commit[:CURTO] if commit else DESCONHECIDO,
        # Qual variavel respondeu. Sem isso, um SHA assado na imagem e um
        # injetado pela plataforma sao indistinguiveis - e so' o segundo prova
        # que o processo ATUAL e' daquele commit.
        "commit_origem": origem,
        "api_agora": api_agora.isoformat(),
        "banco_agora": banco_agora.isoformat(),
        "desvio_s": round((api_agora - banco_agora).total_seconds(), 3),
    }
