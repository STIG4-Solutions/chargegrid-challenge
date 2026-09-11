"""Leitura do razao da carteira.

`wallet_entries` guarda cada movimento com sinal; aqui ele vira extrato. O
trabalho real e' de traducao, e nao e' decorativo: a coluna `origem` guarda
`cashback`, que nao diz nada a quem recebeu, e o motorista precisa ler "Cashback
de missao" ao lado do valor.

POR QUE O SALDO VEM DA LINHA, e nao de `users.wallet_balance`. Os dois deveriam
ser iguais - e' a invariante que o razao sustenta - mas quando divergirem, quem
esta olhando o extrato precisa ver a versao que as linhas contam. Um saldo
avulso no topo de uma lista que soma outra coisa e' pior que nao ter saldo.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.billing import Invoice, WalletEntry

# Quantos movimentos a tela do motorista mostra por vez.
PAGINA = 50

# O que cada origem significa para quem recebeu o dinheiro. Sem isto o extrato
# imprime `cashback` cru - o mesmo defeito que os ROTULOS do recibo corrigiram.
ROTULOS = {
    "topup": "Recarga de saldo",
    "cashback": "Cashback de missão",
    "estorno": "Estorno",
    "ajuste": "Ajuste",
    "pagamento": "Pagamento de recarga",
}


def _rotulo(entrada: WalletEntry, codigo_da_fatura: str | None) -> str:
    base = ROTULOS.get(entrada.origem, entrada.origem)
    if entrada.origem == "pagamento" and codigo_da_fatura:
        return f"{base} — {codigo_da_fatura}"
    return base


async def extrato(db: AsyncSession, user_id: uuid.UUID, limite: int = PAGINA) -> dict:
    """Os ultimos movimentos da carteira deste motorista, do mais novo ao mais
    antigo.

    O codigo da fatura entra por LEFT JOIN, e nao por `selectinload`: e' um
    campo so', num debito que sempre tem fatura. Carregar o objeto inteiro para
    ler `code` traria linhas, pagamentos e o site junto.
    """
    linhas = (
        await db.execute(
            select(WalletEntry, Invoice.code)
            .outerjoin(Invoice, Invoice.id == WalletEntry.invoice_id)
            .where(WalletEntry.user_id == user_id)
            .order_by(WalletEntry.created_at.desc(), WalletEntry.id.desc())
            .limit(limite)
        )
    ).all()

    # O saldo e' a soma de TUDO, nao das linhas desta pagina: quem abre o
    # extrato com 50 movimentos de 200 veria um saldo que nao e' o dele.
    saldo = (
        await db.execute(
            select(func.coalesce(func.sum(WalletEntry.amount), 0)).where(
                WalletEntry.user_id == user_id
            )
        )
    ).scalar_one()

    return {
        "saldo": float(Decimal(str(saldo))),
        "movimentos": [
            {
                "id": str(entrada.id),
                "data": entrada.created_at.isoformat(),
                "valor": float(entrada.amount),
                "saldo_apos": float(entrada.balance_after),
                "origem": entrada.origem,
                "rotulo": _rotulo(entrada, codigo),
                "invoice_id": str(entrada.invoice_id) if entrada.invoice_id else None,
            }
            for entrada, codigo in linhas
        ],
    }
