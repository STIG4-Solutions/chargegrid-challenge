"""A documentacao que o assistente consulta: sincronia da copia e qualidade da busca.

As perguntas abaixo sao PERGUNTAS-OURO: cada uma tem um trecho que precisa vir
entre os tres primeiros. Mexer na limpeza, no corte dos trechos ou nos
parametros do BM25 e ver uma delas cair e' o sinal de que a mudanca piorou a
busca - mesmo que tenha melhorado a pergunta que motivou a mudanca.
"""

from __future__ import annotations

import re

import pytest

from app.services.assistant import knowledge
from scripts import exportar_conhecimento as exportar


def test_a_copia_e_exatamente_o_que_o_script_gera():
    """A imagem Docker so' leva `apps/api`: a copia e' o que chega em producao."""
    if not exportar.fontes_disponiveis():
        pytest.skip("fora do checkout: as fontes da copia nao existem aqui")
    esperados = exportar.gerar()
    presentes = {a.name: a.read_bytes().decode("utf-8") for a in exportar.DESTINO.glob("*.md")}
    assert set(presentes) == set(esperados), "rode `python -m scripts.exportar_conhecimento`"
    divergentes = [nome for nome in esperados if presentes[nome] != esperados[nome]]
    assert not divergentes, (
        f"copia desatualizada: {divergentes}. Um documento ou o README mudou - "
        "rode `python -m scripts.exportar_conhecimento`, nao edite a copia."
    )


def test_a_copia_nao_carrega_imagem_em_base64():
    for arquivo in exportar.DESTINO.glob("*.md"):
        assert "data:image/" not in arquivo.read_text(encoding="utf-8"), arquivo.name


def test_o_sumario_do_manual_nao_vira_trecho():
    """O sumario cita toda secao e casaria com qualquer busca.

    Medido: sem o descarte, o sumario (partido em tres trechos) ocupava uma das
    tres vagas em 3 de 10 perguntas sobre o manual - um resultado e seus tokens
    gastos com uma lista de titulos.
    """
    padrao = re.compile(r"\b\d+\.\d+(?:\.\d+)? [A-ZÁÉÍÓÚÂÊÔÃÕÇ]")
    sumarios = [t for t in knowledge.indice().trechos if len(padrao.findall(t.texto)) >= 6]
    assert not sumarios, [t.texto[:80] for t in sumarios]


def test_nenhum_trecho_passa_muito_do_tamanho_alvo():
    maior = max(len(t.texto) for t in knowledge.indice().trechos)
    assert maior < knowledge.TAMANHO_DO_TRECHO * 1.5, maior


@pytest.mark.parametrize(
    ("pergunta", "precisa_conter"),
    [
        ("registro 10029", "10029"),
        # A consulta LITERAL que o gpt-5.4-mini mandou na medicao real. Sem o peso
        # de identificador, as palavras comuns venciam e o 10029 nem aparecia.
        ("10029 faixa de potência registrador GoodWe HCA G2", "10029"),
        ("EMS Energy Dispatch 10000", "EMS Energy Dispatch"),
        ("o que significa o LED piscando em verde", "Pisca em verde"),
        ("controle dinâmico de carga fusível", "controle dinâmico de carga"),
        ("corrente nominal de entrada trifásico", "Corrente nominal de entrada"),
        ("gerenciamento de cartões RFID", "RFID"),
        ("quantos cartões RFID o carregador aceita", "até 10"),
        ("o carregador tem OCPP", "OCPP"),
        ("quem paga o cashback", "Cashback na carteira"),
        ("por que a previsão usa a média móvel", "preditor que mede melhor"),
    ],
)
def test_pergunta_ouro_acha_o_trecho(pergunta, precisa_conter):
    achados = knowledge.indice().buscar(pergunta, 3)
    textos = [t.texto for t, _ in achados]
    assert any(precisa_conter.lower() in texto.lower() for texto in textos), (
        f"{pergunta!r} nao trouxe {precisa_conter!r} entre os tres primeiros:\n"
        + "\n---\n".join(texto[:200] for texto in textos)
    )


def test_consulta_so_com_palavra_vazia_nao_devolve_nada():
    assert knowledge.indice().buscar("o que é de para", 3) == []


def test_termos_sem_acento_e_sem_plural():
    assert knowledge.termos("Correntes Máximas do Registrador") == [
        "corrente",
        "maxima",
        "registrador",
    ]


def test_todo_trecho_do_mapa_modbus_traz_o_nome_das_colunas():
    """Sem o cabecalho, "| 1 | 10 | KW | [14,220] |" nao diz que 10 e' fator de escala.

    Foi o que aconteceu na medicao real: o modelo respondeu que o 10029 vai de
    14 a 220 kW (o certo e' 1,4 a 22 kW). O conversor do PDF parte a tabela nas
    quebras de pagina e usa a primeira linha de dados como cabecalho.
    """
    registros = [
        t
        for t in knowledge.indice().trechos
        if t.documento == "Mapa Modbus do GoodWe HCA G2"
        and re.search(r"^\| 1\d{4} ", t.texto, re.M)
    ]
    assert registros
    sem_cabecalho = [t.texto[:60] for t in registros if "#SF" not in t.texto]
    assert not sem_cabecalho, sem_cabecalho
