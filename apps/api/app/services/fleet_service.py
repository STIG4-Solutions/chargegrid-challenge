"""Relatorio mensal da frota, por centro de custo.

Os dados ja existiam inteiros: a sessao aponta o veiculo, o veiculo aponta o
centro de custo, a fatura aponta a sessao. Faltava a consulta que junta - e o
recorte de quem pode ver.

O recorte e' o ponto delicado. Um gestor de frota nao e' operador: ele nao
administra estabelecimento nenhum, e transforma-lo em `operator` lhe daria o
painel de sites onde a frota nem carrega. Tambem nao pode ser um motorista
comum, ou nao veria o gasto de ninguem alem do proprio. Por isso `fleet_manager`
e' um recorte de LEITURA sobre o papel de motorista: ele ve o consolidado da
propria frota, e mais nada.

O mes fecha pela data de EMISSAO da fatura, nao pelo inicio da recarga. Uma
sessao que comeca 31/03 as 23h e termina 01/04 as 2h pertence a fatura de
abril - e e' a fatura que o financeiro concilia.
"""

from __future__ import annotations

import calendar
import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice
from app.models.enums import InvoiceStatus
from app.models.session import ChargingSession
from app.models.user import User, Vehicle

# Rotulo para o que nao tem centro de custo definido. Aparece de proposito no
# relatorio, em vez de sumir num filtro: gasto sem area responsavel e' o
# primeiro que o financeiro precisa ver para mandar cadastrar.
SEM_CENTRO = "Sem centro de custo"


@dataclass
class LinhaDoCentro:
    centro: str
    sessoes: int = 0
    energia_kwh: float = 0.0
    total_brl: float = 0.0
    veiculos: set[str] = field(default_factory=set)
    motoristas: set[str] = field(default_factory=set)

    def as_dict(self) -> dict:
        return {
            "centro_de_custo": self.centro,
            "sessoes": self.sessoes,
            "energia_kwh": round(self.energia_kwh, 2),
            "total_brl": round(self.total_brl, 2),
            "veiculos": len(self.veiculos),
            "motoristas": len(self.motoristas),
            "custo_medio_por_sessao_brl": (
                round(self.total_brl / self.sessoes, 2) if self.sessoes else 0.0
            ),
            "custo_por_kwh_brl": (
                round(self.total_brl / self.energia_kwh, 3) if self.energia_kwh > 0 else 0.0
            ),
        }


def _limites(mes: str) -> tuple[date, date]:
    """'2026-03' -> (2026-03-01, 2026-03-31). Levanta ValueError se malformado."""
    ano_s, _, mes_s = mes.partition("-")
    ano, numero = int(ano_s), int(mes_s)
    if not (1 <= numero <= 12):
        raise ValueError("mês fora do intervalo")
    ultimo = calendar.monthrange(ano, numero)[1]
    return date(ano, numero, 1), date(ano, numero, ultimo)


async def relatorio_mensal(db: AsyncSession, gestor: User, *, mes: str) -> dict:
    """Consolidado da frota do gestor, agrupado por centro de custo."""
    inicio, fim = _limites(mes)

    if gestor.fleet_id is None:
        return {
            "mes": mes,
            "disponivel": False,
            "motivo": "conta sem frota vinculada",
            "centros": [],
        }

    # Uma consulta com os tres joins, nao uma por fatura. O relatorio de uma
    # frota grande pode ter centenas de sessoes no mes.
    linhas = (
        await db.execute(
            select(Invoice, ChargingSession, Vehicle, User)
            .join(ChargingSession, ChargingSession.id == Invoice.session_id)
            .join(User, User.id == Invoice.user_id)
            .outerjoin(Vehicle, Vehicle.id == ChargingSession.vehicle_id)
            .where(
                User.fleet_id == gestor.fleet_id,
                Invoice.issued_on >= inicio,
                Invoice.issued_on <= fim,
                # Fatura cancelada nao e' despesa. Soma-la inflaria o gasto da
                # area com dinheiro que ninguem pagou.
                Invoice.status != InvoiceStatus.VOID,
            )
        )
    ).all()

    centros: dict[str, LinhaDoCentro] = {}
    em_aberto = 0.0
    for invoice, sessao, veiculo, motorista in linhas:
        nome = (veiculo.cost_center if veiculo and veiculo.cost_center else SEM_CENTRO).strip()
        alvo = centros.setdefault(nome, LinhaDoCentro(centro=nome))
        alvo.sessoes += 1
        alvo.energia_kwh += float(sessao.energy_kwh or 0)
        alvo.total_brl += float(invoice.total or 0)
        if veiculo is not None:
            alvo.veiculos.add(str(veiculo.id))
        alvo.motoristas.add(str(motorista.id))
        if invoice.status != InvoiceStatus.PAID:
            em_aberto += float(invoice.total or 0)

    # Maior gasto primeiro: e' a ordem em que o financeiro le.
    ordenados = sorted(centros.values(), key=lambda c: c.total_brl, reverse=True)
    total = sum(c.total_brl for c in ordenados)

    return {
        "mes": mes,
        "disponivel": True,
        "inicio": inicio.isoformat(),
        "fim": fim.isoformat(),
        "centros": [c.as_dict() for c in ordenados],
        "total_brl": round(total, 2),
        "energia_kwh": round(sum(c.energia_kwh for c in ordenados), 2),
        "sessoes": sum(c.sessoes for c in ordenados),
        "em_aberto_brl": round(em_aberto, 2),
        "veiculos": len({v for c in ordenados for v in c.veiculos}),
        "motoristas": len({m for c in ordenados for m in c.motoristas}),
        # Quanto do gasto ainda nao tem area responsavel. E' o numero que faz
        # alguem cadastrar os centros que faltam.
        "sem_centro_brl": round(
            next((c.total_brl for c in ordenados if c.centro == SEM_CENTRO), 0.0), 2
        ),
    }


async def veiculos_da_frota(db: AsyncSession, gestor: User) -> list[dict]:
    """Carros da frota e seus centros de custo, para o gestor conferir."""
    if gestor.fleet_id is None:
        return []

    linhas = (
        await db.execute(
            select(Vehicle, User)
            .join(User, User.id == Vehicle.user_id)
            .where(User.fleet_id == gestor.fleet_id)
            .order_by(Vehicle.cost_center.nulls_last(), Vehicle.model)
        )
    ).all()
    return [
        {
            "id": str(v.id),
            "modelo": v.model,
            "placa": v.plate,
            "centro_de_custo": v.cost_center,
            "motorista": u.full_name,
        }
        for v, u in linhas
    ]


async def definir_centro_de_custo(
    db: AsyncSession, gestor: User, vehicle_id: uuid.UUID, centro: str | None
) -> dict | None:
    """Atribui o centro de custo de um carro da propria frota.

    Devolve None quando o carro nao existe ou e' de outra frota - a rota
    traduz nos dois casos para 404, para nao confirmar a existencia de
    veiculos de terceiros.
    """
    linha = (
        await db.execute(
            select(Vehicle, User)
            .join(User, User.id == Vehicle.user_id)
            .where(Vehicle.id == vehicle_id, User.fleet_id == gestor.fleet_id)
        )
    ).first()
    if linha is None or gestor.fleet_id is None:
        return None

    veiculo, motorista = linha
    limpo = (centro or "").strip()
    veiculo.cost_center = limpo or None
    await db.commit()
    return {
        "id": str(veiculo.id),
        "modelo": veiculo.model,
        "placa": veiculo.plate,
        "centro_de_custo": veiculo.cost_center,
        "motorista": motorista.full_name,
    }
