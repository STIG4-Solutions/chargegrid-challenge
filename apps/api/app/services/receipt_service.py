"""Recibo da recarga.

A fatura ja tinha tudo: linhas por tipo, quantidade, preco unitario, a tarifa
aplicada no momento do consumo, o pagamento e a taxa do adquirente. Faltava o
documento - o papel que o motorista guarda, anexa a prestacao de contas da
empresa ou manda para o contador.

Duas decisoes que separam um recibo de um dump da fatura:

  a taxa do adquirente NAO entra. `net_amount = total - processing_fee`: quem
  paga a taxa e' o estabelecimento, descontada do que ele recebe. O motorista
  pagou `total`. Mostrar a taxa no recibo dele diria que ele pagou algo que
  nao pagou, e num documento que vai para prestacao de contas isso e' pior que
  incompleto - e errado.

  o HTML sai daqui, nao do app. Um recibo montado no cliente e' um recibo cujos
  numeros dependem da versao instalada: dois motoristas com dois builds
  diferentes gerariam documentos diferentes para a mesma fatura. Renderizar no
  servidor faz o documento ter uma unica origem, igual a fatura.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from html import escape

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.billing import Invoice
from app.models.charge_point import ChargePoint
from app.models.enums import InvoiceStatus
from app.models.session import ChargingSession
from app.models.site import Site
from app.models.user import User

# Rotulos legiveis para o `kind` das linhas. Um recibo que diz "energy" nao
# serve para prestacao de contas - quem le nao e' quem escreveu o codigo.
# As chaves TEM que ser as que `tariff_engine` emite. Tres delas nao eram:
# "session" e "minimum" nunca existiram - o motor sempre emitiu "session_fee" e
# "min_charge" -, e "dynamic" faltava. Como a leitura e' `ROTULOS.get(kind, kind)`,
# o recibo caia na chave crua e imprimia a palavra `session_fee` no campo "tipo",
# num documento que vai para prestacao de contas. Nenhum teste cobria.
ROTULOS = {
    "energy": "Energia",
    "time": "Tempo de recarga",
    "idle": "Ociosidade",
    "session_fee": "Taxa de conexão",
    "min_charge": "Complemento de valor mínimo",
    "dynamic": "Ajuste dinâmico de demanda",
    "plano": "Plano — kWh inclusos",
    "desconto": "Desconto",
}


def _brl(valor: float) -> str:
    # O sinal vem ANTES do simbolo: "-R$ 5,60", e nao "R$ -5,60".
    #
    # Nao era visivel enquanto nenhuma linha podia ser negativa. Agora as linhas
    # de plano e de desconto sao, e "R$ -5,60" num recibo de prestacao de contas
    # se le como erro de formatacao - quando nao passa despercebido.
    sinal = "-" if valor < 0 else ""
    inteiro, _, centavos = f"{abs(valor):,.2f}".partition(".")
    return f"{sinal}R$ {inteiro.replace(',', '.')},{centavos}"


def _quantidade(q: float, unidade: str) -> str:
    casas = 3 if unidade == "kWh" else 0
    return f"{q:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


async def montar(db: AsyncSession, invoice_id: uuid.UUID, user: User) -> dict | None:
    """Dados do recibo de uma fatura do proprio motorista.

    Devolve None quando a fatura nao existe OU nao e' dele - a rota traduz nos
    dois casos para 404. Distinguir "nao existe" de "nao e sua" confirmaria a
    existencia de faturas alheias para quem sondar identificadores.
    """
    invoice = (
        await db.execute(
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.user_id == user.id)
            .options(selectinload(Invoice.lines), selectinload(Invoice.payments))
        )
    ).scalar_one_or_none()
    if invoice is None:
        return None

    site = (await db.execute(select(Site).where(Site.id == invoice.site_id))).scalar_one_or_none()

    sessao = None
    ponto = None
    if invoice.session_id:
        sessao = (
            await db.execute(
                select(ChargingSession).where(ChargingSession.id == invoice.session_id)
            )
        ).scalar_one_or_none()
        if sessao is not None:
            ponto = (
                await db.execute(
                    select(ChargePoint).where(ChargePoint.id == sessao.charge_point_id)
                )
            ).scalar_one_or_none()

    pago = invoice.status == InvoiceStatus.PAID
    pagamento = next(
        (p for p in sorted(invoice.payments, key=lambda p: p.created_at, reverse=True)), None
    )

    return {
        "invoice_id": str(invoice.id),
        "codigo": invoice.code,
        "emitida_em": invoice.issued_on.isoformat(),
        "status": str(invoice.status),
        "pago": pago,
        "pago_em": invoice.paid_at.isoformat() if invoice.paid_at else None,
        "metodo": str(pagamento.method) if pagamento else None,
        "moeda": invoice.currency,
        "cliente": {"nome": user.full_name, "email": user.email},
        "estabelecimento": {
            "nome": site.name if site else "—",
            "endereco": (site.address if site else None),
            "cidade": (site.city if site else None),
            "estado": (site.state if site else None),
        },
        "recarga": (
            {
                "codigo": sessao.code,
                "ponto": ponto.name if ponto else None,
                "ponto_codigo": ponto.code if ponto else None,
                "inicio": sessao.started_at.isoformat() if sessao.started_at else None,
                "fim": sessao.ended_at.isoformat() if sessao.ended_at else None,
                "energia_kwh": float(sessao.energy_kwh or 0),
                "duracao_min": int((sessao.duration_s or 0) / 60),
                "tarifa": (invoice.tariff_snapshot or {}).get("name"),
            }
            if sessao
            else None
        ),
        "linhas": [
            {
                "descricao": linha.description,
                "tipo": ROTULOS.get(linha.kind, linha.kind),
                "quantidade": float(linha.quantity),
                "unidade": linha.unit,
                "preco_unitario": float(linha.unit_price),
                "valor": float(linha.amount),
            }
            for linha in sorted(invoice.lines, key=lambda x: x.position)
        ],
        "subtotal": float(invoice.subtotal),
        "desconto": float(invoice.discount),
        # O que o motorista pagou. A taxa do adquirente sai do que o
        # estabelecimento recebe, nao do bolso dele, e por isso nao aparece.
        "total": float(invoice.total),
    }


def como_html(r: dict) -> str:
    """Recibo em HTML, pronto para virar PDF no aparelho.

    Estilo embutido e sem imagem externa: o documento precisa abrir igual no
    visualizador de PDF de qualquer aparelho, offline, meses depois.
    """
    e = escape
    est = r["estabelecimento"]
    rec = r.get("recarga")

    def _linha(item: dict) -> str:
        qtd = e(_quantidade(item["quantidade"], item["unidade"]))
        return f"""<tr>
          <td>{e(item["descricao"])}<div class="tipo">{e(item["tipo"])}</div></td>
          <td class="n">{qtd} {e(item["unidade"])}</td>
          <td class="n">{e(_brl(item["preco_unitario"]))}</td>
          <td class="n forte">{e(_brl(item["valor"]))}</td>
        </tr>"""

    linhas = "".join(_linha(item) for item in r["linhas"])

    endereco = (
        e(", ".join(x for x in [est.get("endereco"), est.get("cidade"), est.get("estado")] if x))
        or "&mdash;"
    )

    bloco_recarga = ""
    if rec:
        bloco_recarga = f"""
      <div class="grade">
        <div><span>Recarga</span>{e(rec["codigo"])}</div>
        <div><span>Ponto</span>{e(rec.get("ponto") or "—")}</div>
        <div><span>Energia</span>{e(_quantidade(rec["energia_kwh"], "kWh"))} kWh</div>
        <div><span>Duração</span>{rec["duracao_min"]} min</div>
        <div><span>Tarifa</span>{e(rec.get("tarifa") or "—")}</div>
      </div>"""

    desconto = ""
    if r["desconto"] > 0:
        desconto = f"""<tr><td colspan="3">Desconto</td>
          <td class="n">-{e(_brl(r["desconto"]))}</td></tr>"""

    selo = (
        f'<div class="selo pago">Pago em {e((r["pago_em"] or "")[:10])}</div>'
        if r["pago"]
        else '<div class="selo aberto">Em aberto</div>'
    )

    return f"""<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Recibo {e(r["codigo"])}</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{ font: 13px/1.5 -apple-system, "Segoe UI", Roboto, sans-serif;
         color: #14161a; background: #fff; margin: 0; padding: 28px; }}
  h1 {{ font-size: 19px; margin: 0 0 2px; }}
  .sub {{ color: #6b7078; font-size: 12px; }}
  .topo {{ display: flex; justify-content: space-between; align-items: flex-start;
          gap: 16px; border-bottom: 2px solid #14161a; padding-bottom: 14px; }}
  .selo {{ font-size: 11px; font-weight: 700; text-transform: uppercase;
          letter-spacing: .4px; padding: 5px 10px; border-radius: 4px; white-space: nowrap; }}
  .pago {{ background: #e4f3eb; color: #17794a; }}
  .aberto {{ background: #faf0de; color: #9a6412; }}
  .grade {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
           gap: 10px; margin: 18px 0; }}
  .grade div span {{ display: block; color: #6b7078; font-size: 10px;
                    text-transform: uppercase; letter-spacing: .4px; margin-bottom: 1px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th {{ text-align: left; font-size: 10px; text-transform: uppercase; letter-spacing: .4px;
       color: #6b7078; border-bottom: 1px solid #d9dade; padding: 6px 0; }}
  td {{ padding: 9px 0; border-bottom: 1px solid #eceef1; vertical-align: top; }}
  .n {{ text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; }}
  .forte {{ font-weight: 600; }}
  .tipo {{ color: #6b7078; font-size: 11px; }}
  tfoot td {{ border: none; padding-top: 8px; }}
  .total td {{ border-top: 2px solid #14161a; font-size: 16px;
              font-weight: 700; padding-top: 12px; }}
  .rodape {{ margin-top: 26px; color: #6b7078; font-size: 11px;
            border-top: 1px solid #eceef1; padding-top: 12px; }}
</style></head>
<body>
  <div class="topo">
    <div>
      <h1>{e(est["nome"])}</h1>
      <div class="sub">{endereco}</div>
    </div>
    {selo}
  </div>

  <div class="grade">
    <div><span>Recibo</span>{e(r["codigo"])}</div>
    <div><span>Emitido em</span>{e(r["emitida_em"])}</div>
    <div><span>Cliente</span>{e(r["cliente"]["nome"])}</div>
    <div><span>Pagamento</span>{e(r["metodo"] or "—")}</div>
  </div>
  {bloco_recarga}

  <table>
    <thead><tr><th>Item</th><th class="n">Qtd.</th>
      <th class="n">Preço</th><th class="n">Valor</th></tr></thead>
    <tbody>{linhas}</tbody>
    <tfoot>
      <tr><td colspan="3">Subtotal</td><td class="n">{e(_brl(r["subtotal"]))}</td></tr>
      {desconto}
      <tr class="total"><td colspan="3">Total pago</td><td class="n">{e(_brl(r["total"]))}</td></tr>
    </tfoot>
  </table>

  <div class="rodape">
    Documento gerado por ChargeGrid Intelligence em {datetime.now(UTC).strftime("%d/%m/%Y")}.
    Os valores refletem a tarifa vigente no momento de cada trecho da recarga.
  </div>
</body></html>"""
