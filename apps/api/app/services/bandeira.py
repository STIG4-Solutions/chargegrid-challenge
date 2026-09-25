"""Bandeira do site: a folga de potencia vira multiplicador de preco.

O rebalanceador ja' sabe, a cada ciclo, quanto sobra para os eletropostos. Ate'
aqui esse numero morria no rateio, e o preco so' mudava por janela horaria. A
bandeira e' a ponte: folga alta, preco neutro; folga curta, preco sobe - o
motorista que carrega quando o predio esta' no limite paga pela escassez que
causa, e quem pode esperar tem motivo para esperar.

FOLGA = potencia disponivel / capacidade. A capacidade e' rede + solar + bateria
COMO O ORCAMENTO JA' AS CONSIDEROU: leitura vencida zera solar e bateria, SOC
abaixo do minimo zera a bateria. Usar os valores crus do medidor daria folga
sobre uma energia que o proprio alocador ja' decidiu nao usar.

Funcao pura: sem banco, sem relogio. E' o que permite testar as bordas das
faixas com literais, e e' a mesma conta para o worker, a rota e o teste.

O MOTIVO e' regra, nao modelo. Uma frase que diz o que pesou no orcamento - a
bandeira existe para ser entendida pelo motorista, e uma cor sem motivo e' so'
um preco mais caro.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.core.config import get_settings
from app.services.power_manager import PowerBudget

VERDE, AMARELA, VERMELHA = "verde", "amarela", "vermelha"


@dataclass(frozen=True, slots=True)
class Faixas:
    """Onde cada cor comeca e quanto ela multiplica. Bordas pertencem a de cima."""

    folga_verde: Decimal
    folga_amarela: Decimal
    mult_verde: Decimal
    mult_amarela: Decimal
    mult_vermelha: Decimal

    @classmethod
    def da_configuracao(cls) -> Faixas:
        s = get_settings()
        return cls(
            folga_verde=Decimal(str(s.bandeira_folga_verde)),
            folga_amarela=Decimal(str(s.bandeira_folga_amarela)),
            mult_verde=Decimal(str(s.bandeira_mult_verde)),
            mult_amarela=Decimal(str(s.bandeira_mult_amarela)),
            mult_vermelha=Decimal(str(s.bandeira_mult_vermelha)),
        )


@dataclass(frozen=True, slots=True)
class Bandeira:
    cor: str
    multiplicador: Decimal
    folga_pct: Decimal
    motivo: str


def _motivo(budget: PowerBudget, cor: str) -> str:
    """O que mais pesou no orcamento, numa frase para o motorista."""
    if cor == VERDE:
        return "Folga confortável de potência no estabelecimento"
    nao_ev = max(budget.reserved_kw, budget.building_load_kw)
    if budget.booked_kw > nao_ev:
        return "Reservas agendadas seguram boa parte da potência"
    if budget.building_load_kw > budget.reserved_kw:
        return "Consumo do prédio alto: sobra pouca potência para os carregadores"
    return "Sem geração solar ou bateria suficiente para folgar a rede"


def calcular(budget: PowerBudget, *, over_budget: bool, faixas: Faixas | None = None) -> Bandeira:
    """A bandeira deste orcamento. `over_budget` vem do plano de rateio."""
    f = faixas or Faixas.da_configuracao()
    capacidade = Decimal(str(budget.grid_limit_kw + budget.pv_kw + budget.battery_kw))

    if capacidade <= 0:
        return Bandeira(
            VERMELHA, f.mult_vermelha, Decimal("0.0"), "Sem capacidade disponível no site"
        )

    folga = Decimal(str(budget.available_kw)) / capacidade
    folga_pct = (folga * 100).quantize(Decimal("0.1"))

    if over_budget:
        # Os pisos dos pontos ja' passam do disponivel: a folga pode ate' parecer
        # alta no papel, mas o site esta' comprometido acima do que tem.
        return Bandeira(
            VERMELHA,
            f.mult_vermelha,
            folga_pct,
            "Pontos em carga pedem mais que o orçamento de potência",
        )

    if folga >= f.folga_verde:
        cor, mult = VERDE, f.mult_verde
    elif folga >= f.folga_amarela:
        cor, mult = AMARELA, f.mult_amarela
    else:
        cor, mult = VERMELHA, f.mult_vermelha
    return Bandeira(cor, mult, folga_pct, _motivo(budget, cor))


async def registrar(db, site, plan, *, agora: datetime | None = None) -> dict:
    """Calcula a bandeira do plano recem-aplicado e a grava no site.

    Gravada inteira - cor, multiplicador, folga, motivo e instante -, e nao so'
    o multiplicador: e' daqui que a sessao copia o preco, e a tela precisa mostrar
    exatamente o que foi copiado.
    """
    b = calcular(plan.budget, over_budget=plan.over_budget)
    site.bandeira_cor = b.cor
    site.bandeira_multiplicador = b.multiplicador
    site.bandeira_folga_pct = b.folga_pct
    site.bandeira_motivo = b.motivo
    site.bandeira_calculada_em = agora or datetime.now(UTC)
    await db.commit()
    return {
        "cor": b.cor,
        "multiplicador": float(b.multiplicador),
        "folga_pct": float(b.folga_pct),
        "motivo": b.motivo,
        "calculada_em": site.bandeira_calculada_em.isoformat(),
    }


def para_travar(site, *, agora: datetime | None = None) -> tuple[Decimal, str | None]:
    """O multiplicador e a cor que uma recarga iniciada agora deve travar.

    Bandeira ausente ou velha trava o neutro, sem cor. Velha e' o caso do
    rebalanceador parado - a instancia hibernou e a ultima cor gravada pode ser
    de um pico de horas atras. Cobrar 1,30 de alguem com base nela seria cobrar
    por uma escassez que ninguem mediu.
    """
    agora = agora or datetime.now(UTC)
    validade = timedelta(seconds=get_settings().bandeira_validade_s)
    if (
        site.bandeira_multiplicador is None
        or site.bandeira_calculada_em is None
        or agora - site.bandeira_calculada_em > validade
    ):
        return Decimal("1.00"), None
    return Decimal(str(site.bandeira_multiplicador)), site.bandeira_cor
