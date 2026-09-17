"""O contrato publicado tem de ser o contrato que a API responde.

`openapi.json` nao e' documentacao: e' a fonte de `packages/sdk/src/schema.ts`,
e portanto dos tipos com que o painel e o app foram escritos. Um arquivo velho
nao produz erro em lugar nenhum - produz um SDK que descreve uma API que nao
existe mais, e o desencontro so' aparece em runtime, no cliente.

E foi o que aconteceu. O arquivo era mantido A MAO - havia `gen:types` para ir
do JSON aos tipos, e nada para ir do app ao JSON - e chegou a divergir em 30
rotas: 29 sem `additionalProperties` (o FastAPI passou a emiti-lo para retorno
`dict`) e uma com a descricao congelada numa versao anterior da docstring.
Nenhum teste olhava, que e' por que apodreceu em silencio.

Este e' o teste que faltava.
"""

from __future__ import annotations

import json

from scripts.exportar_openapi import DESTINO, REGISTRO, como_texto, versoes_daqui

COMANDO = "npm run gen:contrato"


def test_o_arquivo_e_exatamente_o_que_o_app_gera():
    """Compara o TEXTO, e nao o objeto.

    Comparar `json.loads` dos dois passaria com o arquivo reindentado, reordenado
    ou salvo com BOM - e qualquer um dos tres estraga o diff do proximo, que e'
    metade do motivo de versionar o contrato. O byte importa aqui.
    """
    assert DESTINO.exists(), "o contrato sumiu do repositorio"

    if DESTINO.read_text(encoding="utf-8") == como_texto():
        return

    # Antes de acusar deriva, confere de quem e' a culpa. O formato da saida
    # depende do FastAPI e do Pydantic, entao ambiente diferente do que gerou
    # o arquivo produz diferenca em trinta rotas sem nenhuma rota ter mudado -
    # e obedecer a mensagem de regerar, ali, CORROMPE o contrato.
    gerado_com = json.loads(REGISTRO.read_text(encoding="utf-8"))
    aqui = versoes_daqui()
    if aqui != gerado_com:
        divergentes = ", ".join(
            f"{nome} {aqui[nome]} (contrato: {gerado_com[nome]})"
            for nome in sorted(gerado_com)
            if aqui[nome] != gerado_com[nome]
        )
        raise AssertionError(
            "Isto NAO e' deriva do contrato - e' este ambiente.\n\n"
            f"Difere do que gerou o arquivo: {divergentes}.\n"
            "O formato do OpenAPI muda com essas versoes, entao o diff aparece "
            "sem nenhuma rota ter mudado. O arquivo commitado esta' CORRETO.\n\n"
            f"NAO regere aqui - use {COMANDO}, que gera dentro do contêiner."
        )

    raise AssertionError(
        "openapi.json esta' fora de sincronia com a API.\n\n"
        "Nao edite o arquivo a mao - foi assim que ele divergiu em 30 rotas.\n"
        f"Regere com:\n  {COMANDO}\n"
        "e depois `npm run gen:types` para o SDK acompanhar."
    )


def test_o_contrato_e_json_valido_sem_bom():
    """BOM ja' entrou aqui uma vez, por redirecionamento de shell no Windows.

    Um BOM nao quebra o `json.load` do Python, mas quebra parsers mais estritos -
    e o `openapi-typescript` le este arquivo.
    """
    cru = DESTINO.read_bytes()
    assert not cru.startswith(b"\xef\xbb\xbf"), "o arquivo comecou com BOM"
    assert cru.endswith(b"\n"), (
        "sem quebra de linha final, o diff da proxima vez marca a ultima linha"
    )
    assert b"\r\n" not in cru, "CRLF no contrato faz o diff inteiro parecer alterado"
    json.loads(cru.decode("utf-8"))


# NAO acrescente aqui um teste que percorre `app.routes` para conferir se toda
# rota chegou ao contrato. Ja' foi tentado, e duas vezes:
#
#   - a primeira versao passava sempre. Nesta versao do FastAPI (0.141) cada
#     `include_router` vira UMA entrada `_IncludedRouter`, entao o primeiro nivel
#     tem seis itens - quatro da documentacao, `/health` e a v1 inteira colapsada.
#     Comparar isso com as 82 publicadas nunca acusa nada. So' a mutacao mostrou:
#     acrescentar rota a' API nao fazia o teste falhar;
#   - descer de verdade exige `_IncludedRouter.original_router`, que e' privado e
#     muda entre versoes. Um guardiao construido sobre atributo interno e' passivo,
#     nao protecao.
#
# E e' desnecessario: `test_o_arquivo_e_exatamente_o_que_o_app_gera` compara com
# `app.openapi()`, que e' a API PUBLICA e ja' cobre rota nova - conferido por
# mutacao. Um segundo teste sobre a mesma propriedade so' custaria manutencao.
