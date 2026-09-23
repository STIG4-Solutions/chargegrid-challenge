"""Visao de rede: as pracas lado a lado.

Todo o resto do sistema opera dentro de um site - e assim que o operador
trabalha, e e assim que o isolamento multi-tenant se sustenta. Mas quem
administra a rede tem uma pergunta que nenhuma tela de site responde: qual
praca esta segurando a operacao, e para onde vai o proximo ponto?

Comparar sites exige cuidado com a base. Uma praca com dez pontos fatura mais
que uma com dois quase por definicao; o que diz se ela vai bem e a receita por
ponto e a ocupacao, nao o total. Por isso o ranking desta tela e por receita
por ponto - o total continua visivel, ao lado, para nao esconder a escala.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.charge_point import ChargePoint, ChargePointFault
from app.models.enums import ACTIVE_SESSION_STATES, ChargePointStatus, SessionState
from app.models.session import ChargingSession
from app.models.site import Site

# Estados que representam energia efetivamente entregue (ou em entrega). Os
# mesmos de utilization_service: contar AUTHORIZING como receita somaria
# tentativa de cartao recusado ao faturamento.
ESTADOS_FATURAVEIS = {
    SessionState.CHARGING,
    SessionState.SUSPENDED,
    SessionState.FINISHING,
    SessionState.FINISHED,
    SessionState.BILLED,
}


@dataclass
class SiteNaRede:
    site_id: str
    nome: str
    cidade: str | None
    estado: str | None
    timezone: str

    pontos: int = 0
    pontos_disponiveis: int = 0
    pontos_em_falha: int = 0
    sessoes_ativas: int = 0

    grid_limit_kw: float = 0.0
    sessoes: int = 0
    energia_kwh: float = 0.0
    receita_brl: float = 0.0
    falhas_abertas: int = 0

    @property
    def receita_por_ponto(self) -> float:
        """A metrica que permite comparar pracas de tamanhos diferentes."""
        return self.receita_brl / self.pontos if self.pontos else 0.0

    @property
    def disponibilidade(self) -> float:
        """Fracao dos pontos que nao esta em falha nem offline."""
        if not self.pontos:
            return 0.0
        return max(0.0, (self.pontos - self.pontos_em_falha) / self.pontos)

    def as_dict(self) -> dict:
        return {
            "site_id": self.site_id,
            "nome": self.nome,
            "cidade": self.cidade,
            "estado": self.estado,
            "timezone": self.timezone,
            "pontos": self.pontos,
            "pontos_disponiveis": self.pontos_disponiveis,
            "pontos_em_falha": self.pontos_em_falha,
            "sessoes_ativas": self.sessoes_ativas,
            "grid_limit_kw": round(self.grid_limit_kw, 1),
            "sessoes": self.sessoes,
            "energia_kwh": round(self.energia_kwh, 2),
            "receita_brl": round(self.receita_brl, 2),
            "receita_por_ponto_brl": round(self.receita_por_ponto, 2),
            "falhas_abertas": self.falhas_abertas,
            "disponibilidade_pct": round(self.disponibilidade * 100, 1),
        }


async def visao_da_rede(db: AsyncSession, *, dias: int = 30, agora: datetime | None = None) -> dict:
    """Numeros comparaveis de cada site da rede.

    Uma consulta agregada por assunto, e nao uma por site: com vinte pracas o
    laco viraria oitenta viagens ao banco a cada abertura da tela.
    """
    agora = agora or datetime.now(UTC)
    desde = agora - timedelta(days=dias)

    sites = (await db.execute(select(Site).order_by(Site.name))).scalars().all()
    if not sites:
        return {"dias": dias, "sites": [], "totais": _totais([])}

    por_id = {
        str(s.id): SiteNaRede(
            site_id=str(s.id),
            nome=s.name,
            cidade=s.city,
            estado=s.state,
            timezone=s.timezone,
            grid_limit_kw=float(s.grid_limit_kw or 0),
        )
        for s in sites
    }

    pontos = await db.execute(
        select(ChargePoint.site_id, ChargePoint.status, func.count()).group_by(
            ChargePoint.site_id, ChargePoint.status
        )
    )
    for site_id, status, quantos in pontos:
        alvo = por_id.get(str(site_id))
        if alvo is None:
            continue
        alvo.pontos += quantos
        if status == ChargePointStatus.AVAILABLE:
            alvo.pontos_disponiveis += quantos
        if status in {ChargePointStatus.FAULTED, ChargePointStatus.OFFLINE}:
            alvo.pontos_em_falha += quantos

    ativas = await db.execute(
        select(ChargingSession.site_id, func.count())
        .where(ChargingSession.state.in_(ACTIVE_SESSION_STATES))
        .group_by(ChargingSession.site_id)
    )
    for site_id, quantas in ativas:
        if (alvo := por_id.get(str(site_id))) is not None:
            alvo.sessoes_ativas = quantas

    faturadas = await db.execute(
        select(
            ChargingSession.site_id,
            func.count(),
            func.coalesce(func.sum(ChargingSession.energy_kwh), 0),
            func.coalesce(func.sum(ChargingSession.estimated_cost), 0),
        )
        .where(
            ChargingSession.state.in_(ESTADOS_FATURAVEIS),
            ChargingSession.started_at.is_not(None),
            ChargingSession.started_at >= desde,
        )
        .group_by(ChargingSession.site_id)
    )
    for site_id, quantas, kwh, brl in faturadas:
        if (alvo := por_id.get(str(site_id))) is not None:
            alvo.sessoes = quantas
            alvo.energia_kwh = float(kwh or 0)
            alvo.receita_brl = float(brl or 0)

    falhas = await db.execute(
        select(ChargePoint.site_id, func.count())
        .join(ChargePointFault, ChargePointFault.charge_point_id == ChargePoint.id)
        .where(ChargePointFault.resolved_at.is_(None))
        .group_by(ChargePoint.site_id)
    )
    for site_id, quantas in falhas:
        if (alvo := por_id.get(str(site_id))) is not None:
            alvo.falhas_abertas = quantas

    ordenados = sorted(por_id.values(), key=lambda s: s.receita_por_ponto, reverse=True)
    return {
        "dias": dias,
        "sites": [s.as_dict() for s in ordenados],
        "totais": _totais(ordenados),
    }


def _totais(sites: list[SiteNaRede]) -> dict:
    pontos = sum(s.pontos for s in sites)
    return {
        "sites": len(sites),
        "pontos": pontos,
        "sessoes_ativas": sum(s.sessoes_ativas for s in sites),
        "energia_kwh": round(sum(s.energia_kwh for s in sites), 2),
        "receita_brl": round(sum(s.receita_brl for s in sites), 2),
        "falhas_abertas": sum(s.falhas_abertas for s in sites),
        "pontos_em_falha": sum(s.pontos_em_falha for s in sites),
        # Media ponderada pelos pontos, nao media das medias: uma praca de dois
        # pontos toda quebrada nao pode pesar igual a uma de vinte inteira.
        "disponibilidade_pct": (
            round((pontos - sum(s.pontos_em_falha for s in sites)) / pontos * 100, 1)
            if pontos
            else 0.0
        ),
    }


async def criar_site(db: AsyncSession, dados) -> dict:
    """Abre uma praca nova e devolve no formato do seletor.

    Devolve o MESMO dicionario de `sites_visiveis` de proposito: quem acabou de
    cadastrar precisa poder escolher a praca sem uma segunda chamada, e duas
    formas diferentes para a mesma coisa e' como as duas saem de sincronia.

    O fuso e' validado aqui, e nao so' pelo tamanho do campo: `America/Sao_Pualo`
    passa por qualquer `max_length` e so' falha muito depois, na primeira conta
    de janela horaria - onde o erro aparece como numero errado, nao como erro.
    """
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    from app.core.errors import Conflict

    try:
        ZoneInfo(dados.timezone)
    except (ZoneInfoNotFoundError, ValueError) as erro:
        raise Conflict(f"fuso horario desconhecido: {dados.timezone}") from erro

    repetido = (await db.execute(select(Site).where(Site.slug == dados.slug))).scalar_one_or_none()
    if repetido is not None:
        # 409, e nao o IntegrityError do indice unico: o slug e' escolhido por
        # uma pessoa, e "ja existe" e' resposta, nao falha.
        raise Conflict(f"ja existe uma praca com o identificador '{dados.slug}'")

    if dados.reserva_kw >= dados.limite_da_rede_kw:
        # Reserva maior que o limite deixa o orcamento negativo: a praca nasce
        # sem potencia nenhuma para distribuir, e nada na tela explica por que.
        raise Conflict(
            f"a reserva ({dados.reserva_kw} kW) precisa ser menor que o limite da rede "
            f"({dados.limite_da_rede_kw} kW), senao nao sobra potencia para nenhum ponto"
        )

    site = Site(
        name=dados.nome,
        slug=dados.slug,
        city=dados.cidade,
        state=dados.estado.upper() if dados.estado else None,
        address=dados.endereco,
        timezone=dados.timezone,
        grid_limit_kw=dados.limite_da_rede_kw,
        reserved_kw=dados.reserva_kw,
    )
    db.add(site)
    await db.flush()

    return {
        "site_id": str(site.id),
        "nome": site.name,
        "cidade": site.city,
        "estado": site.state,
        "timezone": site.timezone,
    }


async def sites_visiveis(db: AsyncSession, user) -> list[dict]:
    """Sites que este usuario pode escolher no seletor do painel.

    Operador enxerga apenas o proprio - a lista tambem e' superficie de
    informacao, e nao adianta o escopo barrar a consulta se o seletor entrega
    os nomes e as cidades da rede inteira.
    """
    from app.models.enums import UserRole

    consulta = select(Site).order_by(Site.name)
    if user.role != UserRole.ADMIN:
        if user.site_id is None:
            return []
        consulta = consulta.where(Site.id == user.site_id)

    return [
        {
            "site_id": str(s.id),
            "nome": s.name,
            "cidade": s.city,
            "estado": s.state,
            "timezone": s.timezone,
        }
        for s in (await db.execute(consulta)).scalars().all()
    ]
