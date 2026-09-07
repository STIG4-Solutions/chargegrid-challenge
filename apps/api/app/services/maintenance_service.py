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

from app.models.charge_point import ChargePoint, ChargePointFault
from app.models.charge_point_report import ChargePointReport

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


async def pontos_em_atencao(
    db: AsyncSession, site_id: uuid.UUID, *, dias: int = 30
) -> dict:
    """Ranking de pontos por recorrencia de falha no periodo."""
    desde = datetime.now(UTC) - timedelta(days=dias)

    linhas = (
        (
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
        )
        .all()
    )

    por_ponto: dict[uuid.UUID, PontoEmAtencao] = {}
    agrupado: dict[tuple[uuid.UUID, str], SintomaDoPonto] = {}

    for falha, ponto in linhas:
        alvo = por_ponto.setdefault(
            ponto.id,
            PontoEmAtencao(
                charge_point_id=ponto.id, code=ponto.code, name=ponto.name, episodios=0
            ),
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
            PontoEmAtencao(
                charge_point_id=ponto.id, code=ponto.code, name=ponto.name, episodios=0
            ),
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
    pontos = sorted(
        por_ponto.values(), key=lambda p: (ordem[p.prioridade], -p.episodios)
    )

    return {
        "dias": dias,
        "pontos": [p.as_dict() for p in pontos],
        "total_episodios": sum(p.episodios for p in pontos),
        "total_reportes_abertos": sum(p.reportes_abertos for p in pontos),
        "sem_ocorrencias": not pontos,
    }
