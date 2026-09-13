"""Autenticacao e usuarios."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from app.models.enums import UserRole
from app.schemas.common import ORMModel


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RegistroPublicoIn(BaseModel):
    """Cadastro pelo app do motorista. Rota PUBLICA, sem token.

    NAO tem `role` nem `site_id`, e a ausencia dos dois e' a regra de seguranca -
    nao esquecimento. A rota fixa `role="driver"` no corpo da funcao, entao
    aceita-los aqui esta' seguro HOJE por causa de como a funcao foi escrita, e
    nao por causa do contrato. No dia em que alguem trocar a construcao
    explicita por `User(**payload.model_dump())` - que e' o idioma usado em
    `mobile.py:538` e `power.py:454` - vira escalacao de privilegio silenciosa:
    qualquer pessoa na internet criaria um admin.

    Quem cria operador e admin e' o admin da rede, por rota propria e
    autenticada.
    """

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8)
    phone: str | None = None
    document: str | None = None


class UserOut(ORMModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    phone: str | None
    document: str | None
    site_id: uuid.UUID | None
    wallet_balance: float
    # Conta corporativa. Sem estes na resposta o app nao tem como decidir se
    # mostra a aba de frota - e uma aba que so' devolve 403 e' pior que aba
    # nenhuma. Mesma classe do campo que o FastAPI descartava em silencio no
    # AllocationOut.
    fleet_id: uuid.UUID | None = None
    fleet_manager: bool = False
    created_at: datetime


class VehicleCreate(BaseModel):
    model: str = Field(max_length=80)
    plate: str | None = None
    vin: str | None = None
    battery_kwh: float | None = Field(default=None, ge=0)
    max_ac_kw: float | None = Field(default=None, ge=0)


class VehicleUpdate(BaseModel):
    """Atualizacao parcial: so o que vier no corpo e' alterado."""

    model: str | None = Field(default=None, max_length=80)
    plate: str | None = None
    vin: str | None = None
    battery_kwh: float | None = Field(default=None, ge=0)
    max_ac_kw: float | None = Field(default=None, ge=0)


class VehicleOut(ORMModel):
    id: uuid.UUID
    model: str
    plate: str | None
    vin: str | None
    battery_kwh: float | None
    max_ac_kw: float | None
    # Area responsavel pelo carro. O motorista comum ve (e' o carro dele), mas
    # so' o gestor altera.
    cost_center: str | None = None


class RfidCardCreate(BaseModel):
    uid: str = Field(min_length=4, max_length=14)
    label: str | None = None
    user_id: uuid.UUID | None = None
    tariff_id: uuid.UUID | None = None


class RfidCardOut(ORMModel):
    id: uuid.UUID
    uid: str
    label: str | None
    is_active: bool
    user_id: uuid.UUID | None
    tariff_id: uuid.UUID | None
    synced_to_hardware: bool


class WalletTopUpIn(BaseModel):
    """Corpo do credito na carteira.

    O valor era um parametro de query, e float. Dinheiro nao anda na URL - ela
    vaza para log de servidor, historico e referer - e todo o resto do dominio
    usa Decimal. Aqui ele volta a ser Decimal, com duas casas.
    """

    amount: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    idempotency_key: str | None = Field(default=None, max_length=80)


class PushDeviceIn(BaseModel):
    """Token do servico de push, entregue pelo aparelho no login.

    O token pertence ao aparelho, nao a pessoa: dois motoristas no mesmo
    celular emprestado precisam que o registro reaponte o dono, senao o
    segundo recebe as notificacoes do primeiro.
    """

    token: str = Field(min_length=8, max_length=200)
    platform: Literal["android", "ios"] = "android"


class ReporteIn(BaseModel):
    """Problema que o motorista viu no ponto.

    A categoria e' fechada de proposito: campo livre sozinho vira depoimento,
    e depoimento nao agrega - tres pessoas descrevendo o mesmo cabo rompido
    com palavras diferentes viram tres problemas num relatorio que deveria
    mostrar um.
    """

    categoria: Literal[
        "nao_inicia",
        "conector_travado",
        "cabo_danificado",
        "tela_apagada",
        "vaga_ocupada",
        "qr_ilegivel",
        "outro",
    ]
    descricao: str | None = Field(default=None, max_length=1000)
    session_id: uuid.UUID | None = None


class CentroDeCustoIn(BaseModel):
    """Vazio ou so' espacos limpa o centro de custo do veiculo."""

    centro_de_custo: str | None = Field(default=None, max_length=60)


class ContaNovaIn(BaseModel):
    """Conta de operacao criada por um admin da rede.

    Existe separada de `RegistroPublicoIn` porque as duas rotas respondem a
    perguntas opostas: aquela e' publica e NAO pode escolher papel; esta e'
    autenticada, restrita a admin, e escolher o papel e' a razao dela existir.
    Um schema so' para as duas obrigaria a rota publica a ignorar campos - que
    foi exatamente o arranjo fragil que a 0027 desfez.

    `role` nao aceita `driver`: motorista se cadastra sozinho pelo app, e criar
    um daqui produziria uma conta sem senha escolhida pelo dono dela.
    """

    email: EmailStr
    full_name: str = Field(min_length=2, max_length=160)
    password: str = Field(min_length=8)
    role: Literal["operator", "admin"]
    # Obrigatorio para operador, e a rota recusa sem ele. Nao e' burocracia:
    # `get_scoped_site_id` cai no PRIMEIRO site da rede quando nao ha `site_id`,
    # entao um operador sem praca nao fica sem acesso - fica com o acesso da
    # praca errada, em silencio.
    site_id: uuid.UUID | None = None


class ContaAtivaIn(BaseModel):
    """Ligar ou desligar uma conta. Nao ha apagar."""

    is_active: bool


class ContaOut(ORMModel):
    """O que a tela de contas mostra.

    Deliberadamente menos que `UserOut`: saldo de carteira, telefone e documento
    sao dados do MOTORISTA, e nao tem o que fazer numa tela sobre quem opera a
    rede. `last_login_at` entra porque e' a pergunta que essa tela responde e
    nenhuma outra - conta criada e nunca usada.

    Herda `ORMModel` para ENTRAR na guarda de `test_cobertura_de_schema`: aquela
    varredura so' enxerga subclasses de `ORMModel`, entao um schema de resposta
    em `BaseModel` escaparia tanto da tabela de omissoes quanto da checagem de
    campo sigiloso - e este aqui carrega colunas de `User`.
    """

    id: uuid.UUID
    email: EmailStr
    full_name: str
    role: UserRole
    is_active: bool
    site_id: uuid.UUID | None
    site_nome: str | None
    last_login_at: datetime | None
