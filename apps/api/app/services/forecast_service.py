"""Leitura da previsao de demanda. A API nunca a calcula.

Quem calcula e' `apps/forecast`, um job que roda fora deste processo. Aqui so' se
le a linha mais recente e se traduz para a tela - incluindo as guardas de
honestidade, que sao a parte que nao pode ser esquecida.

DE ONDE VEIO O NUMERO. `kwh_previsto` tem duas origens possiveis, e `fonte` diz
qual. O job so' usa o modelo quando ele MEDE melhor que a media movel de 28 dias
no backtest; caso contrario grava a propria media movel. Nao e' desistir do
modelo - quando ele passar a ganhar, o backtest inverte a escolha sozinho.

Isso produz tres estados, e o aviso muda em cada um:

  aplicavel=False, fonte=media_movel  -> historico curto demais para o modelo
  aplicavel=True,  fonte=media_movel  -> o modelo conhece o local e perde da regua
  aplicavel=True,  fonte=modelo       -> previsao de verdade, com banda

Os dois primeiros entregam o MESMO numero por motivos diferentes, e juntar os
dois faria o operador achar que falta dado quando o que falta e' modelo melhor.

A faixa p10-p90 tem aviso proprio: ela cobre menos do que promete, e tratar os
extremos como piores casos e' otimismo.

Nada disso e' escondido. O projeto ja faz isso em `demand_service`
(`confiavel`) e em `maintenance_service` (`so_humano`), e pela mesma razao: um
numero sem a sua incerteza e' pior que numero nenhum, porque parece confiavel.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import Date, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.forecast import SiteForecast
from app.models.site import Site

# Quanto a faixa p10-p90 promete conter. E' a definicao dos quantis, nao opiniao.
COBERTURA_ESPERADA = Decimal("80")

# Folga antes de acusar sub-calibracao. Backtest de tres meses tem ruido de
# amostragem; acusar por um ponto de diferenca so' geraria alarme.
# O que cada `fonte` E', em uma frase. Serve os dois ramos do aviso, e existe porque
# o texto estava SUPONDO a conta: o ramo de historico curto dizia "a media dos
# ultimos 28 dias" para qualquer linha, e a janela de ANO grava
# `modelo_aplicavel = False` com `fonte = 'tendencia'` - entao o aviso afirmava que
# uma extrapolacao de reta era uma media movel. O operador que le isso e ve um salto
# de 54% entre dois anos conclui que a media esta' subindo, nao que uma reta foi
# esticada a partir de duas observacoes.
O_QUE_E = {
    "media_movel": "a média dos últimos 28 dias",
    "ano_a_ano": ("a comparação com o mesmo mês do ano anterior, corrigida pelo crescimento"),
    "media_dow": "a média daquele dia da semana no histórico recente",
    "perfil_hora": "o perfil médio daquela hora e dia da semana",
    "tendencia": "uma reta esticada a partir do histórico anual",
}

# As reguas que podem servir a janela MENSAL. O numero gravado e' o mesmo tipo de
# coisa nas duas - um total de mes vindo de conta simples -, mas elas erram de
# formas muito diferentes: medido no banco local, a media movel erra 13,95% e a de
# ano-a-ano 8,67%. Chamar as duas pelo mesmo nome esconde 5,3 pontos.
REGUAS_MENSAIS = ("media_movel", "ano_a_ano")

# Fontes cujo numero vem de pouquissimas observacoes, e quantas. A janela de ano tem
# DUAS comparacoes ano-a-ano em quatro anos de historico: uma reta por dois pontos
# passa exata pelos dois e nao diz nada sobre o terceiro. Sem este aviso, o numero da
# tela tem a mesma cara de um que foi aferido.
POUCAS_OBSERVACOES = {
    "tendencia": (
        "São duas observações anuais completas no histórico: a reta passa exata por "
        "elas e não há terceira para conferir. Use a ordem de grandeza, não o número."
    ),
}

TOLERANCIA_DE_COBERTURA = Decimal("5")

# As janelas que o job grava. A ordem e' do mais fino para o mais grosso.
JANELAS = ("hora", "dia", "semana", "mes", "ano")

# Quantos buckets devolver por janela, quando ninguem pede outro numero.
#
# Nao e' o mesmo para todas: 48 horas sao dois dias de curva, que e' o que serve
# para decidir rebalanceamento; 12 meses sao um ano de planejamento. Devolver 48
# anos nao faria sentido, e devolver 12 horas cortaria a curva do dia no meio.
BUCKETS_PADRAO = {"hora": 48, "dia": 30, "semana": 12, "mes": 12, "ano": 3}
BUCKETS_MAXIMO = {"hora": 24 * 14, "dia": 365, "semana": 104, "mes": 36, "ano": 10}


def _bucket(linha: SiteForecast) -> dict:
    """Uma linha da serie. Mesmos nomes de campo da resposta mensal.

    A banda vem nula quando a fonte nao declara quantil, e o CHECK
    `banda_com_quantil` no banco garante que isso e' consistente - a tela nao
    precisa decidir sozinha se desenha incerteza.
    """
    return {
        "bucket_inicio": linha.bucket_inicio.isoformat(),
        "kwh_previsto": _float(linha.kwh_previsto),
        "kwh_p10": _float(linha.kwh_p10),
        "kwh_p90": _float(linha.kwh_p90),
        "faturamento_previsto_brl": _float(linha.faturamento_previsto_brl),
        "fat_p10_brl": _float(linha.fat_p10_brl),
        "fat_p90_brl": _float(linha.fat_p90_brl),
        "fonte": linha.fonte,
    }


def _float(valor) -> float | None:
    return None if valor is None else float(valor)


async def _fuso_dos_buckets(db: AsyncSession, site_id: uuid.UUID | None) -> str:
    """Em que fuso os buckets foram CONTADOS.

    Sem isto a tela nao tem como rotular a janela de hora. A resposta carrega o
    instante em UTC, e o navegador o converte para o fuso de QUEM OLHA - o que
    desloca a curva do dia para qualquer pessoa fora do fuso da praca. O CI pegou
    isso: o runner roda em UTC e viu o pico das 17h como 20h.

    E' a curva do dia que da' sentido a janela horaria, entao o deslocamento nao e'
    cosmetico: e' a feature errada.

    Para a REDE nao existe uma praca, e o fuso vem do conjunto. O job que escreve
    (`exportar_janelas.py`) RECUSA gravar quando as pracas estao em fusos
    diferentes, entao aqui ha no maximo um - e o `min` e' so' determinismo.
    """
    if site_id is not None:
        fuso = (
            await db.execute(select(Site.timezone).where(Site.id == site_id))
        ).scalar_one_or_none()
        return fuso or "UTC"
    fuso = (await db.execute(select(func.min(Site.timezone)))).scalar_one_or_none()
    return fuso or "UTC"


def _mes_corrente():
    """O primeiro dia do mes de HOJE, calculado no banco.

    No banco e nao em Python de proposito: o `CURRENT_DATE` do Postgres e' o mesmo
    relogio que carimba as linhas, e uma comparacao entre datas de relogios
    diferentes erra no virar do mes em fuso diferente.
    """
    return cast(func.date_trunc("month", func.current_date()), Date)


def _avisos(linha: SiteForecast) -> list[dict]:
    """O que o operador precisa saber antes de usar este numero."""
    avisos: list[dict] = []

    # A conta que produziu o numero, DITA e nao suposta. `fonte` desconhecida cai
    # numa frase generica em vez de ser chamada de media movel: um valor novo no
    # banco tem de aparecer vago na tela, nao ganhar a descricao de outra conta.
    o_que_e = O_QUE_E.get(linha.fonte, "uma conta simples sobre o histórico")

    # Dois casos, dois textos. O numero pode nao vir do modelo por dois motivos
    # completamente diferentes, e juntar os dois faria o operador achar que falta
    # dado quando na verdade o modelo e' que nao entrega - ou o contrario, que e'
    # pior: esperar o modelo melhorar numa praca que so' precisa de tempo.
    if not linha.modelo_aplicavel:
        avisos.append(
            {
                "nivel": "alto",
                "texto": (
                    f"Sem histórico suficiente para o modelo neste ponto. O valor "
                    f"abaixo é {o_que_e}, não uma previsão."
                ),
            }
        )
    elif linha.fonte in REGUAS_MENSAIS:
        # As DUAS reguas mensais entram aqui. Antes so' `media_movel` casava, e uma
        # linha servida pela regua de ano-a-ano saia SEM aviso nenhum - a tela
        # deixava de dizer que o numero nao veio do modelo, e silencio parece
        # confirmacao.
        modelo, regua = linha.wape_modelo_pct, linha.wape_baseline_pct
        detalhe = ""
        if modelo is not None and regua is not None:
            detalhe = f" — ele erra {float(modelo):.1f}% contra {float(regua):.1f}% dela"
        avisos.append(
            {
                "nivel": "medio",
                "texto": (
                    f"Este número é {o_que_e}. O modelo existe e conhece este ponto, "
                    f"mas não supera essa régua no teste{detalhe}. Ele volta sozinho "
                    f"quando passar a acertar mais."
                ),
            }
        )

    # Quantas observacoes sustentam o numero, quando sao poucas. Vem DEPOIS do aviso
    # da conta, porque a ordem importa: primeiro o que o numero e', depois quanta
    # evidencia ele tem.
    if linha.fonte in POUCAS_OBSERVACOES:
        avisos.append({"nivel": "alto", "texto": POUCAS_OBSERVACOES[linha.fonte]})

    # So' quando ha faixa NA TELA. Com `fonte = media_movel` nao se desenha
    # banda nenhuma, e avisar sobre a calibracao de algo que o operador nao esta
    # vendo e' ruido - e ruido faz o aviso seguinte, que importa, ser ignorado.
    medida, declarada = linha.cobertura_medida_pct, linha.cobertura_declarada_pct

    # Faixa DESENHADA cuja cobertura nao foi medida. Acontece quando os fatores da
    # calibracao existem mas a verificacao fora da amostra nao teve observacoes
    # suficientes - em staging, 3 pracas dao 18 residuos mensais contra o minimo de
    # 30. A faixa e' legitima; o que falta e' a afericao dela, e isso tem de ser dito.
    # Sem este aviso o operador ve' uma faixa sem nada distinguindo-a de uma aferida.
    if linha.fonte == "modelo" and linha.kwh_p10 is not None and medida is None:
        avisos.append(
            {
                "nivel": "medio",
                "texto": (
                    "A faixa foi calibrada, mas a cobertura dela não foi medida neste "
                    "teste — faltaram observações fora da amostra. Ela continua sendo a "
                    "melhor estimativa de incerteza disponível; só não há número "
                    "confirmando que contém o valor real na frequência que promete."
                ),
            }
        )

    if linha.fonte == "modelo" and medida is not None and declarada is not None:
        if Decimal(str(medida)) < Decimal(str(declarada)) - TOLERANCIA_DE_COBERTURA:
            avisos.append(
                {
                    "nivel": "medio",
                    "texto": (
                        f"A faixa é mais estreita do que deveria: no teste ela conteve "
                        f"o valor real em {float(medida):.0f}% dos casos, e não nos "
                        f"{float(declarada):.0f}% que promete. Trate os extremos como otimistas."
                    ),
                }
            )

    return avisos


async def previsao_do_site(db: AsyncSession, site_id: uuid.UUID) -> dict:
    """A previsao mais recente deste site, ou a declaracao de que nao ha.

    `disponivel: false` nao e' erro. A tabela vazia e' o estado normal de quem
    nunca rodou o job, e a tela precisa saber a diferenca entre "ainda nao
    calculamos" e "calculamos e deu zero".
    """
    linha = (
        await db.execute(
            select(SiteForecast)
            .where(SiteForecast.site_id == site_id)
            # `granularidade` EXPLICITA. Esta rota sempre falou do total do mes, e
            # ate' existir uma segunda janela o filtro era desnecessario. Agora
            # existem cinco: sem ele, `order_by ... limit 1` devolveria a linha
            # mais recente de QUALQUER janela - uma hora, provavelmente - e a tela
            # de demanda contratada mostraria o consumo de uma hora como se fosse
            # o do mes. Nao daria erro em lugar nenhum.
            .where(SiteForecast.granularidade == "mes")
            # O PROXIMO mes, e nao o mais distante.
            #
            # Era `competencia DESC`, que significava "a previsao mais recente"
            # enquanto havia UMA linha mensal por praca. O job de janelas passou a
            # gravar doze, e `DESC` comecou a devolver agosto do ano seguinte -
            # que vem de regua - no lugar do mes que vem, que vem do modelo. A
            # tela de demanda contratada mostrava o numero errado, sem erro
            # nenhum. Encontrado conferindo o banco depois da primeira execucao.
            #
            # Prefere bucket futuro; entre futuros, o mais proximo. Se TODOS
            # estiverem no passado - job parado ha meses - devolve o menos velho
            # em vez de dizer que nao ha previsao: a competencia vai na resposta e
            # a tela mostra de quando e'.
            .order_by(
                (SiteForecast.competencia >= _mes_corrente()).desc(),
                func.abs(SiteForecast.competencia - _mes_corrente()).asc(),
                SiteForecast.gerado_em.desc(),
            )
            .limit(1)
        )
    ).scalar_one_or_none()

    if linha is None:
        return {
            "disponivel": False,
            "motivo": (
                "Nenhuma previsão calculada para este ponto ainda. "
                "O cálculo roda fora da API, uma vez por mês."
            ),
        }

    return {
        "disponivel": True,
        "competencia": linha.competencia.isoformat(),
        "gerado_em": linha.gerado_em.isoformat(),
        "kwh_previsto": _float(linha.kwh_previsto),
        # Sem banda quando o modelo nao se aplica. O `None` aqui e' o que faz a
        # tela nao desenhar incerteza em volta de uma media movel.
        "kwh_p10": _float(linha.kwh_p10),
        "kwh_p90": _float(linha.kwh_p90),
        "faturamento_previsto_brl": _float(linha.faturamento_previsto_brl),
        "fat_p10_brl": _float(linha.fat_p10_brl),
        "fat_p90_brl": _float(linha.fat_p90_brl),
        "media_diaria_28d": _float(linha.media_diaria_28d),
        "modelo_aplicavel": linha.modelo_aplicavel,
        # De onde veio o numero que esta em `kwh_previsto`. A tela desenha a
        # banda so' quando e' "modelo".
        "fonte": linha.fonte,
        "modelo_versao": linha.modelo_versao,
        "dias_de_historico": linha.dias_de_historico,
        "cobertura_declarada_pct": _float(linha.cobertura_declarada_pct),
        "cobertura_medida_pct": _float(linha.cobertura_medida_pct),
        "wape_modelo_pct": _float(linha.wape_modelo_pct),
        "wape_baseline_pct": _float(linha.wape_baseline_pct),
        "avisos": _avisos(linha),
    }


async def serie_por_janela(
    db: AsyncSession,
    janela: str,
    site_id: uuid.UUID | None,
    quantos: int | None = None,
) -> dict:
    """Os proximos buckets desta janela, para uma praca ou para a REDE.

    `site_id = None` pede a linha da rede, onde a coluna e' NULL. Usa-se
    `is_(None)` por clareza e pelo linter; o SQLAlchemy traduz `== None` para
    `IS NULL` sozinho, entao as duas formas funcionam - uma versao anterior deste
    comentario afirmava o contrario, e uma mutacao provou que nao.

    A ordem e' CRESCENTE no tempo, ao contrario da rota mensal, que quer so' a
    linha mais recente. Uma serie desenhada de tras para frente nao e' grafico.
    """
    if janela not in JANELAS:
        raise ValueError(f"janela desconhecida: {janela}")

    limite = quantos or BUCKETS_PADRAO[janela]
    limite = max(1, min(int(limite), BUCKETS_MAXIMO[janela]))

    escopo = SiteForecast.site_id.is_(None) if site_id is None else SiteForecast.site_id == site_id
    linhas = (
        (
            await db.execute(
                select(SiteForecast)
                .where(escopo)
                .where(SiteForecast.granularidade == janela)
                .order_by(SiteForecast.bucket_inicio.asc())
                .limit(limite)
            )
        )
        .scalars()
        .all()
    )

    fuso = await _fuso_dos_buckets(db, site_id)

    if not linhas:
        return {
            "disponivel": False,
            "janela": janela,
            "escopo": "rede" if site_id is None else "praca",
            "timezone": fuso,
            "motivo": (
                f"Nenhuma previsão de janela '{janela}' calculada ainda. "
                "O cálculo roda fora da API."
            ),
        }

    # `gerado_em`, `modelo_versao` e as metricas sao da EXECUCAO, nao do bucket:
    # todos os buckets de uma serie vem da mesma rodada do job. Repeti-los em cada
    # item inflaria a resposta e sugeriria que podem divergir.
    ultima = max(linhas, key=lambda linha: linha.gerado_em)
    return {
        "disponivel": True,
        "janela": janela,
        "escopo": "rede" if site_id is None else "praca",
        # O fuso em que os buckets foram contados. A tela rotula o eixo com ele, e
        # nao com o do navegador - ver `_fuso_dos_buckets`.
        "timezone": fuso,
        "gerado_em": ultima.gerado_em.isoformat(),
        "modelo_versao": ultima.modelo_versao,
        "wape_modelo_pct": _float(ultima.wape_modelo_pct),
        "wape_baseline_pct": _float(ultima.wape_baseline_pct),
        "cobertura_declarada_pct": _float(ultima.cobertura_declarada_pct),
        "cobertura_medida_pct": _float(ultima.cobertura_medida_pct),
        "buckets": [_bucket(linha) for linha in linhas],
        "avisos": _avisos(ultima),
    }
