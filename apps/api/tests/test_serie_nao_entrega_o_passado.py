"""A série de previsão entrega o que ainda não começou, e só isso.

O DEFEITO, e ele chegou ao ambiente. `serie_por_janela` fazia
`order_by(bucket_inicio.asc()).limit(n)` sem filtrar o passado, e o docstring dela
promete "os PROXIMOS buckets desta janela". Ela devolvia os mais antigos guardados.

Medido em staging as 18:06 UTC, logo depois de o job rodar:

    janela   buckets   de ... ate                      passados
    hora        336    24/09 03:00 ... 08/10 02:00          40
    dia          60    24/09 ... 22/11                       2
    semana       15    28/09 ... 04/01                        0
    mes          11    01/10 ... 01/08                        0
    ano           2    2027 ... 2028                          0

O padrao da tela para a horaria e' 48 buckets. Com 40 passados no comeco, o operador
via 40 horas que JA' ACONTECERAM e so' 8 futuras - e a horaria e' a unica janela
servida com FAIXA, cuja aceitacao e' por cobertura.

POR QUE NENHUM TESTE PEGOU. Os que existiam gravavam buckets FUTUROS, entao o filtro
e' invisivel para eles: passaram sem alteracao depois da correcao. Um teste que so'
usa o caminho felizmente comum nao prende o caminho que quebra.

A causa era a rota, nao o dado: `gravar.py` escreve uma janela que comeca no ultimo
bucket do painel, e o painel fica atras de "agora". Guardar bucket passado e'
inofensivo - cada execucao os reescreve.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import func, text

from app.models.forecast import SiteForecast
from app.services import forecast_service

AGORA = datetime.now(UTC)

# O instante do BEGIN da transacao do teste. `now()` no PostgreSQL e' estavel dentro
# da transacao - vale o BEGIN, e nao o momento da chamada -, e e' isso que permite
# gravar um bucket exatamente no limiar sem depender de tempo de parede.
AGORA_DO_BANCO = func.now()
UM_MICROSSEGUNDO = text("interval '1 microsecond'")


async def _bucket(
    db,
    site,
    inicio,
    *,
    janela: str = "hora",
    kwh: float = 10.0,
    competencia: date | None = None,
):
    """Um bucket. `inicio` aceita datetime OU expressao SQL.

    A expressao existe para os dois testes de relogio, que precisam gravar em `now()`
    do BANCO. Nesses casos `competencia` vem explicita: `.date()` nao existe numa
    expressao SQL, e o campo nao participa do filtro que se testa aqui.
    """
    linha = SiteForecast(
        site_id=site.id,
        granularidade=janela,
        bucket_inicio=inicio,
        competencia=competencia
        or (inicio.date() if isinstance(inicio, datetime) else AGORA.date()),
        gerado_em=AGORA,
        kwh_previsto=Decimal(str(kwh)),
        kwh_p10=None,
        kwh_p90=None,
        modelo_aplicavel=True,
        fonte="media_dow",
        modelo_versao="2.0.0",
    )
    db.add(linha)
    await db.flush()
    return linha


def _inicios(saida: dict) -> list[str]:
    return [b["bucket_inicio"] for b in saida["buckets"]]


async def test_bucket_que_ja_passou_nao_aparece(db, site):
    """O defeito, em um assert.

    Uma hora de ontem e uma de amanha: a serie devolve UMA.
    """
    await _bucket(db, site, AGORA - timedelta(days=1), kwh=99)
    futuro = await _bucket(db, site, AGORA + timedelta(days=1), kwh=11)

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)

    assert _inicios(saida) == [futuro.bucket_inicio.isoformat()], saida["buckets"]


async def test_o_bucket_que_esta_correndo_tambem_sai(db, site):
    """`>` e nao `>=`.

    Uma previsao para a hora das 14h lida as 14h30 esta' metade vencida. Apresentá-la
    como previsao e' o mesmo defeito, um grau mais fino.

    O bucket e' gravado em `now()` EXATO - o do banco, estavel dentro da transacao -,
    entao ele fica no limiar: `>` o exclui e `>=` o incluiria. Uma versao anterior
    deste teste usava "meia hora atras", e ali os dois operadores concordam: a mutacao
    de `>` para `>=` sobrevivia.
    """
    await _bucket(db, site, AGORA_DO_BANCO, kwh=50)

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)

    assert saida["disponivel"] is False, (
        "o bucket que comeca AGORA entrou na serie - o filtro virou `>=`"
    )


async def test_a_comparacao_usa_o_relogio_do_BANCO(db, site):
    """`func.now()` e nao `datetime.now()` do processo da API.

    Sao relogios diferentes, e `bucket_inicio` e' TIMESTAMPTZ gravado pelo job - a
    comparacao tem de acontecer no mesmo relogio que gravou.

    O teste distingue os dois sem depender de tempo de parede: um bucket em
    `now() + 1us` esta' DEPOIS do BEGIN da transacao, entao o relogio do banco o
    inclui. O relogio do PROCESSO e' lido dentro de `serie_por_janela`, ou seja
    depois do insert e do flush - sempre mais tarde que o BEGIN -, e excluiria.
    """
    await _bucket(db, site, AGORA_DO_BANCO + UM_MICROSSEGUNDO, kwh=7)

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)

    assert saida["disponivel"] is True, (
        "o bucket logo apos o inicio da transacao foi excluido - a comparacao passou a "
        "usar o relogio do processo, que e' posterior ao do banco"
    )
    assert len(saida["buckets"]) == 1, saida["buckets"]


async def test_o_limite_conta_so_os_FUTUROS(db, site):
    """O assert que mede o impacto real.

    Com 40 passados e 8 futuros e um limite de 48, a versao antiga devolvia os 40
    passados mais 8 futuros. Aqui: 3 passados, 2 futuros, limite 3 - tem de sair 2
    futuros, e nao 3 passados.
    """
    for i in (3, 2, 1):
        await _bucket(db, site, AGORA - timedelta(hours=i), kwh=90 + i)
    esperados = []
    for i in (1, 2):
        esperados.append(await _bucket(db, site, AGORA + timedelta(hours=i), kwh=i))

    saida = await forecast_service.serie_por_janela(db, "hora", site.id, quantos=3)

    assert _inicios(saida) == [b.bucket_inicio.isoformat() for b in esperados]


async def test_a_ordem_dos_futuros_e_crescente(db, site):
    """Serie desenhada de tras para frente nao e' grafico."""
    for i in (3, 1, 2):
        await _bucket(db, site, AGORA + timedelta(hours=i), kwh=i)

    inicios = _inicios(await forecast_service.serie_por_janela(db, "hora", site.id))

    assert inicios == sorted(inicios), inicios


