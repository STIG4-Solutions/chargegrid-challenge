"""O portao: quem e' a melhor regua, e o modelo a supera?

POR QUE ESTA REGRA GANHOU UMA CASA. Ela vivia dentro de `main()` do `exportar.py`, e
o resumo do job de previsao a reescrevia em YAML - comparando so' com a media movel:

    modelo, regua = m.get("wape_mensal"), m.get("wape_mensal_baseline_m28")
    venceu = modelo is not None and regua is not None and modelo < regua

As duas versoes concordavam quando havia uma regua so'. Desde que a de ano-a-ano
entrou, elas DIVERGEM - e o resumo mente para quem abre a execucao:

    caso                          modelo    m28   melhor   resumo   portao
    a corrida de 25/09             12,25  15,72    14,41   venceu   venceu
    modelo entre as duas reguas    15,00  15,72    14,41   venceu   PERDEU
    ano-a-ano muito melhor         13,00  15,72    11,00   venceu   PERDEU

Em dois de tres casos plausiveis o resumo anuncia promocao que nao houve. Uma regra
de decisao escrita em dois lugares sai de sincronia no primeiro dia em que muda; esta
mudou, e foi o que aconteceu.
"""

from __future__ import annotations

# As reguas que competem pela janela MENSAL, e a chave da metrica de cada uma. A
# ordem nao importa para o `min`, mas importa para o texto: e' a ordem em que elas
# entraram no projeto.
REGUAS_MENSAIS = {
    "media_movel": "wape_mensal_baseline_m28",
    "ano_a_ano": "wape_mensal_baseline_ano",
}

# Quando NENHUMA regua tem metrica no artefato. Nao e' um valor de erro - e' o nome
# que a `fonte` recebe, e a media movel e' a escolha conservadora: um artefato sem
# backtest nao provou nada, e o numero gravado vira a conta mais simples que existe.
REGUA_PADRAO = "media_movel"


def reguas_medidas(metricas: dict) -> dict[str, float]:
    """As reguas que o artefato realmente mediu.

    `None` fica FORA: artefato antigo nao tem a metrica de ano-a-ano, e um `None`
    dentro de um `min` seria um erro de tipo ou - pior, em outra linguagem - o menor
    de todos os valores.
    """
    medidas = {}
    for nome, chave in REGUAS_MENSAIS.items():
        valor = metricas.get(chave)
        if valor is not None:
            medidas[nome] = float(valor)
    return medidas


def melhor_regua(metricas: dict) -> tuple[str, float | None]:
    """O nome e o erro da melhor regua medida.

    Sem nenhuma medida, devolve `(REGUA_PADRAO, None)` - o nome existe porque a
    `fonte` da linha gravada precisa de um, e o erro e' `None` porque nao ha' com que
    comparar.
    """
    medidas = reguas_medidas(metricas)
    if not medidas:
        return REGUA_PADRAO, None
    nome = min(medidas, key=medidas.__getitem__)
    return nome, medidas[nome]


def modelo_vence(metricas: dict) -> bool:
    """O modelo e' usado so' quando MEDE melhor que a MELHOR regua.

    Empate NAO promove: com o mesmo erro, a regua e' preferivel por ser explicavel em
    tres linhas. E sem metrica de um dos lados o modelo tambem nao entra - e' o valor
    conservador, porque um artefato sem backtest nao provou nada.

    Nem promover nem desistir e' decisao de quem escreve codigo: o backtest inverte
    isto sozinho quando o numero mudar de lado.
    """
    modelo = metricas.get("wape_mensal")
    _, regua = melhor_regua(metricas)
    return modelo is not None and regua is not None and float(modelo) < regua
