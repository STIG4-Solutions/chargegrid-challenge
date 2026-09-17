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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PaymentError
from app.core.logging import get_logger
from app.models.billing import Invoice, WalletEntry
from app.models.user import User
from app.services.tariff_engine import money

log = get_logger(__name__)

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
    if codigo_da_fatura and entrada.origem in ("pagamento", "estorno"):
        return f"{base} — {codigo_da_fatura}"
    # O motivo do ajuste vai no rotulo, e nao num campo a parte: e' a unica
    # explicacao que existe para aquela linha, e escondê-la atras de um "ver
    # detalhes" deixaria o extrato com um "Ajuste R$ 50,00" inexplicavel - que
    # e' exatamente o que a coluna existe para impedir.
    if entrada.origem == "ajuste" and entrada.motivo:
        return f"{base} — {entrada.motivo}"
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
                "motivo": entrada.motivo,
            }
            for entrada, codigo in linhas
        ],
    }


# Tamanho maximo do motivo. Bate com a coluna: cortar em silencio no banco
# perderia justamente a parte final da explicacao, que e' onde ela costuma
# dizer o que interessa.
MOTIVO_MAX = 200


async def ajustar(
    db: AsyncSession,
    dono: User,
    valor: Decimal,
    motivo: str,
    *,
    autor: User,
    idempotency_key: str | None = None,
) -> dict:
    """Correcao manual de saldo, com motivo e responsavel.

    E' o unico lancamento do razao em que alguem ESCOLHE o numero - nao ha
    fatura, recarga nem missao por tras. Por isso as tres exigencias:

      - MOTIVO obrigatorio, tambem no banco (CHECK `ajuste_com_motivo`).
        Dinheiro que aparece na conta de alguem sem ninguem saber explicar e' o
        defeito que um razao existe para impedir;
      - RESPONSAVEL gravado. A rota e' de admin, mas "um admin" nao e' resposta
        quando a pergunta for quem;
      - ZERO recusado. Um ajuste de nada nao corrige nada e ainda sujaria o
        extrato do motorista com uma linha sem efeito. O CHECK
        `sinal_da_origem` tambem barra, e a recusa aqui existe para o erro
        chegar como 422 legivel em vez de erro de banco.

    Aceita valor negativo de proposito: correcao existe nos dois sentidos, e um
    credito lancado por engano precisa poder ser desfeito. O que NAO se aceita
    e' deixar o saldo negativo - a carteira e' pre-paga, e saldo devedor seria
    credito que ninguem autorizou.
    """
    motivo = (motivo or "").strip()
    if not motivo:
        raise PaymentError("ajuste exige motivo")
    if len(motivo) > MOTIVO_MAX:
        raise PaymentError(f"motivo passa de {MOTIVO_MAX} caracteres")
    if valor == 0:
        raise PaymentError("ajuste de zero não corrige nada")

    if idempotency_key:
        anterior = (
            await db.execute(
                select(WalletEntry).where(WalletEntry.idempotency_key == idempotency_key)
            )
        ).scalar_one_or_none()
        if anterior is not None:
            return await extrato(db, dono.id)

    saldo_atual = (
        await db.execute(select(User.wallet_balance).where(User.id == dono.id).with_for_update())
    ).scalar_one()
    novo = money(Decimal(str(saldo_atual)) + valor)
    if novo < 0:
        raise PaymentError(
            f"ajuste deixaria o saldo negativo: {saldo_atual} disponível, {valor} pedido"
        )

    db.add(
        WalletEntry(
            user_id=dono.id,
            amount=valor,
            balance_after=novo,
            idempotency_key=idempotency_key,
            provider="manual",
            origem="ajuste",
            motivo=motivo,
            criado_por=autor.id,
        )
    )
    dono.wallet_balance = novo
    try:
        await db.commit()
    except IntegrityError:
        # Mesma chave por dois caminhos ao mesmo tempo. O primeiro vale.
        await db.rollback()
        return await extrato(db, dono.id)

    log.info(
        "carteira.ajustada",
        motorista=str(dono.id),
        valor=float(valor),
        por=str(autor.id),
        motivo=motivo,
    )
    return await extrato(db, dono.id)
