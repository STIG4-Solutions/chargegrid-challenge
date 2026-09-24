"""A previsao passa a ter JANELA, e a rede passa a ter linha propria.

A tabela guardava uma previsao por praca e por competencia: um total mensal, e
nada mais. O pedido e' cobrir hora, dia, semana, mes e ano, em kWh e em reais - e
nenhuma das cinco cabe no formato atual, porque `competencia` e' `Date` e a chave
unica e' `(site_id, competencia)`. Duas janelas do mesmo mes colidiriam na
primeira gravacao.

POR QUE A REDE, E NAO SO' A PRACA. Medido no banco: a celula hora x praca tem 20%
de ocupacao, com 1,26 sessao quando ocupada; a celula da REDE tem 54%, e no plato
diurno chega a 79% dos dias. Prever quanto UMA praca vende as 15h de uma
quarta-feira e' prever se um carro especifico aparece, o que e' ruido de contagem.
Prever o mesmo para a rede inteira nao e'. Entao `site_id` passa a aceitar NULL, e
NULL significa "a rede toda".

`UNIQUE NULLS NOT DISTINCT` e' o que faz isso funcionar. No padrao do SQL dois
NULL nunca conflitam, logo a chave unica ignoraria as linhas de rede por
completo: cada execucao do job empilharia uma versao nova e ninguem saberia qual
vale. PostgreSQL 15 em diante permite declarar que NULL conflita com NULL, e o
banco deste projeto e' 18.

A BANDA DEIXA DE SER PRIVILEGIO DO MODELO. `banda_so_do_modelo` exigia
`fonte = 'modelo'` para haver p10/p90, e a intencao era certa: desenhar incerteza
em volta de uma media movel daria ares de previsao a uma conta de padaria. Mas na
janela de UMA HORA a faixa e' o produto. Medido: a melhor regua horaria erra 50%
na rede e a referencia que usa o futuro erra 50,2% - a folga e' de -0,05 ponto, ou
seja, o erro e' ruido de contagem e nenhum modelo o remove. Ali o numero honesto
nao e' um ponto, e' uma faixa com cobertura aferida. Entao a banda passa a ser
permitida para as fontes que declaram quantil, e segue proibida para a media
movel simples.

`competencia` FICA. Ela e' redundante com `bucket_inicio` para a janela mensal,
mas a rota `/demand/energy-forecast` e `test_previsao.py` a usam hoje, e este
commit nao quebra nenhuma das duas - a janela mensal por praca continua
respondendo exatamente como antes.

Revision ID: 0028_previsao_por_janela
Revises: 0027_catalogo_de_planos
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0028_previsao_por_janela"
down_revision: str | None = "0027_catalogo_de_planos"
branch_labels: str | None = None
depends_on: str | None = None

# As cinco janelas, e o mes como padrao. Toda linha que existe hoje E' mensal,
# entao o `server_default` ja' e' o backfill - nao precisa de UPDATE.
JANELAS = ("hora", "dia", "semana", "mes", "ano")

# De onde o numero gravado veio. As tres primeiras ja' existiam ou sao reguas
# sem ML; `perfil_hora` e `tendencia` nascem aqui.
FONTES = ("modelo", "media_movel", "media_dow", "perfil_hora", "tendencia")

# Quais fontes declaram quantil e portanto podem trazer faixa. `media_movel` e
# `media_dow` sao medias: nao tem dispersao declarada e continuam sem banda.
FONTES_COM_BANDA = ("modelo", "perfil_hora", "tendencia")


def _lista(valores: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in valores)


def upgrade() -> None:
    op.add_column(
        "site_forecasts",
        sa.Column("granularidade", sa.String(8), nullable=False, server_default="mes"),
    )
    op.create_check_constraint(
        "granularidade_conhecida",
        "site_forecasts",
        f"granularidade IN ({_lista(JANELAS)})",
    )

    # O inicio do bucket, com fuso. `competencia` e' `Date` e nao resolve hora;
    # sem isto a janela horaria nao teria onde dizer QUAL hora.
    op.add_column(
        "site_forecasts",
        sa.Column("bucket_inicio", sa.DateTime(timezone=True), nullable=True),
    )
    # O backfill le' o fuso DA PRACA, e nao UTC: `competencia` sempre foi o
    # primeiro dia do mes no calendario local de quem opera. Converter como se
    # fosse UTC deslocaria a competencia de marco para fevereiro em Sao Paulo.
    op.execute(
        """
        UPDATE site_forecasts f
           SET bucket_inicio = (f.competencia::timestamp AT TIME ZONE s.timezone)
          FROM sites s
         WHERE s.id = f.site_id
        """
    )
    op.alter_column("site_forecasts", "bucket_inicio", nullable=False)

    # NULL passa a significar "a rede inteira". A FK continua valendo para as
    # linhas que tem praca.
    op.alter_column("site_forecasts", "site_id", nullable=True)

    op.drop_constraint("uq_site_forecasts_site_competencia", "site_forecasts", type_="unique")
    # `NULLS NOT DISTINCT` nao tem equivalente no `create_unique_constraint` do
    # alembic; sem ele, as linhas de rede nunca conflitariam entre si e o UPSERT
    # do job empilharia uma versao por execucao.
    op.execute(
        """
        ALTER TABLE site_forecasts
          ADD CONSTRAINT uq_site_forecasts_janela
          UNIQUE NULLS NOT DISTINCT (site_id, granularidade, bucket_inicio)
        """
    )

    # A leitura passa a ser sempre "esta janela, deste escopo, neste intervalo".
    op.create_index(
        "ix_site_forecasts_janela",
        "site_forecasts",
        ["granularidade", "bucket_inicio"],
    )

    # Nome CURTO. A convencao de nomes prefixa `ck_<tabela>_` sozinha, e
    # passar o nome completo aqui pede
    # `ck_site_forecasts_ck_site_forecasts_fonte_conhecida`, que nao existe -
    # a mesma pegadinha que o downgrade da 0020 anota, e na qual eu cai.
    op.drop_constraint("fonte_conhecida", "site_forecasts", type_="check")
    op.create_check_constraint(
        "fonte_conhecida", "site_forecasts", f"fonte IN ({_lista(FONTES)})"
    )

    op.drop_constraint("banda_so_do_modelo", "site_forecasts", type_="check")
    op.create_check_constraint(
        "banda_com_quantil",
        "site_forecasts",
        f"fonte IN ({_lista(FONTES_COM_BANDA)}) OR kwh_p10 IS NULL",
    )


def downgrade() -> None:
    # Volta ao formato de uma janela por praca. As linhas que NAO sao mensais ou
    # que sao da rede nao cabem no formato antigo e vao embora - nao ha como
    # representa-las, e mante-las quebraria a chave unica que se recria abaixo.
    op.execute(
        "DELETE FROM site_forecasts WHERE granularidade <> 'mes' OR site_id IS NULL"
    )

    op.drop_constraint("banda_com_quantil", "site_forecasts", type_="check")
    op.create_check_constraint(
        "banda_so_do_modelo", "site_forecasts", "fonte = 'modelo' OR kwh_p10 IS NULL"
    )

    op.drop_constraint("fonte_conhecida", "site_forecasts", type_="check")
    op.create_check_constraint(
        "fonte_conhecida", "site_forecasts", "fonte IN ('modelo', 'media_movel')"
    )

    op.drop_index("ix_site_forecasts_janela", table_name="site_forecasts")
    op.drop_constraint("uq_site_forecasts_janela", "site_forecasts", type_="unique")
    op.alter_column("site_forecasts", "site_id", nullable=False)
    op.create_unique_constraint(
        "uq_site_forecasts_site_competencia", "site_forecasts", ["site_id", "competencia"]
    )

    op.drop_column("site_forecasts", "bucket_inicio")
    op.drop_constraint("granularidade_conhecida", "site_forecasts", type_="check")
    op.drop_column("site_forecasts", "granularidade")
