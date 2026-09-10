"""Identificador estavel do site, para o modelo de previsao.

O modelo de previsao de demanda trata a estacao como variavel categorica: ele
aprende um comportamento por local e guarda a lista de locais conhecidos dentro
do artefato treinado. Local que ele nao viu no treino vira categoria
desconhecida e cai no fallback de media movel - silenciosamente, sem erro, com
a tela continuando a parecer correta.

Isso torna `sites.id` inadequado como chave de treino: o UUID e' sorteado a cada
`create_all`, a cada `downgrade` seguido de `upgrade` e a cada reseed do banco de
desenvolvimento. O artefato sobreviveria ao proximo reset por poucas horas e
depois passaria a prever tudo por fallback sem ninguem notar.

O `slug` existe para ser a parte do site que NAO muda: escrito a mao no seed,
estavel entre reconstrucoes do banco, e legivel em `estacoes_treinadas` dentro do
artefato - o que torna a divergencia entre modelo e banco visivel a olho nu.

Revision ID: 0014_slug_do_site
Revises: 0013_reportes_e_frota
Create Date: 2026-09-09
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0014_slug_do_site"
down_revision: str | None = "0013_reportes_e_frota"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Acentos e cedilha viram a letra base. `unaccent` faria isso melhor, mas e' uma
# extensao que pode nao estar instalada, e uma migration que depende de
# CREATE EXTENSION falha justamente onde nao ha superusuario.
_COM_ACENTO = "áàâãäéèêëíìîïóòôõöúùûüçÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ"
_SEM_ACENTO = "aaaaaeeeeiiiiooooouuuucAAAAAEEEEIIIIOOOOOUUUUC"

# Preenche as linhas que ja existem. O slug sai do nome, e o desempate por
# `row_number` cobre dois sites homonimos - possivel numa rede com "Matriz" em
# duas cidades. Ordenar por (created_at, id) mantem o resultado deterministico:
# rodar isto duas vezes sobre o mesmo dado produz os mesmos slugs.
_BACKFILL = sa.text(
    f"""
    UPDATE sites AS s SET slug = t.slug
    FROM (
        SELECT id,
               CASE WHEN rn = 1 THEN base ELSE base || '-' || rn::text END AS slug
        FROM (
            SELECT id,
                   base,
                   row_number() OVER (PARTITION BY base ORDER BY created_at, id) AS rn
            FROM (
                SELECT id,
                       created_at,
                       COALESCE(
                           NULLIF(
                               trim(BOTH '-' FROM left(
                                   regexp_replace(
                                       lower(translate(name, '{_COM_ACENTO}', '{_SEM_ACENTO}')),
                                       '[^a-z0-9]+', '-', 'g'
                                   ), 32)),
                               ''
                           ),
                           'site'
                       ) AS base
                FROM sites
            ) AS nomes
        ) AS numerados
    ) AS t
    WHERE s.id = t.id
    """
)


def upgrade() -> None:
    # Entra nulavel e so' depois vira obrigatoria: a coluna precisa existir para o
    # backfill rodar, e um NOT NULL sem default recusaria a propria criacao num
    # banco que ja tem sites.
    op.add_column("sites", sa.Column("slug", sa.String(40), nullable=True))
    op.execute(_BACKFILL)
    op.alter_column("sites", "slug", nullable=False)
    op.create_index("uq_sites_slug", "sites", ["slug"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_sites_slug", table_name="sites")
    op.drop_column("sites", "slug")
