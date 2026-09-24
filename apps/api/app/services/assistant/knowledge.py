"""Busca textual (BM25) na documentacao que o assistente consulta.

POR QUE BM25, E NAO EMBEDDINGS. O corpus e' pequeno (seis documentos, ~130 KB) e
cheio de termo exato: numero de registrador ("10029"), sigla ("RFID", "RS485"),
nome de estado do LED. Busca lexical acerta isso melhor que busca semantica, nao
precisa de deployment de embeddings nem de pgvector, e e' deterministica - o
teste roda no CI sem Azure. Se um dia a pergunta tipica for parafrase ("o
carregador para sozinho quando o predio puxa muito"), soma-se embeddings por
cima; nao e' preciso trocar.

OS DOCUMENTOS SAO PDFs CONVERTIDOS. Nao ha titulo Markdown no manual da GoodWe: a
secao aparece como uma linha em negrito ("**4.2 Entregas**"). Sobram tambem
imagens sem texto, tabelas vazias e o sumario, que cita toda secao e por isso
casaria com qualquer pergunta. A limpeza abaixo existe por causa disso, e o que
ela descarta nao tem texto que uma busca conseguisse usar.

O indice e' montado na primeira busca e fica em memoria: sao algumas centenas de
trechos, e reconstruir a cada pergunta custaria mais que a pergunta.
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

PASTA = Path(__file__).resolve().parent / "conhecimento"

# Tamanho-alvo de um trecho. Grande o bastante para uma tabela de registradores
# ou um procedimento inteiro caber; pequeno o bastante para tres trechos custarem
# pouco no contexto (~1 mil tokens).
TAMANHO_DO_TRECHO = 1200

# BM25 classico. Nada aqui foi ajustado por experimento - sao os valores de
# referencia, e mudar exigiria uma bateria de perguntas-ouro para justificar.
K1 = 1.5
B = 0.75

# Peso extra de um IDENTIFICADOR na consulta: numero de 4+ digitos (registrador,
# codigo de falha). Medido com a consulta que o modelo real mandou - "10029 faixa
# de potência registrador GoodWe HCA G2": sem o peso, "potência" e "registrador",
# que aparecem em dezenas de trechos do manual, somavam mais que "10029", que so'
# existe no mapa Modbus, e o assistente respondeu que a documentacao nao cobria.
PESO_DE_IDENTIFICADOR = 3.0

_PARADAS = set(
    "a o e de da do das dos em no na nos nas um uma uns umas para por com sem que "
    "se ao aos as os ou mais menos como qual quais quando onde porque pelo pela "
    "pelos pelas ser sao esta este esse essa isso isto ele ela eles elas tem ter "
    "foi ha nao sim ja ate sobre entre muito pode deve the of and to in is for".split()
)
_SECAO_EM_NEGRITO = re.compile(r"^\*\*(\d+(?:\.\d+)*\.?\s+[^*]{2,100})\*\*\s*$")
_TITULO_MD = re.compile(r"^#{1,4}\s+(.+)$")
_TITULO_DO_DOC = re.compile(r"<!-- titulo: (.+?) -->")
_SUMARIO = re.compile(r"\b\d+\.\d+(?:\.\d+)? [A-ZÁÉÍÓÚÂÊÔÃÕÇ]")
# Entrada de capitulo do sumario: negrito terminado no NUMERO DA PAGINA
# ("**9 Manutenção 54**"). No corpo o titulo nao tem pagina ("**4.2 Entregas**").
# Contar entradas por bloco nao bastava: o sumario vem partido em blocos de tres a
# cinco, todos abaixo do limite, que somados davam o sumario inteiro num trecho.
_CAPITULO_DO_SUMARIO = re.compile(r"^\*\*\d+ [^*]+ \d+\*\*")


@dataclass(frozen=True, slots=True)
class Trecho:
    documento: str
    secao: str | None
    texto: str


def _sem_acento(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c))


def termos(texto: str) -> list[str]:
    """Texto -> termos indexaveis: sem acento, minusculo, sem palavra vazia.

    O plural perde o 's' final ("correntes" casa com "corrente"). E' o minimo de
    radicalizacao que ajuda sem estragar sigla nem numero de registrador.
    """
    saida = []
    for termo in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", _sem_acento(texto).lower()):
        if termo in _PARADAS:
            continue
        if len(termo) > 4 and termo.endswith("s") and not termo.isdigit():
            termo = termo[:-1]
        saida.append(termo)
    return saida


def _limpar(bloco: str) -> str:
    bloco = re.sub(r"!\[[^\]]*\]\[[^\]]*\]|!\[[^\]]*\]\([^)]*\)", "", bloco)  # imagens
    bloco = re.sub(r"\\([.\-_*#()\[\]+~>|=])", r"\1", bloco)  # escapes do conversor
    linhas = []
    for linha in bloco.splitlines():
        # Linha de tabela sem conteudo: "|  |", "| :---- |".
        if re.fullmatch(r"\s*\|[\s|:\-]*\|?\s*", linha):
            continue
        linhas.append(re.sub(r"[ \t]{2,}", " ", linha).strip())
    return "\n".join(linha for linha in linhas if linha).strip()


def _partir(bloco: str) -> list[str]:
    """Bloco maior que um trecho -> pedacos por linha, com o cabecalho da tabela.

    O mapa Modbus e' uma tabela unica de dezenas de registradores, sem linha em
    branco no meio - inteira, ela virava um trecho so', e o registrador buscado
    ficava diluido entre todos os outros. Cada pedaco repete o cabecalho, senao
    as colunas ("RW", "U16", "[0,2]") chegam ao modelo sem nome.
    """
    if len(bloco) <= TAMANHO_DO_TRECHO:
        return [bloco]
    linhas = bloco.splitlines()
    cabecalho = linhas[0] if linhas[0].startswith("|") else None
    pedacos, atual = [], []
    for linha in linhas[1:] if cabecalho else linhas:
        if atual and sum(len(x) + 1 for x in atual) + len(linha) > TAMANHO_DO_TRECHO:
            pedacos.append(atual)
            atual = []
        atual.append(linha)
    if atual:
        pedacos.append(atual)
    return ["\n".join(([cabecalho] if cabecalho else []) + p) for p in pedacos]


def _colunas(linha: str) -> int:
    return linha.strip().strip("|").count("|") + 1


def _cabecalho_bruto(cru: str) -> str | None:
    """Primeira linha do bloco, se for cabecalho de tabela (seguida do separador)."""
    linhas = cru.strip().splitlines()
    # Primeira celula numerica nao e' cabecalho: na quebra de pagina o conversor
    # do PDF abre tabela nova usando a LINHA DE DADOS como cabecalho
    # ("| 10020 | Reservation Status |" seguida de separador).
    if re.match(r"^\s*\|\s*\\?\d", linhas[0]):
        return None
    if len(linhas) >= 2 and linhas[0].lstrip().startswith("|"):
        if re.fullmatch(r"\s*\|[\s|:\-]*\|?\s*", linhas[1]) and "-" in linhas[1]:
            return _limpar(linhas[0])
    return None


def _trechos_do_documento(texto: str) -> list[Trecho]:
    titulo_doc = (_TITULO_DO_DOC.search(texto) or [None, "Documentação"])[1]
    texto = re.sub(r"<!--.*?-->", "", texto, flags=re.DOTALL)

    trechos: list[Trecho] = []
    secao: str | None = None
    atual: list[str] = []
    # Ultimo cabecalho de tabela visto. O mapa Modbus tem linhas em branco NO MEIO
    # da tabela, e cada pedaco depois delas chegava sem nome de coluna: o modelo
    # via "| 1 | 10 | KW | [14,220] |" e respondeu 14 a 220 kW, quando o "10" e' o
    # fator de escala e a faixa real e' 1,4 a 22 kW.
    cabecalho: str | None = None

    def fechar():
        corpo = "\n\n".join(atual).strip()
        if corpo:
            trechos.append(Trecho(titulo_doc, secao, corpo))
        atual.clear()

    for cru in re.split(r"\n\s*\n", texto):
        bloco = _limpar(cru)
        if not bloco:
            continue
        novo = _cabecalho_bruto(cru)
        if novo:
            cabecalho = novo
        elif (
            cabecalho
            and bloco.startswith("|")
            and _colunas(bloco.splitlines()[0]) == _colunas(cabecalho)
        ):
            bloco = f"{cabecalho}\n{bloco}"
        elif not bloco.startswith("|"):
            # Texto corrido encerra a tabela: o cabecalho nao vale para a proxima.
            cabecalho = None
        # O sumario cita toda secao do manual e casaria com qualquer busca.
        if (
            _CAPITULO_DO_SUMARIO.match(bloco)
            or len(_SUMARIO.findall(bloco)) >= 6
            or bloco.strip("* ").upper() == "CONTEÚDO"
        ):
            continue
        titulo = _SECAO_EM_NEGRITO.match(bloco) or _TITULO_MD.match(bloco)
        if titulo and "\n" not in bloco:
            fechar()
            secao = titulo.group(1).strip()
            continue
        for pedaco in _partir(bloco):
            if atual and sum(len(b) for b in atual) + len(pedaco) > TAMANHO_DO_TRECHO:
                fechar()
            atual.append(pedaco)
    fechar()
    return trechos


class Indice:
    def __init__(self, trechos: list[Trecho]):
        self.trechos = trechos
        # Titulo do documento e da secao entram nos termos: "LED" no titulo
        # "3.6.3 Descrição do indicador" e' o que acha a tabela de cores.
        self._termos = [
            Counter(termos(f"{t.documento} {t.secao or ''} {t.secao or ''} {t.texto}"))
            for t in trechos
        ]
        self._tamanhos = [sum(c.values()) for c in self._termos]
        self._media = (sum(self._tamanhos) / len(self._tamanhos)) if trechos else 0.0
        frequencia: Counter[str] = Counter()
        for contagem in self._termos:
            frequencia.update(contagem.keys())
        n = len(trechos)
        self._idf = {
            termo: math.log(1 + (n - df + 0.5) / (df + 0.5)) for termo, df in frequencia.items()
        }

    def buscar(self, consulta: str, limite: int = 3) -> list[tuple[Trecho, float]]:
        pedidos = set(termos(consulta))
        if not pedidos:
            return []
        pontuados = []
        for i, contagem in enumerate(self._termos):
            nota = 0.0
            for termo in pedidos:
                f = contagem.get(termo)
                if not f:
                    continue
                norma = K1 * (1 - B + B * self._tamanhos[i] / self._media)
                peso = PESO_DE_IDENTIFICADOR if termo.isdigit() and len(termo) >= 4 else 1.0
                nota += peso * self._idf[termo] * f * (K1 + 1) / (f + norma)
            if nota > 0:
                pontuados.append((nota, i))
        pontuados.sort(reverse=True)
        return [(self.trechos[i], round(nota, 2)) for nota, i in pontuados[:limite]]


def carregar(pasta: Path = PASTA) -> Indice:
    trechos: list[Trecho] = []
    for arquivo in sorted(pasta.glob("*.md")):
        trechos.extend(_trechos_do_documento(arquivo.read_text(encoding="utf-8")))
    return Indice(trechos)


@lru_cache(maxsize=1)
def indice() -> Indice:
    return carregar()
