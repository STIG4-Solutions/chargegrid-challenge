"""Manutencao a partir do que o carregador ja diz.

O HCA G2 expoe 65 bits de diagnostico em quatro registradores. O sistema ja os
decodifica e mostra o estado atual - mas estado atual so' serve para reagir. A
pergunta que evita a parada e' outra: "qual ponto vem falhando mais?".

Um conector que abre "falha da trava" tres vezes na semana ainda funciona, e
vai parar de funcionar. Um cabo que acende "sobretemperatura" nas tardes
quentes esta pedindo inspecao antes de derreter. Nenhum dos dois aparece num
painel de estado, porque no instante em que se olha eles estao normais.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import DomainError, NotFound
from app.core.logging import get_logger
from app.models.charge_point import ChargePoint, ChargePointFault
from app.models.charge_point_report import ChargePointReport
from app.models.user import User

log = get_logger(__name__)

# Um episodio que durou menos que isto e' ruido de leitura, nao evento.
CICLOS_MINIMOS = 2

# A partir de quantos episodios no periodo o ponto entra na fila de manutencao.
# Nao e' regra de engenharia - e' um corte para a lista ser curta o bastante
# para alguem agir sobre ela.
EPISODIOS_PARA_ATENCAO = 3

# Reportes abertos que ja bastam para tratar o ponto como problema, mesmo sem
# nenhum sinal do sensor. Duas pessoas diferentes reclamando da mesma coisa
# nao e' azar - e' um defeito que o equipamento nao tem como enxergar.
REPORTES_PARA_ATENCAO = 2


@dataclass
class SintomaDoPonto:
    label: str
    terminal: bool
    episodios: int
    ciclos_totais: int
    primeira_vez: datetime
    ultima_vez: datetime
    aberto: bool

    def as_dict(self) -> dict:
        return {
            "label": self.label,
            "terminal": self.terminal,
            "episodios": self.episodios,
            "ciclos_totais": self.ciclos_totais,
            "primeira_vez": self.primeira_vez.isoformat(),
            "ultima_vez": self.ultima_vez.isoformat(),
            "aberto": self.aberto,
        }


@dataclass
class ReporteAgrupado:
    """Quantas pessoas reclamaram da mesma coisa neste ponto."""

    categoria: str
    quantidade: int
    abertos: int
    ultima_vez: datetime
    ultimo_relato: str | None

    def as_dict(self) -> dict:
        return {
            "categoria": self.categoria,
            "quantidade": self.quantidade,
            "abertos": self.abertos,
            "ultima_vez": self.ultima_vez.isoformat(),
            "ultimo_relato": self.ultimo_relato,
        }


@dataclass
class PontoEmAtencao:
    charge_point_id: uuid.UUID
    code: str
    name: str
    episodios: int
    sintomas: list[SintomaDoPonto] = field(default_factory=list)
    reportes: list[ReporteAgrupado] = field(default_factory=list)

    @property
    def tem_terminal(self) -> bool:
        return any(s.terminal for s in self.sintomas)

    @property
    def reportes_abertos(self) -> int:
        return sum(r.abertos for r in self.reportes)

    @property
    def so_humano(self) -> bool:
        """Reclamacao de gente sem nenhum sinal do equipamento.

        E' o caso que da nome a feature: cabo cortado, tela apagada, vaga
        tomada por um carro a combustao. O ponto reporta "disponivel" com toda
        a sinceridade, porque do ponto de vista dele esta tudo bem.
        """
        return self.reportes_abertos > 0 and not self.sintomas

    @property
    def prioridade(self) -> str:
        """Falha terminal ja parou a recarga uma vez; alarme ainda nao."""
        if self.tem_terminal:
            return "alta"
        # Gente reclamando pesa como sintoma recorrente: o motorista chega
        # antes do sensor, e esperar o equipamento confirmar e' esperar por
        # uma confirmacao que, nestes casos, nunca vem.
        if self.reportes_abertos >= REPORTES_PARA_ATENCAO:
            return "alta" if self.so_humano else "media"
        return "media" if self.episodios >= EPISODIOS_PARA_ATENCAO else "baixa"

    def as_dict(self) -> dict:
        return {
            "charge_point_id": str(self.charge_point_id),
            "code": self.code,
            "name": self.name,
            "episodios": self.episodios,
            "prioridade": self.prioridade,
            "tem_falha_aberta": any(s.aberto for s in self.sintomas),
            "sintomas": [s.as_dict() for s in self.sintomas],
            "reportes": [r.as_dict() for r in self.reportes],
            "reportes_abertos": self.reportes_abertos,
            # Sinaliza para a tela que aqui o sensor nao vai confirmar nada.
            "so_humano": self.so_humano,
        }


async def pontos_em_atencao(db: AsyncSession, site_id: uuid.UUID, *, dias: int = 30) -> dict:
    """Ranking de pontos por recorrencia de falha no periodo."""
    desde = datetime.now(UTC) - timedelta(days=dias)

    linhas = (
        await db.execute(
            select(ChargePointFault, ChargePoint)
            .join(ChargePoint, ChargePoint.id == ChargePointFault.charge_point_id)
            .where(
                ChargePoint.site_id == site_id,
                ChargePointFault.first_seen_at >= desde,
                # Um ciclo isolado e' ruido do barramento, nao sintoma.
                ChargePointFault.ciclos >= CICLOS_MINIMOS,
            )
            .order_by(ChargePointFault.first_seen_at)
        )
    ).all()

    por_ponto: dict[uuid.UUID, PontoEmAtencao] = {}
    agrupado: dict[tuple[uuid.UUID, str], SintomaDoPonto] = {}

    for falha, ponto in linhas:
        alvo = por_ponto.setdefault(
            ponto.id,
            PontoEmAtencao(charge_point_id=ponto.id, code=ponto.code, name=ponto.name, episodios=0),
        )
        alvo.episodios += 1

        chave = (ponto.id, falha.label)
        sintoma = agrupado.get(chave)
        if sintoma is None:
            sintoma = SintomaDoPonto(
                label=falha.label,
                terminal=falha.terminal,
                episodios=0,
                ciclos_totais=0,
                primeira_vez=falha.first_seen_at,
                ultima_vez=falha.last_seen_at,
                aberto=falha.resolved_at is None,
            )
            agrupado[chave] = sintoma
            alvo.sintomas.append(sintoma)

        sintoma.episodios += 1
        sintoma.ciclos_totais += falha.ciclos
        sintoma.ultima_vez = max(sintoma.ultima_vez, falha.last_seen_at)
        sintoma.aberto = sintoma.aberto or falha.resolved_at is None

    # ---- o que as pessoas reportaram ----
    #
    # Entra DEPOIS das falhas e cria o ponto se ele ainda nao existir: um ponto
    # com tres reclamacoes e zero sinal de sensor e' exatamente o caso que esta
    # feature existe para tornar visivel. Filtrar por pontos que ja tem falha
    # apagaria justamente ele.
    reportes = (
        await db.execute(
            select(ChargePointReport, ChargePoint)
            .join(ChargePoint, ChargePoint.id == ChargePointReport.charge_point_id)
            .where(
                ChargePoint.site_id == site_id,
                ChargePointReport.created_at >= desde,
            )
            .order_by(ChargePointReport.created_at)
        )
    ).all()

    por_categoria: dict[tuple[uuid.UUID, str], ReporteAgrupado] = {}
    for reporte, ponto in reportes:
        alvo = por_ponto.setdefault(
            ponto.id,
            PontoEmAtencao(charge_point_id=ponto.id, code=ponto.code, name=ponto.name, episodios=0),
        )
        chave = (ponto.id, reporte.categoria)
        grupo = por_categoria.get(chave)
        if grupo is None:
            grupo = ReporteAgrupado(
                categoria=reporte.categoria,
                quantidade=0,
                abertos=0,
                ultima_vez=reporte.created_at,
                ultimo_relato=None,
            )
            por_categoria[chave] = grupo
            alvo.reportes.append(grupo)

        grupo.quantidade += 1
        if reporte.resolved_at is None:
            grupo.abertos += 1
        # A consulta vem em ordem crescente, entao o ultimo visto e' o mais
        # recente - e e' o relato que o operador quer ler primeiro.
        grupo.ultima_vez = max(grupo.ultima_vez, reporte.created_at)
        if reporte.descricao:
            grupo.ultimo_relato = reporte.descricao

    ordem = {"alta": 0, "media": 1, "baixa": 2}
    pontos = sorted(por_ponto.values(), key=lambda p: (ordem[p.prioridade], -p.episodios))

    return {
        "dias": dias,
        "pontos": [p.as_dict() for p in pontos],
        "total_episodios": sum(p.episodios for p in pontos),
        "total_reportes_abertos": sum(p.reportes_abertos for p in pontos),
        "sem_ocorrencias": not pontos,
    }


# ---------------------------------------------------------------- reportes
#
# O motorista reportava e ninguem conseguia resolver. `resolved_at` era LIDO -
# a resposta do app expoe `resolvido`, e o indice parcial
# `ix_charge_point_reports_abertos` e' a fila de abertos - e nenhuma rota o
# escrevia. A fila nunca drenava, e o CHECK `resolucao_completa` mantinha
# `resolved_by` inalcancavel junto.


async def listar_reportes(
    db: AsyncSession, site_id: uuid.UUID, *, abertos: bool = True, limite: int = 100
) -> list[dict]:
    """Os reportes desta praca, do mais novo ao mais antigo.

    ESCOPO PELO PONTO, e nao pelo reporte: `charge_point_reports` nao tem
    `site_id`, e ler sem o JOIN devolveria a reclamacao do vizinho.

    Traz quem reportou porque o operador precisa poder responder a pessoa - e
    nao traz nada alem do e-mail: o reporte ja e' uma reclamacao, e enriquecer
    a linha com o resto do cadastro seria expor o motorista a quem ele
    reclamou.
    """
    autor = aliased(User)
    resolvedor = aliased(User)
    consulta = (
        select(ChargePointReport, ChargePoint, autor.email, resolvedor.email)
        .join(ChargePoint, ChargePoint.id == ChargePointReport.charge_point_id)
        .outerjoin(autor, autor.id == ChargePointReport.user_id)
        .outerjoin(resolvedor, resolvedor.id == ChargePointReport.resolved_by)
        .where(ChargePoint.site_id == site_id)
        .order_by(ChargePointReport.created_at.desc())
        .limit(limite)
    )
    if abertos:
        consulta = consulta.where(ChargePointReport.resolved_at.is_(None))

    return [
        {
            "id": str(r.id),
            "charge_point_id": str(r.charge_point_id),
            "ponto": cp.code,
            "categoria": r.categoria,
            "descricao": r.descricao,
            "reportado_em": r.created_at.isoformat(),
            "reportado_por": email_autor,
            "resolvido": r.resolved_at is not None,
            "resolvido_em": r.resolved_at.isoformat() if r.resolved_at else None,
            "resolvido_por": email_resolvedor,
            "resolucao": r.resolucao,
        }
        for r, cp, email_autor, email_resolvedor in (await db.execute(consulta)).all()
    ]


async def resolver_reporte(
    db: AsyncSession, reporte_id: uuid.UUID, site_id: uuid.UUID, *, por: User, resolucao: str
) -> dict:
    """Fecha um reporte, dizendo o que foi feito.

    RESOLUCAO OBRIGATORIA. Fechar sem dizer o que se fez transforma a fila num
    botao de "sumir com isto": o proximo motorista que reportar o mesmo cabo
    nao tem como saber que ja olharam, e o relatorio de manutencao perde a
    unica informacao que o distingue de uma contagem de reclamacoes.

    Fechar duas vezes NAO reescreve o primeiro fechamento. Quem resolveu e
    quando sao fato consumado - a segunda chamada devolve o que ja estava la',
    em vez de trocar o responsavel pelo ultimo que clicou.
    """
    resolucao = (resolucao or "").strip()
    if not resolucao:
        raise DomainError("descreva o que foi feito para fechar o reporte")

    linha = (
        await db.execute(
            select(ChargePointReport)
            .join(ChargePoint, ChargePoint.id == ChargePointReport.charge_point_id)
            .where(ChargePointReport.id == reporte_id, ChargePoint.site_id == site_id)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if linha is None:
        # 404 tambem quando o reporte existe noutra praca: dizer "existe, mas
        # nao e' seu" ja entrega que ele existe.
        raise NotFound("reporte não encontrado")

    if linha.resolved_at is None:
        linha.resolved_at = datetime.now(UTC)
        linha.resolved_by = por.id
        linha.resolucao = resolucao
        await db.commit()
        log.info(
            "reporte.resolvido",
            reporte=str(linha.id),
            ponto=str(linha.charge_point_id),
            por=str(por.id),
        )

    return {
        "id": str(linha.id),
        "resolvido": True,
        "resolvido_em": linha.resolved_at.isoformat(),
        "resolucao": linha.resolucao,
    }
