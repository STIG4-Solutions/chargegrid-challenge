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

from app.main import app

DESTINO = Path(__file__).resolve().parents[1] / "openapi.json"


def como_texto() -> str:
    """O conteudo canonico do contrato, pronto para gravar ou comparar."""
    return json.dumps(app.openapi(), indent=2, ensure_ascii=False) + "\n"


def main() -> int:
    antes = DESTINO.read_text(encoding="utf-8") if DESTINO.exists() else None
    depois = como_texto()
    DESTINO.write_text(depois, encoding="utf-8")

    if antes == depois:
        print(f"{DESTINO.name} ja' estava em dia.")
    else:
        print(f"{DESTINO.name} atualizado. Rode `npm run gen:types` para o SDK acompanhar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
