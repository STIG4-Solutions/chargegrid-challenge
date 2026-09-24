"""Monta o painel diario e o cadastro de estacoes a partir do banco do ChargeGrid.

O pipeline de previsao foi escrito contra CDRs no formato OCPI. O ChargeGrid tem
`charging_sessions`, que e' a mesma informacao com outros nomes - o adaptador
`pipeline/ingest/cdr.py` existe justamente para isso. Aqui a conversao e' feita
em SQL, porque agregar dia a dia no banco e' mais barato que trazer vinte mil
sessoes para dentro do pandas.

CHAVE DE TREINO. O identificador do local e' `sites.slug`, nunca o `id`. O UUID e'
sorteado a cada reseed do banco; o slug e' escrito a mao no seed e sobrevive.
Treinar sobre o `id` faria o artefato virar inutil no proximo reset - e o pior e'
que ele nao daria erro: cairia em fallback para tudo, em silencio.
"""

from __future__ import annotations

import os
from datetime import date

import pandas as pd
from sqlalchemy import create_engine, text

# O arquetipo do local continua NAO existindo como coluna: o ChargeGrid nao
# precisa dele para operar, e criar a coluna so' para o modelo poria uma decisao
# de modelagem dentro do dominio de quem administra potencia. A decisao segue
# aqui, ao lado de quem consome.
#
# O QUE MUDOU: era um mapa de SLUG para arquetipo, escrito a mao. Isso bastava
# enquanto so' o seed criava praca. Desde que o painel ganhou "Nova praca",
# qualquer praca nascida pelo produto caia em "corporativo" por omissao - e
# silenciosamente, porque um padrao nao avisa. Foi o que aconteceu no staging, com
# duas pracas novas que o modelo leria como corporativas.
#
# Agora sai do HARDWARE, que o proprio banco declara. Uma praca nova nasce
# classificada, sem ninguem editar codigo.
#
# O limite de 100 kW separa rodovia de shopping porque e' onde o negocio muda, nao
# por gosto: ninguem para tres horas na estrada, e um DC de 150 kW existe para
# encher o tanque em quinze minutos. Abaixo disso o carro fica enquanto a pessoa
# faz outra coisa.
LIMITE_DC_DE_RODOVIA_KW = 100.0


def arquetipo_de(tem_dc: bool, tem_trifasico: bool, potencia_kw: float) -> str:
    """O carater do local, deduzido do equipamento instalado.

    E' PROXY, e vale dizer onde ele erra: um shopping que instale DC de 150 kW
    sera' lido como rodovia. O erro e' de perfil, nao de operacao - o modelo
    aprende a sazonalidade errada para aquela praca -, e some quando houver
    operacao real para medir. O alternativo era continuar com a lista de slugs,
    que erra em TODA praca nova.
    """
    if tem_dc:
        return "rodovia" if potencia_kw >= LIMITE_DC_DE_RODOVIA_KW else "shopping"
    return "corporativo" if tem_trifasico else "condominio"


# O driver deste processo. `psycopg` e nao `asyncpg`: o pipeline e' pandas, e
# pandas nao fala asyncpg - que e' o driver da API.
DRIVER = "postgresql+psycopg"

# Driver que a URL da API traz e que precisa ser trocado. A mesma string de
# conexao serve aos dois processos; o que muda e' quem vai falar com o banco.
_DRIVERS_DE_OUTREM = ("postgresql+asyncpg://", "postgres://", "postgresql://")


def com_driver_sincrono(url: str) -> str:
    """A mesma URL, apontando para o driver deste processo.

    Existe para que o job de previsao reuse o segredo que o workflow de
    migrations ja' tem (`STAGING_DATABASE_URL`) em vez de exigir outras cinco
    variaveis. Segredo duplicado e' segredo que sai de sincronia - e o sintoma
    seria o pipeline treinando contra um banco e gravando noutro.

    `postgres://` entra na lista porque e' o formato que varios provedores
    entregam, e o SQLAlchemy nao o aceita sem driver.

    TROCAR O DRIVER NAO E' SO' TROCAR O PREFIXO. Os parametros de conexao tem
    nomes diferentes em cada um, e o TLS e' o que aparece primeiro: asyncpg le
    `ssl=require`, libpq (psycopg) le `sslmode=require`. A primeira versao desta
    funcao trocava so' o prefixo, e o job morreu contra o Neon com
    `invalid connection option "ssl"` - depois de resolver o host e as
    credenciais, o que torna a mensagem enganosa: parece problema de rede.
    """
    for prefixo in _DRIVERS_DE_OUTREM:
        if url.startswith(prefixo):
            url = DRIVER + "://" + url[len(prefixo) :]
            break

    if not url.startswith(DRIVER + "://"):
        return url
    return _com_parametros_do_libpq(url)


