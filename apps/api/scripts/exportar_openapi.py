"""Escreve `openapi.json` a partir do proprio app.

    python -m scripts.exportar_openapi

ESTE ARQUIVO FALTAVA, e a falta tem consequencia visivel. A cadeia era
`openapi.json` -> `gen:types` -> `schema.ts` -> SDK, com o primeiro elo mantido
A MAO: quem acrescentava uma rota editava o JSON manualmente. Funciona enquanto
alguem lembra, e o resultado de nao lembrar foi 30 rotas divergindo do que a API
realmente responde - sem que nada acusasse, porque tambem nao havia teste.

O formato e' o mesmo que o arquivo ja' tinha: indentacao de 2, UTF-8 com acento
literal (`ensure_ascii=False`), quebra de linha no fim, sem BOM. Nao e' capricho
- e' o que faz o diff de um retreino mostrar so' o que mudou de verdade, em vez
de reescrever o arquivo inteiro.

A ORDEM vem do app, e nao do arquivo anterior. Ordenar por outro criterio - ou
preservar a ordem antiga - faria a saida depender do que ja' estava la', e dois
clones do repositorio produziriam arquivos diferentes a partir do mesmo codigo.
"""

from __future__ import annotations

import json
from pathlib import Path

import fastapi
import pydantic

from app.main import app

DESTINO = Path(__file__).resolve().parents[1] / "openapi.json"
REGISTRO = DESTINO.with_name("openapi.gerado-com.json")


def versoes_daqui() -> dict[str, str]:
    """Quem manda no formato da saida.

    Nao e' metadado decorativo. O formato do contrato depende da versao do
    FastAPI e do Pydantic - `additionalProperties` em retorno `dict`, `int`
    ou `float` nos limites numericos, `ctx` no `ValidationError`, `pattern`
    nos decimais. Gerar com versao diferente da que produziu o arquivo
    reescreve trinta rotas sem que nenhuma rota tenha mudado.

    E o estrago e' silencioso: o arquivo reescrito e' JSON valido, passa no
    teste do contrato (ele compara com o app da MESMA maquina) e so' aparece
    depois, nos tipos do SDK, no cliente. Guardar as versoes e' o que permite
    ao teste dizer "seu ambiente difere" em vez de "o contrato derivou".
    """
    return {"fastapi": fastapi.__version__, "pydantic": pydantic.VERSION}


def como_texto() -> str:
    """O conteudo canonico do contrato, pronto para gravar ou comparar."""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def registro_como_texto() -> str:
    return json.dumps(versoes_daqui(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    antes = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else None
    depois = como_texto()
    DESTINO.write_text(depois, encoding="utf-8")
    REGISTRO.write_text(registro_como_texto(), encoding="utf-8")

    if antes == depois:
        print(f"{DESTINO.name} ja' estava em dia.")
    else:
        print(f"{DESTINO.name} atualizado. Rode `npm run gen:types` para o SDK acompanhar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
