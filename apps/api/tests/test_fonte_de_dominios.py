"""A fonte unica de enderecos, e quem a consome.

config/domains.json alimenta API, dashboard e app. O valor so vale se os tres
lerem o mesmo arquivo - e o jeito de isso se perder e' alguem escrever um
endereco fixo de novo em algum canto.
"""

import json
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[3]
ARQUIVO = RAIZ / "config" / "domains.json"


def test_o_arquivo_existe_e_tem_o_essencial():
    d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    assert d["protocolo"] in {"http", "https"}
    assert d["api"] and d["dashboard"] and d["site"]


def test_cors_deriva_do_arquivo():
    from app.core.config import _origens_padrao

    d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    assert f"{d['protocolo']}://{d['dashboard']}" in _origens_padrao()


def test_o_dashboard_de_desenvolvimento_continua_liberado():
    """Sem isso, trabalhar localmente exigiria editar o .env a cada clone."""
    from app.core.config import _origens_padrao

    origens = _origens_padrao()
    assert any("localhost:5173" in o for o in origens)


def test_sem_o_arquivo_o_backend_ainda_sobe(monkeypatch, tmp_path):
    """A imagem Docker copia so o backend: o arquivo pode nao estar la."""
    from app.core import config

    monkeypatch.setattr(config, "_RAIZ", tmp_path)
    assert config._dominios() == {}
    assert config._origens_padrao(), "sem o arquivo, ainda precisa liberar o dev"


def test_nenhum_endereco_de_producao_fixo_no_codigo():
    """O endereco tem de vir do arquivo, nunca escrito direto na fonte."""
    import re

    d = json.loads(ARQUIVO.read_text(encoding="utf-8"))
    dominios = [re.escape(d[chave]) for chave in ("api", "dashboard", "site")]
    alvos = [
        RAIZ / "apps" / "api" / "app",
        RAIZ / "packages" / "sdk" / "src",
        RAIZ / "apps" / "dashboard" / "src",
        RAIZ / "apps" / "mobile" / "src",
    ]
    achados = []
    for raiz in alvos:
        for f in raiz.rglob("*"):
            if f.suffix not in {".py", ".ts", ".tsx", ".js", ".jsx"} or "schema.ts" in f.name:
                continue
            for n, linha in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                tem_dominio = any(re.search(dominio, linha) for dominio in dominios)
                if tem_dominio and not linha.lstrip().startswith(("#", "*", "//")):
                    achados.append(f"{f.relative_to(RAIZ)}:{n}")
    assert not achados, f"endereço fixo fora de config/domains.json: {achados}"