def _com_parametros_do_libpq(url: str) -> str:
    """Renomeia os parametros de consulta que mudam de nome entre os drivers.

    So' o nome muda: o vocabulario de valores e' o mesmo (`require`, `disable`,
    `prefer`, `verify-full`), entao renomear a chave basta.

    Um `sslmode` que ja' venha na URL vence o `ssl`: se quem escreveu o segredo
    foi explicito no formato do libpq, nao e' este codigo que vai contradizer.
    """
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    partes = urlsplit(url)
    if not partes.query:
        return url

    consulta = parse_qsl(partes.query, keep_blank_values=True)
    ja_tem_sslmode = any(chave == "sslmode" for chave, _ in consulta)

    traduzida = [
        ("sslmode", valor) if chave == "ssl" and not ja_tem_sslmode else (chave, valor)
        for chave, valor in consulta
    ]
    if ja_tem_sslmode:
        traduzida = [(c, v) for c, v in traduzida if c != "ssl"]

    return urlunsplit(partes._replace(query=urlencode(traduzida)))


def url_do_banco() -> str:
    """De onde ler o historico.

    `DATABASE_URL_OVERRIDE` vence quando existe - e' a mesma variavel que o
    ambiente do Alembic usa, entao apontar o pipeline para staging nao inventa
    uma segunda forma de dizer a mesma coisa. Sem ela, as variaveis soltas do
    `.env`, que e' como o compose local funciona.
    """
    override = os.environ.get("DATABASE_URL_OVERRIDE")
    if override:
        return com_driver_sincrono(override)

    usuario = os.environ.get("POSTGRES_USER", "chargegrid")
    senha = os.environ.get("POSTGRES_PASSWORD", "")
    host = os.environ.get("POSTGRES_HOST", "localhost")
    porta = os.environ.get("POSTGRES_PORT", "5432")
    banco = os.environ.get("POSTGRES_DB", "chargegrid")
    return f"{DRIVER}://{usuario}:{senha}@{host}:{porta}/{banco}"


def conectar():
    return create_engine(url_do_banco(), future=True)


# Uma linha por (site, dia local). `date_trunc` no fuso do site, e nao em UTC:
# uma recarga das 22h em Sao Paulo e' do dia 1 em UTC, e contar no dia errado
# desloca a curva semanal inteira que o modelo tenta aprender.
_SESSOES = text(
    """
    SELECT s.slug AS location_id,
           (cs.started_at AT TIME ZONE s.timezone)::date AS date,
           sum(cs.energy_kwh)                            AS kwh,
           count(*)::float                               AS sessions,
           coalesce(sum(i.total), 0)                     AS revenue
    FROM charging_sessions cs
    JOIN sites s ON s.id = cs.site_id
    LEFT JOIN invoices i ON i.session_id = cs.id AND i.status <> 'VOID'
    WHERE cs.started_at IS NOT NULL
      AND cs.state = 'BILLED'
    GROUP BY 1, 2
    """
)

_ESTACOES = text(
    """
    SELECT s.slug                                   AS location_id,
           s.name                                   AS location_name,
           (s.created_at AT TIME ZONE s.timezone)::date AS opened_at,
           count(cp.id)                             AS n_connectors,
           coalesce(max(cp.rated_kw), 0)            AS max_electric_power,
           bool_or(cp.rated_kw >= 50)               AS tem_dc,
           bool_or(cp.phase_type = 'THREE')         AS tem_trifasico
    FROM sites s
    LEFT JOIN charge_points cp ON cp.site_id = s.id
    GROUP BY s.slug, s.name, s.created_at, s.timezone
    """
)

# A tarifa por kWh que vale hoje em cada site. O modelo nao preve dinheiro: ele
# preve kWh, e o faturamento sai depois como kWh x tarifa. Por isso um reajuste
# de preco nao invalida o artefato.
_TARIFAS = text(
    """
    SELECT DISTINCT ON (s.slug)
           s.slug                AS location_id,
           t.price_per_kwh       AS price_per_kwh,
           (s.created_at AT TIME ZONE s.timezone)::date AS vigencia_inicio
    FROM sites s
    JOIN tariffs t ON t.id = s.default_tariff_id
    ORDER BY s.slug, t.created_at DESC
    """
)


def _tipo_de_potencia(linha) -> str:
    if linha["tem_dc"]:
        return "DC"
    return "AC_3_PHASE" if linha["tem_trifasico"] else "AC_1_PHASE"


