"""A regua de ano-a-ano ganha nome proprio em `fonte`.

POR QUE UMA FONTE NOVA. Quando o modelo perde da regua, `exportar.py` grava o
numero da regua e `fonte` diz qual regua foi. Ate aqui havia uma regua mensal so'
- a media movel de 28 dias - e `media_movel` a nomeava.

Agora ha' duas, e a nova e' muito melhor. Medido com walk-forward de 24 meses no
banco local, n=168 registros mensais:

    media movel de 28 dias                  13,57%
    mesmo mes um ano antes x crescimento     9,95%

3,6 pontos de diferenca entre duas coisas que `fonte = 'media_movel'` chamaria
pelo mesmo nome. Gravar a regua de ano-a-ano como `media_movel` seria dizer ao
operador que o numero na tela e' uma media dos ultimos 28 dias quando nao e' - e o
aviso que a tela monta a partir de `fonte` descreveria o previsor errado.

A BANDA CONTINUA SO' DO MODELO. `banda_com_quantil` nao muda. Os fatores conformes
que a faixa usa sao calibrados nos residuos DO MODELO; aplica-los a uma regua
seria emprestar a incerteza de um previsor para outro. Regua sem faixa e' o
comportamento honesto, e e' o que `kwh_p10 IS NULL` ja' significa.

Revision ID: 0029_fonte_ano_a_ano
Revises: 0028_previsao_por_janela
"""

from __future__ import annotations

from alembic import op

revision: str = "0029_fonte_ano_a_ano"
down_revision: str | None = "0028_previsao_por_janela"
branch_labels: str | None = None
depends_on: str | None = None

# `ano_a_ano` entra no fim: a ordem e' historica, e manter as anteriores no lugar
# faz o diff desta migracao mostrar so' o que ela acrescenta.
FONTES = ("modelo", "media_movel", "media_dow", "perfil_hora", "tendencia", "ano_a_ano")
FONTES_ANTERIORES = FONTES[:-1]


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    # Nome CURTO do CHECK. A convencao de nomes deste projeto prefixa
    # `ck_<tabela>_`, e passar o nome completo produz
    # `ck_site_forecasts_ck_site_forecasts_...`, que nao existe - e a queda leva
    # toda a suite junto, porque o banco de teste fica no meio da migracao.
    op.drop_constraint("fonte_conhecida", "site_forecasts", type_="check")
    op.create_check_constraint(
        "fonte_conhecida", "site_forecasts", f"fonte IN ({_lista(FONTES)})"
    )


def downgrade() -> None:
    # Volta as linhas que usam a fonte nova para `media_movel` ANTES de estreitar
    # o CHECK. Sem isto o `create_check_constraint` falha na validacao das linhas
    # existentes, e o downgrade quebra em vez de desfazer.
    #
    # `media_movel` e nao `modelo`: perder a distincao entre as duas reguas e' o
    # que esta' migracao desfaz, e cair para a regua mais conservadora e' o menos
    # errado dos dois.
    op.execute("UPDATE site_forecasts SET fonte = 'media_movel' WHERE fonte = 'ano_a_ano'")
    op.drop_constraint("fonte_conhecida", "site_forecasts", type_="check")
    op.create_check_constraint(
        "fonte_conhecida", "site_forecasts", f"fonte IN ({_lista(FONTES_ANTERIORES)})"
    )
