"""Contratos de campanha, missao e recompensa.

Duas leituras muito diferentes saem das mesmas tabelas, e por isso ha dois
conjuntos de schema.

O OPERADOR ve a campanha como instrumento comercial: quanto ela custa, quanto ja
consumiu, quantas pessoas alcancou. Ele precisa dos numeros de dinheiro.

O MOTORISTA ve a missao como jogo: onde ele esta, quanto falta, o que ganha. Ele
nao precisa saber o orcamento de ninguem - e expor isso vazaria a estrategia
comercial do estabelecimento para quem carrega la.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.models.campaign import BENEFICIOS, JANELAS, METRICAS, PATROCINADORES
from app.schemas.common import ORMModel


class MissaoIn(BaseModel):
    codigo: str = Field(max_length=40)
    titulo: str = Field(max_length=120)
    descricao: str | None = None
    metrica: str
    alvo: float = Field(gt=0)
    janela: str = "campanha"
    ordem: int = 0
    repetivel: bool = False

    @model_validator(mode="after")
    def _listas_fechadas(self):
        # A mesma lista que o check constraint usa. Validar aqui devolve 422 com
        # a explicacao; deixar chegar ao banco devolveria 500 com um nome de
        # constraint que nao diz nada a quem preenche o formulario.
        if self.metrica not in METRICAS:
            raise ValueError(f"metrica deve ser uma de: {', '.join(METRICAS)}")
        if self.janela not in JANELAS:
            raise ValueError(f"janela deve ser uma de: {', '.join(JANELAS)}")
        return self


class MissaoOut(ORMModel):
    id: uuid.UUID
    codigo: str
    titulo: str
    descricao: str | None
    metrica: str
    alvo: float
    janela: str
    ordem: int
    repetivel: bool


class CampanhaIn(BaseModel):
    nome: str = Field(max_length=120)
    descricao: str | None = None
    patrocinador: str = "rede"
    # Para QUEM vale, e nao quem paga. Diferente de `site_id`, este campo pode
    # vir do corpo: restringir a quem a campanha se aplica nao custa nada a
    # frota, enquanto escolher o site custaria a margem do vizinho.
    fleet_id: uuid.UUID | None = None
    # Nao ha `site_id` aqui de proposito. Quem paga vem do ESCOPO do token, nunca
    # do corpo: um campo aceito no payload deixaria um operador criar campanha
    # bancada pelo vizinho. A rota preenche a partir de `ScopedSiteId`, e pedir o
    # valor aqui so' criaria um campo que o servidor descarta - contrato que
    # mente sobre o que aceita.
    starts_at: datetime
    ends_at: datetime
    ativa: bool = True
    beneficio_tipo: str
    beneficio_valor: float = Field(gt=0)
    teto_por_recompensa: float | None = Field(default=None, gt=0)
    orcamento_brl: float = Field(default=0, ge=0)
    limite_por_motorista: int | None = Field(default=None, gt=0)
    missoes: list[MissaoIn] = []

    @model_validator(mode="after")
    def _coerencia(self):
        if self.patrocinador not in PATROCINADORES:
            raise ValueError(f"patrocinador deve ser um de: {', '.join(PATROCINADORES)}")
        if self.beneficio_tipo not in BENEFICIOS:
            raise ValueError(f"beneficio_tipo deve ser um de: {', '.join(BENEFICIOS)}")
        if self.ends_at <= self.starts_at:
            raise ValueError("o fim da campanha precisa ser depois do inicio")

        # Missao so' faz sentido com cashback: desconto age na propria fatura, na
        # hora, sem nada a acumular. Aceitar as duas coisas juntas criaria uma
        # campanha cujas missoes nunca premiam ninguem.
        if self.missoes and not self.beneficio_tipo.startswith("cashback"):
            raise ValueError("missoes exigem beneficio do tipo cashback")
        if self.beneficio_tipo.startswith("cashback") and not self.missoes:
            raise ValueError("campanha de cashback precisa de pelo menos uma missao")
        if self.teto_por_recompensa and self.orcamento_brl:
            if self.teto_por_recompensa > self.orcamento_brl:
                raise ValueError("o teto por recompensa nao pode passar do orcamento")

        codigos = [m.codigo for m in self.missoes]
        if len(codigos) != len(set(codigos)):
            raise ValueError("ha missoes com o mesmo codigo")
        return self


class CampanhaOut(ORMModel):
    """Visao do operador: inclui o dinheiro."""

    id: uuid.UUID
    nome: str
    descricao: str | None
    patrocinador: str
    site_id: uuid.UUID | None
    fleet_id: uuid.UUID | None
    starts_at: datetime
    ends_at: datetime
    ativa: bool
    beneficio_tipo: str
    beneficio_valor: float
    teto_por_recompensa: float | None
    orcamento_brl: float
    consumido_brl: float
    limite_por_motorista: int | None
    # `validation_alias`, e nao `alias`. O relacionamento do modelo chama-se
    # `missions` e a tela le `missoes`; com `alias` os dois lados mudam de nome,
    # e como o FastAPI serializa com `by_alias=True` por padrao a resposta saia
    # com a chave `missions` - o campo simplesmente sumia da tela.
    missoes: list[MissaoOut] = Field(default_factory=list, validation_alias="missions")

    model_config = {"from_attributes": True, "populate_by_name": True}


class DesempenhoOut(BaseModel):
    """O que o operador precisa para decidir se a campanha vale.

    Sem `motoristas_alcancados` e `concluidas`, "consumido_brl" sozinho nao diz
    se o dinheiro comprou comportamento ou so' saiu do caixa.
    """

    campanha_id: uuid.UUID
    nome: str
    motoristas_alcancados: int
    missoes_concluidas: int
    recompensas_creditadas: int
    consumido_brl: float
    orcamento_brl: float
    orcamento_disponivel: float
    percentual_consumido: float


class MissaoDoMotoristaOut(BaseModel):
    """Visao do motorista: sem numero de orcamento.

    Expor `orcamento_brl` aqui vazaria a estrategia comercial do estabelecimento
    para quem carrega nele.
    """

    id: uuid.UUID
    codigo: str
    titulo: str
    descricao: str | None
    metrica: str
    alvo: float
    janela: str
    progresso: float
    concluida: bool
    concluida_em: datetime | None
    periodo: date | None
    campanha: str
    recompensa: str


class RecompensaOut(ORMModel):
    id: uuid.UUID
    campanha: str
    valor_brl: float
    estado: str
    tipo: str
    created_at: datetime
