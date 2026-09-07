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

# Um episodio que durou menos que isto e' ruido de leitura, nao evento.
CICLOS_MINIMOS = 2

# A partir de quantos episodios no periodo o ponto entra na fila de manutencao.
# Nao e' regra de engenharia - e' um corte para a lista ser curta o bastante
# para alguem agir sobre ela.
EPISODIOS_PARA_ATENCAO = 3


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
class PontoEmAtencao:
    charge_point_id: uuid.UUID
    code: str
    name: str
    episodios: int
    sintomas: list[SintomaDoPonto] = field(default_factory=list)

    @property
    def tem_terminal(self) -> bool:
        return any(s.terminal for s in self.sintomas)

    @property
    def prioridade(self) -> str:
        """Falha terminal ja parou a recarga uma vez; alarme ainda nao."""
        if self.tem_terminal:
            return "alta"
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

    ordem = {"alta": 0, "media": 1, "baixa": 2}
    pontos = sorted(
        por_ponto.values(), key=lambda p: (ordem[p.prioridade], -p.episodios)
    )

    return {
        "dias": dias,
        "pontos": [p.as_dict() for p in pontos],
        "total_episodios": sum(p.episodios for p in pontos),
        "sem_ocorrencias": not pontos,
    }
