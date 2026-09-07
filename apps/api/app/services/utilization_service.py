"""Ocupacao e retorno por ponto de recarga.

O painel de estado responde "o ponto esta carregando?". Este modulo responde
duas perguntas que decidem investimento:

  este ponto se paga? - receita por hora que ele esteve realmente disponivel.
  Um ponto caro num canto sem movimento e capital parado; o operador so
  descobre isso comparando pontos lado a lado.

  este ponto esta sendo desperdicado? - ocupacao alta nao e sinonimo de
  faturamento. Um carro que termina de carregar e fica plugado ocupa o
  conector sem consumir: o ponto aparece 90% ocupado e fatura como se
  estivesse 40%. `charging_sessions.idle_minutes` separa os dois casos, e e'
  essa separacao que justifica cobrar taxa de ociosidade - ou nao cobrar,
  quando o problema e' falta de ponto e nao ma-fe do motorista.

Denominador honesto: horas em que o ponto podia atender. Um ponto que passou
tres dias em falha terminal nao estava "80% ocioso", estava quebrado. As
janelas de falha vem de charge_point_faults e saem da conta - senao a metrica
pune o ponto defeituoso duas vezes e esconde a manutencao atrasada.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charge_point import ChargePoint, ChargePointFault
from app.models.enums import SessionState
from app.models.session import ChargingSession
from app.models.site import Site

# Sessoes que ja entregaram (ou tentaram entregar) energia. AUTHORIZING e QUEUED
# nao ocupam o conector: a primeira ainda esta validando o cartao, a segunda
# espera vaga. Conta-las inflaria a ocupacao com tempo que o ponto estava livre.
ESTADOS_QUE_OCUPAM = {
    SessionState.STARTING,
    SessionState.CHARGING,
    SessionState.SUSPENDED,
    SessionState.FINISHING,
    SessionState.FINISHED,
    SessionState.BILLED,
}

# Acima disto o ponto vive cheio e esta recusando cliente - sinal de que falta
# ponto, nao de que sobra. Abaixo do piso, o ponto nao se paga.
OCUPACAO_CONGESTIONADO = 0.70
OCUPACAO_OCIOSO = 0.15

# Fracao do tempo ocupado em que o carro estava plugado sem consumir. Acima
# disto o conector esta sendo usado como vaga de estacionamento.
OCIOSIDADE_PREOCUPANTE = 0.30


def _mescla(janelas: list[tuple[datetime, datetime]]) -> list[tuple[datetime, datetime]]:
    """Une intervalos que se sobrepoem.

    Duas falhas simultaneas no mesmo ponto (a trava e o medidor, digamos) sao
    dois episodios cobrindo o mesmo periodo. Somar as duracoes contaria o mesmo
    tempo parado duas vezes e podia zerar - ou negativar - as horas disponiveis.
    """
    if not janelas:
        return []
    ordenadas = sorted(janelas)
    unidas = [ordenadas[0]]
    for inicio, fim in ordenadas[1:]:
        ultimo_inicio, ultimo_fim = unidas[-1]
        if inicio <= ultimo_fim:
            unidas[-1] = (ultimo_inicio, max(ultimo_fim, fim))
        else:
            unidas.append((inicio, fim))
    return unidas


@dataclass
class PontoUtilizado:
    charge_point_id: str
    code: str
    name: str
    rated_kw: float

    sessoes: int = 0
    energia_kwh: float = 0.0
    receita_brl: float = 0.0
    horas_ocupadas: float = 0.0
    horas_ociosas: float = 0.0
    horas_indisponiveis: float = 0.0
    horas_da_janela: float = 0.0

    @property
    def horas_disponiveis(self) -> float:
        """Horas em que o ponto podia atender. Nunca negativa."""
        return max(0.0, self.horas_da_janela - self.horas_indisponiveis)

    @property
    def ocupacao(self) -> float:
        base = self.horas_disponiveis
        if base <= 0:
            return 0.0
        # Um ponto pode ter ficado ocupado durante a propria falha (a sessao
        # travou junto). Sem o teto, a razao passava de 1 e virava "130% ocupado".
        return min(1.0, self.horas_ocupadas / base)

    @property
    def ociosidade(self) -> float:
        if self.horas_ocupadas <= 0:
            return 0.0
        return min(1.0, self.horas_ociosas / self.horas_ocupadas)

    @property
    def receita_por_hora_disponivel(self) -> float:
        base = self.horas_disponiveis
        return self.receita_brl / base if base > 0 else 0.0

    @property
    def classificacao(self) -> str:
        """Rotulo que diz ao operador o que fazer com este ponto."""
        if self.horas_disponiveis <= 0:
            return "indisponivel"
        if self.ociosidade >= OCIOSIDADE_PREOCUPANTE:
            return "bloqueado"
        if self.ocupacao >= OCUPACAO_CONGESTIONADO:
            return "congestionado"
        if self.ocupacao <= OCUPACAO_OCIOSO:
            return "ocioso"
        return "saudavel"

    def as_dict(self) -> dict:
        return {
            "charge_point_id": self.charge_point_id,
            "code": self.code,
            "name": self.name,
            "rated_kw": round(self.rated_kw, 2),
            "sessoes": self.sessoes,
            "energia_kwh": round(self.energia_kwh, 2),
            "receita_brl": round(self.receita_brl, 2),
            "horas_ocupadas": round(self.horas_ocupadas, 1),
            "horas_ociosas": round(self.horas_ociosas, 1),
            "horas_indisponiveis": round(self.horas_indisponiveis, 1),
            "horas_disponiveis": round(self.horas_disponiveis, 1),
            "ocupacao_pct": round(self.ocupacao * 100, 1),
            "ociosidade_pct": round(self.ociosidade * 100, 1),
            "receita_por_hora_brl": round(self.receita_por_hora_disponivel, 2),
            "energia_por_sessao_kwh": (
                round(self.energia_kwh / self.sessoes, 2) if self.sessoes else 0.0
            ),
            "classificacao": self.classificacao,
        }


@dataclass
class RelatorioDeUtilizacao:
    dias: int
    pontos: list[PontoUtilizado] = field(default_factory=list)
    horas_da_janela: float = 0.0

    def as_dict(self) -> dict:
        ordenados = sorted(
            self.pontos, key=lambda p: p.receita_por_hora_disponivel, reverse=True
        )
        receita = sum(p.receita_brl for p in self.pontos)
        energia = sum(p.energia_kwh for p in self.pontos)
        ocupadas = sum(p.horas_ocupadas for p in self.pontos)
        disponiveis = sum(p.horas_disponiveis for p in self.pontos)
        ociosas = sum(p.horas_ociosas for p in self.pontos)

        return {
            "dias": self.dias,
            # Janela realmente coberta. Menor que `dias` num site recem-instalado,
            # e e' ela que o painel deve mostrar - senao anuncia 30 dias de
            # historico que nao existem.
            "horas_da_janela": round(self.horas_da_janela, 1),
            "dias_efetivos": round(self.horas_da_janela / 24.0, 2),
            "janela_completa": self.horas_da_janela >= self.dias * 24 - 1,
            "pontos": [p.as_dict() for p in ordenados],
            "receita_total_brl": round(receita, 2),
            "energia_total_kwh": round(energia, 2),
            "sessoes_total": sum(p.sessoes for p in self.pontos),
            "ocupacao_media_pct": (
                round(min(1.0, ocupadas / disponiveis) * 100, 1) if disponiveis > 0 else 0.0
            ),
            # Receita que a ociosidade custou, na tarifa media do proprio site.
            # Nao e' projecao: e' hora de conector que ja foi paga pelo operador
            # (em demanda contratada e capital imobilizado) e nao vendeu energia.
            "horas_ociosas_total": round(ociosas, 1),
            "receita_perdida_por_ociosidade_brl": (
                round((receita / ocupadas) * ociosas, 2) if ocupadas > 0 else 0.0
            ),
            "melhor": ordenados[0].code if ordenados else None,
            "pior": ordenados[-1].code if ordenados else None,
        }


async def ocupacao_por_ponto(
    db: AsyncSession, site_id: uuid.UUID, *, dias: int = 30, agora: datetime | None = None
) -> dict:
    """Ocupacao, receita e ociosidade de cada ponto do site na janela pedida."""
    agora = agora or datetime.now(UTC)
    desde = agora - timedelta(days=dias)

    # A janela nao pode ser maior que a idade do proprio site. Pedir 30 dias de
    # um site instalado ha duas horas dava um denominador de 720 h contra duas
    # horas de operacao: todo ponto saia "ocioso" - nao porque falta procura,
    # mas porque a conta cobrava dele 29 dias em que ele nao existia. O mesmo
    # erro de amostra fina que marca o simulador de contrato como nao confiavel.
    # Idade honesta: a mais antiga entre o cadastro do site e a primeira sessao
    # registrada. So o created_at bastaria se todo site nascesse vazio - mas um
    # site migrado de outro sistema tem sessoes anteriores a propria linha, e
    # nesse caso o cadastro subestimaria o historico disponivel.
    nascimento = (
        await db.execute(select(Site.created_at).where(Site.id == site_id))
    ).scalar_one_or_none()
    primeira_sessao = (
        await db.execute(
            select(func.min(ChargingSession.started_at)).where(
                ChargingSession.site_id == site_id
            )
        )
    ).scalar_one_or_none()
    marcos = [m for m in (nascimento, primeira_sessao) if m is not None]
    inicio = max(desde, min(marcos)) if marcos else desde
    horas_da_janela = max(0.0, (agora - inicio).total_seconds() / 3600.0)

    pontos = (
        (
            await db.execute(
                select(ChargePoint)
                .where(ChargePoint.site_id == site_id)
                .order_by(ChargePoint.code)
            )
        )
        .scalars()
        .all()
    )
    if not pontos:
        return RelatorioDeUtilizacao(dias=dias, horas_da_janela=horas_da_janela).as_dict()

    por_id = {
        str(cp.id): PontoUtilizado(
            charge_point_id=str(cp.id),
            code=cp.code,
            name=cp.name,
            rated_kw=float(cp.rated_kw),
            horas_da_janela=horas_da_janela,
        )
        for cp in pontos
    }

    sessoes = (
        (
            await db.execute(
                select(ChargingSession).where(
                    ChargingSession.site_id == site_id,
                    ChargingSession.state.in_(ESTADOS_QUE_OCUPAM),
                    ChargingSession.started_at.is_not(None),
                    ChargingSession.started_at >= desde,
                )
            )
        )
        .scalars()
        .all()
    )
    for s in sessoes:
        alvo = por_id.get(str(s.charge_point_id))
        if alvo is None:
            continue
        alvo.sessoes += 1
        alvo.energia_kwh += float(s.energy_kwh or 0)
        alvo.receita_brl += float(s.estimated_cost or 0)
        # Sessao ainda aberta conta ate agora: ignorar o tempo ja corrido faria
        # o ponto mais movimentado do site parecer o mais vazio.
        fim = s.ended_at or agora
        ocupado_s = s.duration_s or max(0.0, (fim - s.started_at).total_seconds())
        alvo.horas_ocupadas += ocupado_s / 3600.0
        alvo.horas_ociosas += (s.idle_minutes or 0) / 60.0

    falhas = (
        (
            await db.execute(
                select(ChargePointFault)
                .join(ChargePoint, ChargePoint.id == ChargePointFault.charge_point_id)
                .where(
                    ChargePoint.site_id == site_id,
                    ChargePointFault.terminal.is_(True),
                    ChargePointFault.last_seen_at >= desde,
                )
            )
        )
        .scalars()
        .all()
    )
    janelas: dict[str, list[tuple[datetime, datetime]]] = {}
    for f in falhas:
        # Recorta a janela: uma falha que comecou antes do periodo so conta o
        # pedaco dentro dele. Episodio aberto (resolved_at nulo) corre ate agora.
        inicio = max(f.first_seen_at, desde)
        fim = min(f.resolved_at or agora, agora)
        if fim > inicio:
            janelas.setdefault(str(f.charge_point_id), []).append((inicio, fim))

    for cp_id, intervalos in janelas.items():
        alvo = por_id.get(cp_id)
        if alvo is None:
            continue
        alvo.horas_indisponiveis = sum(
            (fim - inicio).total_seconds() / 3600.0 for inicio, fim in _mescla(intervalos)
        )

    return RelatorioDeUtilizacao(
        dias=dias, pontos=list(por_id.values()), horas_da_janela=horas_da_janela
    ).as_dict()
