"""Copia para dentro de `apps/api` os documentos que o assistente consulta.

    python -m scripts.exportar_conhecimento

POR QUE UMA COPIA. A imagem Docker da API e' construida com contexto
`./apps/api` - a pasta `docs/` da raiz nao entra nela, e o README tambem nao. Sem
a copia, `buscar_documentacao` funcionaria no checkout e devolveria nada em
producao, que e' o pior jeito de falhar: sem erro, com o modelo voltando a
responder especificacao do carregador de memoria.

Uma copia envelhece, e por isso ela e' GERADA, nunca editada: este script e' a
unica forma de produzi-la, e `test_conhecimento.py` compara o que esta' em
`app/services/assistant/conhecimento/` com o que este script geraria agora. Mudou
o manual ou o README e esqueceu de rodar isto? O teste quebra - o mesmo arranjo
do `openapi.json`.

Do README entram so' as secoes de PRODUTO (regras de negocio, quem ve o que). As
de desenvolvimento - como rodar, CI, estrutura do repositorio - nao respondem
pergunta de operador e so' disputariam a busca com o que responde.
"""

from __future__ import annotations

import re
from pathlib import Path

API = Path(__file__).resolve().parents[1]
RAIZ = API.parents[1]
DESTINO = API / "app" / "services" / "assistant" / "conhecimento"

# nome da copia, fonte relativa a raiz, titulo que o assistente cita
DOCUMENTOS = [
    (
        "goodwe-hca-g2-datasheet.md",
        "docs/references/goodwe/hca-g2-datasheet-pt-br.md",
        "Datasheet GoodWe HCA G2",
    ),
    (
        "goodwe-hca-g2-manual.md",
        "docs/references/goodwe/hca-g2-user-manual-pt-br.md",
        "Manual do usuário GoodWe HCA G2",
    ),
    (
        "goodwe-hca-g2-modbus.md",
        "docs/references/goodwe/hca-g2-modbus-map.md",
        "Mapa Modbus do GoodWe HCA G2",
    ),
    (
        "desafio-mentoria-goodwe.md",
        "docs/challenge/mentoring-01.md",
        "Mentoria GoodWe do EV Challenge (13/05/2026)",
    ),
    ("desafio-escopo.md", "docs/challenge/brief.md", "Escopo do desafio ChargeGrid"),
]

# Secoes do README que viram documento, pelo titulo exato.
SECOES_DO_README = (
    "O que cada lado faz",
    "Retenção: quem paga o quê",
    "Previsão de demanda, e por que ela mora fora",
    "Assistente do operador",
    "Medição do site",
    "Quem vê o quê no painel",
)
README = ("plataforma-regras-de-negocio.md", "README.md", "Regras de negócio do ChargeGrid")

# Imagem embutida em base64 (a mentoria tem varias): pesa na copia e nao tem
# nada que uma busca por texto consiga usar.
_IMAGEM_EMBUTIDA = re.compile(r"^\[image\d+\]: <data:image/[^>]*>\s*$", re.MULTILINE)


def _cabecalho(titulo: str, fonte: str) -> str:
    return (
        f"<!-- GERADO por scripts/exportar_conhecimento.py a partir de {fonte}. "
        "Nao edite: rode o script. -->\n"
        f"<!-- titulo: {titulo} -->\n\n"
    )


def _secoes_do_readme(texto: str) -> str:
    """Recorta as secoes pedidas, cada uma ate o proximo titulo do mesmo nivel ou acima."""
    linhas = texto.splitlines()
    saida: list[str] = []
    dentro_nivel: int | None = None
    for linha in linhas:
        titulo = re.match(r"^(#{2,3}) (.+)$", linha)
        if titulo:
            nivel = len(titulo.group(1))
            if dentro_nivel is not None and nivel <= dentro_nivel:
                dentro_nivel = None
            if titulo.group(2).strip() in SECOES_DO_README:
                dentro_nivel = nivel
        if dentro_nivel is not None:
            saida.append(linha)
    return "\n".join(saida).strip() + "\n"


def gerar() -> dict[str, str]:
    """Nome da copia -> conteudo, exatamente o que deve estar em DESTINO."""
    arquivos: dict[str, str] = {}
    for nome, fonte, titulo in DOCUMENTOS:
        texto = (RAIZ / fonte).read_text(encoding="utf-8").replace("\r\n", "\n")
        texto = _IMAGEM_EMBUTIDA.sub("", texto).rstrip() + "\n"
        arquivos[nome] = _cabecalho(titulo, fonte) + texto
    nome, fonte, titulo = README
    arquivos[nome] = _cabecalho(titulo, fonte) + _secoes_do_readme(
        (RAIZ / fonte).read_text(encoding="utf-8").replace("\r\n", "\n")
    )
    return arquivos


def fontes_disponiveis() -> bool:
    """Fora do checkout (na imagem Docker) as fontes nao existem - e nem precisam."""
    return all((RAIZ / fonte).exists() for _, fonte, _ in [*DOCUMENTOS, README])


def main() -> int:
    DESTINO.mkdir(parents=True, exist_ok=True)
    esperados = gerar()
    for antigo in DESTINO.glob("*.md"):
        if antigo.name not in esperados:
            antigo.unlink()
    for nome, conteudo in esperados.items():
        # write_bytes, e nao write_text: no Windows o write_text troca \n por
        # \r\n, e o teste de sincronia acusaria diferenca no arquivo inteiro.
        (DESTINO / nome).write_bytes(conteudo.encode("utf-8"))
    print(f"{len(esperados)} documentos em {DESTINO.relative_to(API)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