async def test_tudo_passado_diz_que_PASSOU_e_nao_que_falta_calcular(db, site):
    """Dois motivos para a tela vazia, e nao um.

    "Nunca calculado" pede espera; "tudo que foi calculado ja' passou" pede uma
    execucao nova. Juntar os dois faria o operador esperar por um calculo que ja'
    rodou e envelheceu - que e' o pior dos dois erros, porque nao produz acao.
    """
    await _bucket(db, site, AGORA - timedelta(days=2))

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)

    assert saida["disponivel"] is False
    assert "já passaram" in saida["motivo"], saida["motivo"]
    assert "Nenhuma previsão" not in saida["motivo"], saida["motivo"]


async def test_nunca_calculado_continua_com_o_texto_dele(db, site):
    """Tabela vazia nao pode herdar o texto do caso novo."""
    saida = await forecast_service.serie_por_janela(db, "hora", site.id)

    assert saida["disponivel"] is False
    assert "Nenhuma previsão" in saida["motivo"], saida["motivo"]
    assert "já passaram" not in saida["motivo"], saida["motivo"]


async def test_o_motivo_de_tudo_passado_cita_o_ultimo_bucket(db, site):
    """Sem a data, o operador nao sabe se o job atrasou uma hora ou um mes."""
    ultimo = await _bucket(db, site, AGORA - timedelta(days=5))

    saida = await forecast_service.serie_por_janela(db, "hora", site.id)

    assert ultimo.bucket_inicio.isoformat(timespec="minutes") in saida["motivo"], saida["motivo"]


async def test_o_filtro_vale_para_a_serie_da_REDE(db, site):
    """A linha da rede tem `site_id` NULL e passa pelo mesmo caminho.

    Foi na serie da REDE que o defeito apareceu em staging, entao o teste cobre os
    dois escopos - corrigir so' o da praca deixaria o caso observado de fora.
    """
    passado = SiteForecast(
        site_id=None,
        granularidade="hora",
        bucket_inicio=AGORA - timedelta(days=1),
        competencia=date(2026, 9, 24),
        gerado_em=AGORA,
        kwh_previsto=Decimal("500"),
        modelo_aplicavel=True,
        fonte="perfil_hora",
        modelo_versao="2.0.0",
    )
    db.add(passado)
    await db.flush()

    saida = await forecast_service.serie_por_janela(db, "hora", None)

    assert saida["escopo"] == "rede"
    assert saida["disponivel"] is False, saida
    assert "já passaram" in saida["motivo"]
