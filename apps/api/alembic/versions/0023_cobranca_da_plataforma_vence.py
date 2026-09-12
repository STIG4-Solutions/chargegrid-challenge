"""A cobranca da plataforma passa a poder VENCER.

`platform_invoices` tinha `vence_em` desde a 0019 e nenhum codigo a lia. Os
estados eram `aberta`, `paga` e `cancelada`: uma cobranca passada do prazo ficava
`aberta` para sempre, indistinguivel de uma emitida ontem.

Do outro lado, `site_subscriptions` aceita `inadimplente` no CHECK desde a mesma
migration, o painel tem um badge vermelho para ele em `Contract.jsx` - e NADA no
sistema jamais atribuia esse estado. Uma coluna escrita e nunca lida de um lado,
um estado declarado e inalcancavel do outro.

ESTA MIGRATION E' A METADE DE SCHEMA DE UMA DECISAO DE ESCOPO, e a decisao vale
registrada aqui porque e' ela que explica o recorte:

  NAO se constroi liquidacao bancaria B2B. Cobrar o estabelecimento por Pix
  exigiria credencial de PSP DA PLATAFORMA - a chave da GoodWe, nao a do lojista,
  que e' o que `SitePaymentMethod` guarda. Nao existe essa conta, e o
  `liquidacao_automatica: false` da resposta continua verdadeiro.

  SE constroi o ciclo da inadimplencia, que nao depende de PSP nenhum: a
  cobranca vence, o contrato fica inadimplente, para de renovar sozinho, e a
  baixa manual desfaz os dois. E' o que faz `vence_em` deixar de ser enfeite e
  `inadimplente` deixar de ser um estado que so' existe no CHECK.

O QUE DELIBERADAMENTE NAO ACONTECE: o servico NAO e' cortado. Quem deixou de
pagar foi o estabelecimento; quem ficaria sem recarregar seria o motorista, que
nao tem nada com isso. A consequencia da inadimplencia e' parar de renovar e
aparecer em vermelho na tela de quem pode resolver.

Revision ID: 0023_cobranca_vence
Revises: 0022_nomes_de_constraint
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0023_cobranca_vence"
down_revision: str | None = "0022_nomes_de_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nome CURTO: a convencao de `Base.metadata` prefixa `ck_<tabela>_`. Ver 0022.
    op.drop_constraint("estado_conhecido", "platform_invoices", type_="check")
    op.create_check_constraint(
        "estado_conhecido",
        "platform_invoices",
        "estado IN ('aberta', 'vencida', 'paga', 'cancelada')",
    )

    # As que ja passaram do prazo viram `vencida` agora. Sem este passo, o estado
    # novo so' valeria para cobrancas futuras e o painel continuaria mostrando
    # como "aberta" uma divida de tres meses atras - que e' o caso que mais
    # importa mostrar.
    op.execute(
        "UPDATE platform_invoices SET estado = 'vencida' "
        "WHERE estado = 'aberta' AND vence_em < CURRENT_DATE"
    )

    # E os contratos que ficaram com alguma delas. Coerencia desde o primeiro
    # minuto: o worker faria isso no ciclo seguinte, mas ate la' a tela mostraria
    # cobranca vencida num contrato "ativa".
    op.execute(
        """
        UPDATE site_subscriptions s SET estado = 'inadimplente'
        WHERE s.estado = 'ativa'
          AND EXISTS (
              SELECT 1 FROM platform_invoices i
              WHERE i.site_subscription_id = s.id AND i.estado = 'vencida'
          )
        """
    )


def downgrade() -> None:
    op.execute(
        "UPDATE site_subscriptions SET estado = 'ativa' WHERE estado = 'inadimplente'"
    )
    op.execute("UPDATE platform_invoices SET estado = 'aberta' WHERE estado = 'vencida'")
    op.drop_constraint("estado_conhecido", "platform_invoices", type_="check")
    op.create_check_constraint(
        "estado_conhecido",
        "platform_invoices",
        "estado IN ('aberta', 'paga', 'cancelada')",
    )
