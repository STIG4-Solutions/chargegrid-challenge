"""`patrocinador = 'frota'` sai; `fleet_id` vira ELEGIBILIDADE.

A decisao de escopo que ficou em aberto desde a fase 2 era "campanha de frota:
sim ou nao?". A resposta depende de uma coisa que o codigo ja dizia e que a
pergunta ignorava: **`patrocinador` nunca foi quem paga**.

O docstring de `models/campaign.py` amarra o bolso ao TIPO DE BENEFICIO, e nao ao
patrocinador: desconto na fatura sai do estabelecimento (e' a margem dele naquela
sessao), cashback na carteira sai da rede (credito so' vale dentro da plataforma
e e' resgatavel em qualquer lugar). Nao ha terceiro bolso, e `patrocinador` diz
ESCOPO - onde a campanha vale e quem a administra.

Entao `'frota'` como patrocinador nunca teve mecanismo atras. Era um valor que o
schema aceitava, que a validacao recusava com 422 e que a consulta de
elegibilidade filtrava fora - inalcancavel pelos tres lados. Mesma classe de
defeito que `inadimplente` era antes da 0023: declarado e impossivel.

Fazer dele verdade exigiria dar bolso a frota - `fleet_invoices` com ciclo,
cobranca e inadimplencia, como a plataforma tem. Seria inventar um modelo
comercial que ninguem pediu, a partir de um `billing_email` que e' a unica pista
de que alguem pensou nisso.

O QUE SOBRA, e e' a parte util: campanha restrita aos motoristas de uma frota.
Isso nao precisa de bolso nenhum - quem paga continua sendo o estabelecimento ou
a rede, pelo tipo de beneficio - e a coluna `fleet_id` ja existia. Ela deixa de
ser "quem paga" e passa a ser "para quem vale", o que a torna combinavel com os
dois patrocinadores: a rede pode dar cashback so' para a frota X, e um posto pode
dar desconto so' para a frota da empresa vizinha.

Revision ID: 0024_campanha_de_frota
Revises: 0023_cobranca_vence
Create Date: 2026-09-12
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0024_campanha_de_frota"
down_revision: str | None = "0023_cobranca_vence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nenhuma linha para migrar: o valor era inalcancavel, entao nao existe
    # campanha com `patrocinador = 'frota'` em banco nenhum. A guarda abaixo
    # esta aqui para o caso de eu estar errado sobre isso.
    op.execute(
        "DO $$ BEGIN "
        "IF EXISTS (SELECT 1 FROM campaigns WHERE patrocinador = 'frota') THEN "
        "RAISE EXCEPTION 'ha campanha com patrocinador frota - migre antes de remover o valor'; "
        "END IF; END $$;"
    )

    op.drop_constraint("patrocinador", "campaigns", type_="check")
    op.create_check_constraint(
        "patrocinador", "campaigns", "patrocinador IN ('rede', 'site')"
    )

    # `escopo_coerente` passa a falar so' de `site_id`, que e' o que o
    # patrocinador determina. `fleet_id` sai da regra porque virou um filtro
    # independente: vale com qualquer patrocinador, e nulo significa "todo mundo".
    op.drop_constraint("escopo_coerente", "campaigns", type_="check")
    op.create_check_constraint(
        "escopo_coerente",
        "campaigns",
        "(patrocinador = 'site' AND site_id IS NOT NULL)"
        " OR (patrocinador = 'rede' AND site_id IS NULL)",
    )


def downgrade() -> None:
    op.drop_constraint("escopo_coerente", "campaigns", type_="check")
    op.drop_constraint("patrocinador", "campaigns", type_="check")
    op.create_check_constraint(
        "patrocinador", "campaigns", "patrocinador IN ('rede', 'site', 'frota')"
    )
    op.create_check_constraint(
        "escopo_coerente",
        "campaigns",
        "(patrocinador = 'site' AND site_id IS NOT NULL AND fleet_id IS NULL)"
        " OR (patrocinador = 'frota' AND fleet_id IS NOT NULL AND site_id IS NULL)"
        " OR (patrocinador = 'rede' AND site_id IS NULL AND fleet_id IS NULL)",
    )