def carregar(engine, ate: date | None = None) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Devolve (painel, estacoes, tarifas) no formato que o pipeline espera."""
    estacoes = pd.read_sql_query(_ESTACOES, engine)
    if estacoes.empty:
        raise SystemExit("nenhum site no banco - rode o seed antes")

    estacoes["archetype"] = (
        estacoes.apply(
            lambda linha: arquetipo_de(
                bool(linha["tem_dc"]),
                bool(linha["tem_trifasico"]),
                float(linha["max_electric_power"]),
            ),
            axis=1,
        ).astype("string")
        if len(estacoes)
        else pd.Series([], dtype="string")
    )
    estacoes["power_type"] = estacoes.apply(_tipo_de_potencia, axis=1).astype("string")
    estacoes["location_id"] = estacoes["location_id"].astype("string")
    estacoes["location_name"] = estacoes["location_name"].astype("string")
    estacoes["opened_at"] = pd.to_datetime(estacoes["opened_at"])
    estacoes["n_connectors"] = estacoes["n_connectors"].astype("int64")
    estacoes["max_electric_power"] = estacoes["max_electric_power"].astype("float64")
    estacoes = estacoes.drop(columns=["tem_dc", "tem_trifasico"])

    tarifas = pd.read_sql_query(_TARIFAS, engine)
    tarifas["location_id"] = tarifas["location_id"].astype("string")
    tarifas["price_per_kwh"] = tarifas["price_per_kwh"].astype("float64")
    tarifas["vigencia_inicio"] = pd.to_datetime(tarifas["vigencia_inicio"])

    medido = pd.read_sql_query(_SESSOES, engine)
    medido["location_id"] = medido["location_id"].astype("string")
    medido["date"] = pd.to_datetime(medido["date"])

    painel = _grade_completa(estacoes, medido, ate or date.today())
    painel = painel.merge(tarifas[["location_id", "price_per_kwh"]], on="location_id", how="left")
    # O ChargeGrid nao registra indisponibilidade por DIA - `charge_point_faults`
    # guarda falhas por ponto, com inicio e fim, e reduzi-las a um booleano
    # diario e' uma decisao que ainda nao foi tomada. True em tudo e' honesto
    # enquanto isso: o campo diz "nao sabemos de indisponibilidade", nao "houve".
    painel["is_available"] = True
    return painel, estacoes, tarifas


def _grade_completa(estacoes: pd.DataFrame, medido: pd.DataFrame, ate: date) -> pd.DataFrame:
    """Um dia por linha, inclusive os dias sem nenhuma recarga.

    Dia sem sessao e' zero, e nao ausencia: a estacao estava la' e ninguem
    carregou. Deixar o buraco faria a media movel pular os dias fracos e o
    modelo aprenderia uma demanda maior do que a real - justamente nos fins de
    semana de local corporativo, que sao o que da carater a serie.
    """
    fim = pd.Timestamp(ate)
    pedacos = []
    for _, estacao in estacoes.iterrows():
        inicio = pd.Timestamp(estacao["opened_at"])
        if inicio > fim:
            continue
        pedacos.append(
            pd.DataFrame(
                {
                    "location_id": estacao["location_id"],
                    "date": pd.date_range(inicio, fim, freq="D"),
                }
            )
        )
    if not pedacos:
        # TODA praca nasceu depois do corte. `pd.concat([])` levanta
        # "No objects to concatenate", que nao diz nada a quem abre a execucao -
        # foi o que a primeira corrida do job em staging produziu, onde a unica
        # praca abriu em 2026-09-03 contra um corte em 2026-08-31.
        #
        # Nao ha painel possivel aqui, e insistir seria pior: o modelo exige 150
        # dias de energia e a media movel exige 28. A mensagem diz o corte, a
        # praca mais antiga, e o que fazer.
        mais_antiga = pd.to_datetime(estacoes["opened_at"]).min()
        raise SystemExit(
            f"nenhuma praca havia aberto ate' {fim.date()}. A mais antiga abriu "
            f"em {mais_antiga.date()}, {(mais_antiga - fim).days} dia(s) DEPOIS "
            "do corte. O corte padrao de `treinar.py` e' o ultimo dia do mes "
            "anterior; use `--ate` para alcancar a operacao que existe, ou espere "
            "haver historico. O modelo pede 150 dias de energia por praca, e a "
            "media movel pede 28."
        )

    grade = pd.concat(pedacos, ignore_index=True)
    grade["location_id"] = grade["location_id"].astype("string")

    painel = grade.merge(medido, on=["location_id", "date"], how="left")
    painel["kwh"] = painel["kwh"].astype("float64").fillna(0.0)
    painel["sessions"] = painel["sessions"].astype("float64").fillna(0.0)
    painel["revenue"] = painel["revenue"].astype("float64").fillna(0.0)
    return painel


def resumo(painel: pd.DataFrame) -> str:
    por_local = painel.groupby("location_id", observed=True).agg(
        dias=("date", "size"),
        com_energia=("kwh", lambda s: int((s > 0).sum())),
        kwh=("kwh", "sum"),
    )
    linhas = [
        f"  {loc:<28} {int(r.dias):>5} dias  {int(r.com_energia):>5} com energia"
        f"  {r.kwh / 1000:>8.1f} MWh"
        for loc, r in por_local.iterrows()
    ]
    return "\n".join(linhas)
