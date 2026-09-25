"""Carga inicial de dados.

Reproduz o cenario que o front ja usa em src/data/mockData.js (mesmos codigos de
ponto, tarifas e perfis), para trocar o mock pela API sem reescrever as telas.

    python -m app.seed

HISTORICO. O seed nao cria apenas o estado de hoje: ele gera dois anos de sessoes
encerradas e faturadas. Isso nao e' enfeite. Tres partes do produto so' existem
quando ha passado: o modelo de previsao de demanda descarta qualquer local com
menos de 180 dias de energia, os relatorios de ocupacao e retorno medem janelas
de 30 dias, e qualquer missao com prazo ("recarregue 5 vezes este mes", "tres
semanas seguidas") e' indemonstravel com uma semana de dados. Com poucos dias no
banco as tres entregam tela vazia e parecem quebradas.

O gerador e' deterministico por semente fixa. Duas maquinas que rodarem este seed
produzem o mesmo banco, e um artefato de previsao treinado numa delas continua
valido na outra - o que so' funciona porque o identificador de treino e'
`sites.slug`, escrito a mao aqui, e nao o `id`, sorteado a cada reseed.
"""

from __future__ import annotations

import asyncio
import math
import random
import secrets
import uuid
from datetime import UTC, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.core.security import hash_password
from app.db.session import SessionLocal, engine
from app.models.billing import Invoice, InvoiceLine, SitePaymentMethod, WalletEntry
from app.models.charge_point import ChargePoint, ChargePointConnection
from app.models.enums import (
    AuthMethod,
    ChargePointStatus,
    ConnectorType,
    InvoiceStatus,
    PaymentMethodKind,
    PhaseType,
    SessionState,
    StopReason,
    TariffType,
    UserRole,
)
from app.models.fleet import Fleet
from app.models.platform import PlatformPlan
from app.models.session import ChargingSession
from app.models.site import Site, SiteMeterReading
from app.models.subscription import DriverPlan
from app.models.tariff import ALL_DAYS, WEEKDAYS, WEEKEND, Tariff, TariffWindow
from app.models.user import RfidCard, User, Vehicle

log = get_logger(__name__)

# O equipamento sai do CARATER do local, e nao de uma lista solta por praca.
#
# Era uma lista geral mais uma de rodovia, e quase toda praca usava a geral - um
# shopping e um condominio recebiam o mesmo hardware de um escritorio. Isso passou
# a importar quando o modelo de previsao deixou de ler o arquetipo de um mapa de
# slugs e passou a INFERI-LO do equipamento (`forecast/banco.arquetipo_de`): com
# hardware igual, shopping e condominio seriam lidos como corporativo, e a
# sazonalidade por arquetipo deixaria de valer justamente neles.
#
# Os quatro sao separaveis sem ambiguidade, o que e' o requisito da inferencia:
#
#   rodovia      DC >= 100 kW   enche o tanque em quinze minutos
#   shopping     DC  <  100 kW  carrega enquanto a pessoa esta' no cinema
#   corporativo  AC trifasico   o carro fica o turno inteiro
#   condominio   AC monofasico  carrega de noite, a vaga e' da pessoa
#
# Numeros na faixa do `gerador_cdr.py` do projeto de origem do pipeline, onde a
# calibragem por arquetipo ja' estava feita: 150 / 60 / 22 / 7,4 kW.
PONTOS_POR_CARATER = {
    # code, nome, conector, kW nominal, fases, prioridade
    "rodovia": [
        ("CP-01", "Carregador Ultrarrapido 01", ConnectorType.CCS2, 150.0, PhaseType.THREE, 200),
        ("CP-02", "Carregador Ultrarrapido 02", ConnectorType.CCS2, 150.0, PhaseType.THREE, 200),
        ("CP-03", "Carregador Rapido 03", ConnectorType.CHADEMO, 120.0, PhaseType.THREE, 150),
        ("CP-04", "Carregador Rapido 04", ConnectorType.CCS2, 100.0, PhaseType.THREE, 150),
    ],
    "shopping": [
        ("CP-01", "Carregador Rapido 01", ConnectorType.CCS2, 60.0, PhaseType.THREE, 200),
        ("CP-02", "Carregador Rapido 02", ConnectorType.CCS2, 60.0, PhaseType.THREE, 200),
        ("CP-03", "Carregador Rapido 03", ConnectorType.CHADEMO, 50.0, PhaseType.THREE, 150),
        ("CP-04", "Carregador Rapido 04", ConnectorType.CCS2, 60.0, PhaseType.THREE, 100),
    ],
    "corporativo": [
        ("CP-01", "Ponto de Recarga 01", ConnectorType.TYPE2, 22.0, PhaseType.THREE, 200),
        ("CP-02", "Ponto de Recarga 02", ConnectorType.TYPE2, 22.0, PhaseType.THREE, 100),
        ("CP-03", "Ponto de Recarga 03", ConnectorType.TYPE2, 22.0, PhaseType.THREE, 100),
        ("CP-04", "Ponto de Recarga 04", ConnectorType.TYPE2, 11.0, PhaseType.THREE, 50),
    ],
    # TODOS monofasicos, e nao por estilo: um unico ponto trifasico faria a
    # inferencia ler o predio como escritorio.
    "condominio": [
        ("CP-01", "Ponto de Recarga 01", ConnectorType.TYPE2, 7.4, PhaseType.SINGLE, 200),
        ("CP-02", "Ponto de Recarga 02", ConnectorType.TYPE2, 7.4, PhaseType.SINGLE, 100),
        ("CP-03", "Ponto de Recarga 03", ConnectorType.TYPE2, 7.4, PhaseType.SINGLE, 100),
        ("CP-04", "Ponto de Recarga 04", ConnectorType.TYPE2, 7.4, PhaseType.SINGLE, 50),
    ],
}


def _senha(configurada: str | None, rotulo: str, sorteadas: dict[str, str]) -> str:
    """Senha do seed: a do ambiente, ou uma sorteada e anunciada uma unica vez.

    Nao ha valor embutido de proposito. Uma senha escrita no repositorio vale
    para toda instalacao que o clonar, e este seed cria contas de admin.
    """
    if configurada:
        return configurada
    gerada = secrets.token_urlsafe(12)
    sorteadas[rotulo] = gerada
    return gerada


# Planos de recarga. Escopo de rede: nao pertencem a praca nenhuma.
#
# Dois de proposito, e nao um: com um so' nao ha escolha a demonstrar, e a tela
# de assinatura vira um botao. Os dois se diferenciam pelo EIXO, nao pelo
# tamanho - um da desconto percentual, o outro da franquia de kWh -, porque e'
# assim que o motorista percebe qual serve para ele.
#
# Nenhum isenta ociosidade: essa taxa nao e' receita, e' o que libera a vaga.
PLANOS = [
    # codigo, nome, descricao, mensalidade, desconto %, kWh inclusos, isenta taxa
    (
        "leve",
        "Plano Leve",
        "Para quem carrega de vez em quando.",
        19.90,
        10.0,
        0.0,
        True,
    ),
    (
        "mensal",
        "Plano Mensal",
        "Para quem usa o carro todo dia.",
        49.90,
        15.0,
        30.0,
        True,
    ),
]

# O que a GoodWe vende ao estabelecimento.
#
# A mensalidade e' a parte chata; o que faz o modelo valer e'
# `fee_percent_transacao` sobre o faturamento do site - ele cresce com o cliente
# sem renegociacao. Os dois planos trocam uma coisa pela outra de proposito: o
# menor cobra pouco fixo e mais taxa, o maior o contrario.
PLANOS_DA_PLATAFORMA = [
    # codigo, nome, descricao, mensal, por ponto, inclusos, taxa %, meses minimos
    (
        "essencial",
        "Essencial",
        "Para quem esta comecando: mensalidade baixa, taxa maior por transacao.",
        149.00,
        35.00,
        2,
        3.5,
        12,
    ),
    (
        "rede",
        "Rede",
        "Para operacao com varios pontos: mensalidade maior, taxa menor.",
        499.00,
        20.00,
        8,
        1.5,
        12,
    ),
]

DRIVERS = [
    ("joao.silva@email.com", "Joao Silva", "Nissan Leaf", "40 kWh", 40.0, 6.6),
    ("maria.souza@email.com", "Maria Souza", "BYD Dolphin", "44 kWh", 44.9, 11.0),
    ("carlos.lima@email.com", "Carlos Lima", "VW ID.4", "77 kWh", 77.0, 11.0),
    ("ana.costa@email.com", "Ana Costa", "Tesla Model 3", "60 kWh", 57.5, 11.0),
    ("pedro.alves@email.com", "Pedro Alves", "GWM Ora 03", "48 kWh", 48.0, 6.6),
]

# A frota existia como modelo, rota (`/app/fleet/report`) e tela (`FleetScreen`)
# desde a 0013 - e o seed nao criava nenhuma. Zero frotas, zero motoristas com
# frota, zero veiculos com centro de custo: a aba do app abria vazia para todo
# mundo, e o relatorio corporativo nao tinha o que relatar.
#
# Dois dos cinco motoristas entram nela. Dois e nao cinco de proposito: e' o que
# torna VISIVEL a diferenca entre campanha dirigida a frota e campanha para
# todos - com todo mundo dentro, os dois casos pareceriam iguais na tela.
FROTA = {
    "nome": "Logistica Sao Paulo LTDA",
    "documento": "12.345.678/0001-90",
    "email_de_cobranca": "financeiro@logisticasp.com.br",
}
MOTORISTAS_DA_FROTA = {
    "maria.souza@email.com": "CC-COMERCIAL",
    "carlos.lima@email.com": "CC-OPERACOES",
}
# Um dos dois e' GESTOR, e o outro nao. `require_fleet_manager` exige as duas
# coisas - `fleet_manager` E `fleet_id` -, entao pertencer a frota nao basta
# para ver o relatorio consolidado.
#
# Marcar so' um deixa a diferenca demonstravel: o gestor abre a aba Frota, o
# colega da mesma empresa toma 403. Com os dois marcados, o recorte de leitura
# que `deps.py` descreve nao apareceria em lugar nenhum.
GESTOR_DA_FROTA = "maria.souza@email.com"

# ---------------------------------------------------------------------------
# Historico
# ---------------------------------------------------------------------------

# A semente e' fixa e o valor nao importa - o que importa e' que nao mude. O
# gerador de CDR do projeto de modelagem usa 42 pela mesma razao, e repetir o
# numero deixa claro que a escolha e' convencao, nao ajuste fino.
SEMENTE_DO_HISTORICO = 42

# Quatro anos, e o numero vem de uma conta sobre SAZONALIDADE, nao de folga.
#
# Eram dois anos, que bastam para o piso de historico do modelo e para aquecer a
# media de 182. Mas o backtest treina so' com meses estritamente anteriores ao
# mes de teste: para prever julho de 2026 com dois anos de historico, o modelo
# viu julho UMA vez. Sao 12 parametros sazonais com uma observacao cada - nao e'
# estimavel, e o resultado medido foi o modelo perdendo da media movel mesmo
# depois de `PESOS_MENSAIS` criar o sinal (16,6% contra 11,4% da regua).
#
# Com quatro anos cada mes do ano aparece tres vezes antes de ser previsto. O
# gargalo nao era numero de pracas - era comprimento de historico.
DIAS_DE_HISTORICO = 1460

# O historico e' gerado em hora local porque as janelas de tarifa (ponta 18h-21h)
# sao locais. Gerar em UTC deslocaria a ponta em tres horas, e o conselho de
# horario do app passaria a recomendar exatamente o pior momento.
FUSO_DO_SITE = ZoneInfo("America/Sao_Paulo")

# Peso por hora do dia (indice 0-23), por carater do local. Nao somam 1: sao
# pesos relativos de um sorteio.
PERFIS_HORARIOS = {
    "corporativo": (
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
        0.2,
        0.6,
        1.8,
        3.2,
        3.0,
        2.2,
        1.6,
        1.4,
        1.5,
        1.6,
        1.8,
        2.4,
        3.4,
        3.0,
        1.6,
        0.8,
        0.4,
        0.2,
        0.1,
    ),
    "shopping": (
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
        0.1,
        0.2,
        0.4,
        0.8,
        1.2,
        1.8,
        2.4,
        2.8,
        2.6,
        2.4,
        2.6,
        3.0,
        3.4,
        3.6,
        3.4,
        2.8,
        1.8,
        0.8,
        0.3,
    ),
    # Estrada tem movimento cedo e no comeco da tarde, e quase nada de
    # madrugada - quem viaja a noite nao para para carregar por opcao.
    "rodovia": (
        0.3,
        0.2,
        0.2,
        0.2,
        0.3,
        0.8,
        1.8,
        2.6,
        2.8,
        2.6,
        2.4,
        2.2,
        2.0,
        2.4,
        2.6,
        2.4,
        2.2,
        2.0,
        1.8,
        1.4,
        1.0,
        0.8,
        0.6,
        0.4,
    ),
    # Predio residencial: o carro chega a noite e passa a madrugada plugado.
    "condominio": (
        0.6,
        0.4,
        0.3,
        0.2,
        0.2,
        0.2,
        0.4,
        0.8,
        0.9,
        0.7,
        0.6,
        0.6,
        0.7,
        0.7,
        0.7,
        0.8,
        1.0,
        1.6,
        2.8,
        3.6,
        3.4,
        2.6,
        1.6,
        0.9,
    ),
}

# Peso por dia da semana (0 = segunda ... 6 = domingo).
PERFIS_SEMANAIS = {
    "corporativo": (1.15, 1.20, 1.20, 1.15, 1.00, 0.35, 0.22),
    "shopping": (0.78, 0.80, 0.85, 0.95, 1.20, 1.48, 1.28),
    "rodovia": (0.82, 0.82, 0.88, 1.02, 1.38, 1.42, 1.28),
    "condominio": (1.00, 1.00, 1.02, 1.05, 1.10, 0.95, 0.88),
}

# Sazonalidade anual por CARATER do local, e nao uma curva so' para a rede.
#
# Era uma tupla unica, igual para todas as pracas. O efeito disso e' medivel, e
# foi medido: com sazonalidade comum nao ha o que o modelo de previsao
# diferencie entre locais, e ele perde da propria regua - 9,26% de WAPE mensal
# contra 9,07%. No painel do projeto de origem do pipeline, onde o peso mensal
# varia por carater, o MESMO codigo faz 7,78% contra 10,40%: ganha por 2,6
# pontos. E as reguas medem praticamente igual nos dois dados (m28 diario 33,08
# aqui, 33,06 la'), ou seja, o que muda e' so' o modelo - assinatura de sinal
# aprendivel que regua nenhuma alcanca.
#
# E' tambem o comportamento real. Uma rodovia enche nas ferias justamente
# quando um corporativo esvazia: janeiro e' +30% num caso e -20% no outro. Uma
# media movel de 28 dias nao tem como saber disso; um modelo com `archetype`
# como feature tem.
#
# Os numeros vem de `simulate/gerador_cdr.py` do projeto de origem
# (`_MES_RODOVIA`, `_MES_SHOP`, `_MES_CORP`, `_MES_NEUTRO`), onde o raciocinio
# ja' estava feito: ferias de janeiro e julho, festas de fim de ano, retracao
# corporativa em dezembro e janeiro.
PESOS_MENSAIS = {
    "rodovia": (1.30, 1.10, 0.95, 0.95, 0.90, 0.95, 1.25, 1.00, 0.95, 1.05, 1.05, 1.35),
    "shopping": (0.95, 0.95, 1.00, 1.00, 1.00, 1.00, 1.05, 1.00, 1.00, 1.05, 1.10, 1.30),
    "corporativo": (0.80, 1.00, 1.05, 1.05, 1.05, 1.00, 0.95, 1.05, 1.05, 1.05, 1.00, 0.75),
    # Quem mora no predio carrega o ano todo: nao ha ferias que mudem isso.
    "condominio": (1.0,) * 12,
}

# Crescimento da frota eletrica no periodo, ao ano. A rede nao tem o mesmo
# movimento em 2024 e em 2026, e um historico plano ensinaria ao modelo que o
# futuro e' igual ao passado.
CRESCIMENTO_ANUAL = 0.38

# Um local recem-aberto nao enche no primeiro dia. Meia-vida de 90 dias.
MEIA_VIDA_DE_MATURACAO = 90

# Energia por sessao: lognormal, com mediana e dispersao POR CARATER.
#
# Era uma mediana unica de 18 kWh para todos, mais um fator de 1,45 so' para
# rodovia. Isso subestimava a estrada (26 kWh efetivos) e superestimava predio:
# um DC de 60 kW na Anhanguera nao entrega o mesmo que um AC de 22 kW num
# escritorio, porque quem para na estrada enche o tanque e quem estaciona no
# trabalho completa o que gastou vindo.
#
# A dispersao tambem e' por carater, e e' o que mais importa para a previsao:
# era 0,55 em tudo. Corporativo e condominio tem rotina - a mesma pessoa, o
# mesmo trajeto - e dispersam pouco (0,35 e 0,30). Rodovia e shopping recebem
# quem passa, e dispersam mais. Sigma alto em local de rotina inventava ruido
# que nao existe, e ruido inventado e' erro que nenhum modelo pode remover.
#
# Numeros de `simulate/gerador_cdr.py` do projeto de origem (`kwh_mediana`,
# `kwh_sigma`), onde a calibragem por arquetipo ja' estava feita.
ENERGIA_POR_SESSAO = {
    "rodovia": (38.0, 0.45),
    "shopping": (24.0, 0.50),
    "corporativo": (19.0, 0.35),
    "condominio": (16.0, 0.30),
}
MINIMO_KWH = 1.8
# Teto fisico: nenhum carro do seed tem bateria maior que isso.
TETO_KWH = 78.0

# Fracao da potencia nominal efetivamente entregue. Bateria nao aceita carga
# nominal do inicio ao fim; o valor sai da curva de aceitacao tipica.
RENDIMENTO_DO_PONTO = 0.72

# Folga minima entre duas sessoes no mesmo ponto: desplugar, sair da vaga, outro
# carro chegar e plugar.
FOLGA_ENTRE_SESSOES = timedelta(minutes=12)

# Com que frequencia um motorista do app volta a carregar. Duas a quatro vezes
# por semana e' o uso de quem depende do carro no dia a dia.
DIAS_ENTRE_RECARGAS = (2.0, 4.0)

# O resto das sessoes fica sem dono. Nao e' lacuna: rede publica atende muito
# visitante avulso, e inventar quarenta contas de login so' para preencher o
# historico criaria usuarios que ninguem consegue explicar na demonstracao.
PROPORCAO_SEM_DONO = 0.82

# Faturas ainda em aberto entre as mais recentes. Sem nenhuma, a tela de faturas
# do app abre so' com "pago" e o fluxo de pagamento nao tem o que fazer.
DIAS_COM_FATURA_ABERTA = 6

# slug, nome, endereco, cidade, UF, lat, lon, carater, sessoes/dia, kW da rede,
# demanda contratada, dias de operacao, QUANTIDADE de pontos (o hardware sai do
# carater, em PONTOS_POR_CARATER)
SITES = [
    (
        "lab-fiap-eco-station",
        "LAB FIAP Eco Station",
        "Av. Lins de Vasconcelos, 1264 - Aclimacao, Sao Paulo",
        "Sao Paulo",
        "SP",
        -23.568500,
        -46.632200,
        "corporativo",
        9.0,
        75.0,
        75.0,
        DIAS_DE_HISTORICO,
        4,
    ),
    (
        "shopping-morumbi-g3",
        "Shopping Morumbi - Piso G3",
        "Av. Roque Petroni Junior, 1089 - Jardim das Acacias, Sao Paulo",
        "Sao Paulo",
        "SP",
        -23.622700,
        -46.698900,
        "shopping",
        13.0,
        120.0,
        110.0,
        DIAS_DE_HISTORICO,
        4,
    ),
    (
        "posto-anhanguera-km-68",
        "Posto Anhanguera km 68",
        "Rodovia Anhanguera, km 68 - Jundiai",
        "Jundiai",
        "SP",
        -23.185600,
        -46.897300,
        "rodovia",
        15.0,
        400.0,
        380.0,
        DIAS_DE_HISTORICO,
        4,
    ),
    # A SEGUNDA praca de cada carater, e a razao e' medida.
    #
    # Com uma praca por arquetipo, `archetype` fica perfeitamente colinear com
    # `location_id`: o modelo aprende "esta praca tem este padrao", nunca
    # "rodovias tem este padrao", e nao generaliza para uma praca nova. Pior,
    # com dois anos de historico sao DUAS observacoes por mes do ano para cada
    # padrao sazonal - o modelo paga a variancia de tentar aprender sazonalidade
    # sem dado que a fixe.
    #
    # O projeto de origem do pipeline tem 8 estacoes em 4 arquetipos, 2 a 3 de
    # cada, e la' o modelo ganha da melhor regua por 1,44 ponto. Duas de cada e'
    # o minimo para a feature significar carater em vez de identidade.
    #
    # Tamanhos de proposito diferentes dos primeiros: clonar uma praca nao
    # acrescenta informacao nenhuma ao treino.
    (
        "centro-empresarial-berrini",
        "Centro Empresarial Berrini",
        "Av. Engenheiro Luis Carlos Berrini, 1681 - Brooklin, Sao Paulo",
        "Sao Paulo",
        "SP",
        -23.610800,
        -46.694400,
        "corporativo",
        7.0,
        60.0,
        55.0,
        DIAS_DE_HISTORICO,
        4,
    ),
    (
        "shopping-tambore",
        "Shopping Tambore",
        "Av. Piracema, 669 - Tambore, Barueri",
        "Barueri",
        "SP",
        -23.500100,
        -46.842200,
        "shopping",
        11.0,
        100.0,
        95.0,
        DIAS_DE_HISTORICO,
        4,
    ),
    (
        "rodovia-castello-km-32",
        "Rodovia Castello km 32",
        "Rodovia Castello Branco, km 32 - Barueri",
        "Barueri",
        "SP",
        -23.510600,
        -46.876100,
        "rodovia",
        12.0,
        350.0,
        330.0,
        DIAS_DE_HISTORICO,
        4,
    ),
    # Condominio com historico completo. O outro condominio do seed tem 118 dias
    # de proposito, e sem este o carater nao entraria no treino em local nenhum.
    (
        "residencial-parque-das-nacoes",
        "Residencial Parque das Nacoes",
        "Av. das Nacoes Unidas, 1200 - Centro, Osasco",
        "Osasco",
        "SP",
        -23.532400,
        -46.791600,
        "condominio",
        4.0,
        37.0,
        33.0,
        DIAS_DE_HISTORICO,
        3,
    ),
    # Aberto ha quatro meses, de proposito: ~120 dias, ABAIXO dos 180 que o modelo
    # de previsao exige. E' o caso que faz a tela dizer "sem historico suficiente"
    # em vez de exibir uma previsao inventada - e sem um local assim no banco,
    # essa guarda nunca seria exercitada antes de chegar a um cliente real.
    (
        "residencial-vila-mariana",
        "Residencial Vila Mariana",
        "Rua Domingos de Morais, 2187 - Vila Mariana, Sao Paulo",
        "Sao Paulo",
        "SP",
        -23.601400,
        -46.638700,
        "condominio",
        5.0,
        45.0,
        40.0,
        118,
        3,
    ),
]


def _poisson(rng: random.Random, media: float) -> int:
    """Sorteio de contagem por Knuth.

    `random` nao traz Poisson, e arredondar uma normal produz numero negativo
    nos dias fracos - justamente os que dao carater a serie. As medias aqui sao
    de uma dezena, entao exp(-media) nao subborda.
    """
    if media <= 0:
        return 0
    limite = math.exp(-media)
    k = 0
    produto = 1.0
    while True:
        produto *= rng.random()
        if produto <= limite:
            return k
        k += 1


def _sorteia_hora(rng: random.Random, pesos: tuple[float, ...]) -> int:
    """Hora do dia segundo o perfil do local."""
    return rng.choices(range(24), weights=pesos, k=1)[0]


def _fracao_solar(hora: int) -> float:
    """Quanto da energia daquela sessao veio do sol.

    Zero de madrugada, maximo ao meio-dia. Um percentual fixo - como o 31% que
    havia aqui antes - faria o app anunciar recarga verde as tres da manha, e
    qualquer missao de energia limpa premiaria o horario errado.
    """
    if hora < 6 or hora > 18:
        return 0.0
    return 0.58 * math.sin(math.pi * (hora - 6) / 12) ** 2


async def _alcancar_o_maximo_gravado(db, sequencia: str, tabela: str) -> None:
    """Empurra a sequencia para depois do maior codigo que a tabela JA tem.

    A sequencia sozinha nao basta, e isto nao e' teoria: gerando historico no
    staging, `nextval('invoice_code_seq')` devolveu 2001 e `INV-2001` ja' existia
    - o UNIQUE `ix_invoices_code` derrubou a execucao depois de cinco minutos
    montando linhas.

    A causa e' historica. Os codigos do seed saiam de um intervalo escolhido a mao
    (INV-2001 em diante) antes de passarem a vir da sequencia, e a sequencia de
    faturas comeca em 1001. Um banco povoado naquela epoca ficou com codigos ACIMA
    da sequencia, e nada nunca a reconciliou.

    O numero sai do proprio codigo (`INV-2001` -> 2001), porque e' ele que o UNIQUE
    guarda - confiar na sequencia e' justamente o que falhou.
    """
    await db.execute(
        text(
            rf"""
            SELECT setval(
                '{sequencia}',
                GREATEST(
                    (SELECT COALESCE(
                        MAX(NULLIF(regexp_replace(code, '\D', '', 'g'), '')::bigint), 0)
                     FROM {tabela}),
                    (SELECT last_value FROM {sequencia})
                )
            )
            """
        )
    )


async def _reservar_codigos(db, sequencia: str, quantidade: int, tabela: str) -> int:
    """Reserva um bloco continuo de codigos e devolve o primeiro.

    Puxa da sequencia em vez de um intervalo fixo, e antes disso a reconcilia com
    o que a tabela tem - ver `_alcancar_o_maximo_gravado`.
    """
    await _alcancar_o_maximo_gravado(db, sequencia, tabela)
    primeiro = (await db.execute(text(f"SELECT nextval('{sequencia}')"))).scalar_one()
    if quantidade > 1:
        await db.execute(
            text(f"SELECT setval('{sequencia}', :ultimo)"),
            {"ultimo": int(primeiro) + quantidade - 1},
        )
    return int(primeiro)


async def _montar_site(db, especificacao: tuple) -> dict:
    """Cria um site completo: tarifas, pontos e meios de pagamento."""
    (
        slug,
        nome,
        endereco,
        cidade,
        uf,
        lat,
        lon,
        carater,
        sessoes_dia,
        grid_kw,
        demanda_kw,
        dias,
        quantos_pontos,
    ) = especificacao

    # O hardware sai do carater, nao da tupla: e' o que torna impossivel um
    # shopping nascer com equipamento de escritorio - e a inferencia de arquetipo
    # le' justamente o equipamento.
    pontos = PONTOS_POR_CARATER[carater][:quantos_pontos]

    site = Site(
        slug=slug,
        name=nome,
        address=endereco,
        city=cidade,
        state=uf,
        latitude=lat,
        longitude=lon,
        grid_limit_kw=grid_kw,
        reserved_kw=round(grid_kw * 0.27, 1),
        main_breaker_current_a=round(grid_kw * 2.0, 1),
        allow_pv_kw=True,
        allow_battery_kw=True,
        battery_min_soc=20.0,
        # Contrato de demanda. A tarifa e' a ordem de grandeza tipica de um A4
        # comercial no Sudeste; o valor real vem da fatura do cliente. Sem ela o
        # custo evitado sai em kW e nao em reais.
        contracted_demand_kw=demanda_kw,
        demand_tariff_brl_per_kw=28.50,
        # Recuado no tempo. `dias_operacao` e' feature do modelo de previsao, e
        # um site nascido hoje com dois anos de sessoes e' uma contradicao que o
        # proprio pipeline do modelo detectaria.
        created_at=datetime.now(UTC) - timedelta(days=dias),
    )
    db.add(site)
    await db.flush()

    # ---- tarifas: ponta / fora de ponta / por tempo ----
    peak = Tariff(
        site_id=site.id,
        name="Tarifa Ponta",
        type=TariffType.TIME_OF_USE,
        # Preco base = fora de ponta: e o fallback caso algum instante escape das
        # janelas, e cobrar ponta por engano penaliza o cliente.
        price_per_kwh=1.40,
        idle_fee_per_min=0.20,
        free_minutes=5,
        min_charge=5.00,
    )
    # Ponta 50% acima da fora de ponta. A razao nao e' arbitraria: na tarifa
    # branca da ANEEL a ponta chega a dobrar a fora de ponta, entao 1,5x e'
    # conservador para um operador que revende. Com os 7% que havia aqui antes,
    # a diferenca sumia no arredondamento e o conselho de horario do app -
    # "comece as 21h e pague menos" - nao tinha o que recomendar.
    peak.windows.append(
        TariffWindow(
            label="Ponta",
            day_mask=WEEKDAYS,
            starts_at=time(18, 0),
            ends_at=time(21, 0),
            price_per_kwh=2.10,
            idle_fee_per_min=0.20,
        )
    )
    peak.windows.append(
        TariffWindow(
            label="Fora de ponta",
            day_mask=ALL_DAYS,
            starts_at=time(21, 0),
            ends_at=time(18, 0),
            price_per_kwh=1.40,
            idle_fee_per_min=0.10,
        )
    )
    # A janela de ponta so vale em dia util, entao o intervalo 18h-21h do fim de
    # semana ficaria descoberto e cairia no preco base.
    peak.windows.append(
        TariffWindow(
            label="Fora de ponta",
            day_mask=WEEKEND,
            starts_at=time(18, 0),
            ends_at=time(21, 0),
            price_per_kwh=1.40,
            idle_fee_per_min=0.10,
        )
    )

    off_peak = Tariff(
        site_id=site.id,
        name="Tarifa Fora de Ponta",
        type=TariffType.PER_KWH,
        price_per_kwh=1.40,
        idle_fee_per_min=0.10,
        free_minutes=5,
    )
    by_time = Tariff(
        site_id=site.id,
        name="Sessão por Tempo",
        type=TariffType.PER_TIME,
        price_per_min=0.35,
        active=False,
    )
    db.add_all([peak, off_peak, by_time])
    await db.flush()
    site.default_tariff_id = peak.id

    # ---- pontos de recarga ----
    criados = []
    for code, name, connector, rated, phase, priority in pontos:
        cp = ChargePoint(
            site_id=site.id,
            code=code,
            name=name,
            connector=connector,
            phase_type=phase,
            rated_kw=rated,
            # Piso do reg 10029: 1,4 kW monofasico / 4,2 kW trifasico.
            min_kw=1.4 if phase == PhaseType.SINGLE else 4.2,
            limit_kw=rated,
            priority=priority,
            status=ChargePointStatus.OFFLINE,
        )
        cp.connection = ChargePointConnection(protocol="modbus_tcp", host=None, port=502, unit_id=1)
        db.add(cp)
        criados.append(cp)
    await db.flush()

    # ---- metodos de pagamento (taxas tipicas do mercado brasileiro) ----
    db.add_all(
        [
            SitePaymentMethod(
                site_id=site.id, kind=PaymentMethodKind.PIX, label="Pix", fee_percent=0.0
            ),
            SitePaymentMethod(
                site_id=site.id,
                kind=PaymentMethodKind.CREDIT_CARD,
                label="Cartao de credito",
                fee_percent=3.2,
                fee_fixed=0.39,
            ),
            SitePaymentMethod(
                site_id=site.id,
                kind=PaymentMethodKind.RFID_SUBSCRIPTION,
                label="Cartao RFID / assinatura",
                fee_percent=0.0,
            ),
            SitePaymentMethod(
                site_id=site.id,
                kind=PaymentMethodKind.WALLET,
                label="Carteira digital (app)",
                fee_percent=1.0,
                enabled=False,
            ),
        ]
    )

    return {
        "site": site,
        "peak": peak,
        "off_peak": off_peak,
        "pontos": criados,
        "carater": carater,
        "sessoes_dia": sessoes_dia,
        "dias": dias,
    }


def _sessoes_do_site(rng: random.Random, montado: dict, agora: datetime) -> list[dict]:
    """Sorteia as sessoes de um site ao longo de toda a sua operacao.

    Devolve dicionarios crus, ainda sem dono e sem codigo: quem e' o motorista so'
    pode ser decidido depois, olhando a rede inteira em ordem cronologica, porque
    uma pessoa nao carrega em dois lugares ao mesmo tempo.
    """
    carater = montado["carater"]
    horas = PERFIS_HORARIOS[carater]
    semana = PERFIS_SEMANAIS[carater]
    mes_a_mes = PESOS_MENSAIS[carater]
    mediana_kwh, desvio_kwh = ENERGIA_POR_SESSAO[carater]
    pontos = montado["pontos"]
    dias = montado["dias"]
    e_rodovia = carater == "rodovia"

    hoje = agora.astimezone(FUSO_DO_SITE).date()
    nascimento = hoje - timedelta(days=dias)
    sessoes: list[dict] = []

    # A ocupacao de um ponto nao zera a meia-noite. Enquanto isto era reiniciado
    # a cada dia, uma sessao comecada as 23h50 seguia ocupando o conector no dia
    # seguinte sem que o gerador soubesse, e a primeira sessao da madrugada
    # entrava por cima: 23 pares de carros plugados ao mesmo tempo no mesmo
    # conector, em dois anos. O banco nao reclamaria - o indice unico so' cobre
    # sessao ATIVA, e historico nasce faturado -, mas o relatorio de ocupacao
    # passaria de 100% e ninguem saberia por que.
    ultimo_fim: dict[uuid.UUID, datetime] = {}

    for atraso in range(dias, 0, -1):
        dia = hoje - timedelta(days=atraso)
        idade = (dia - nascimento).days

        crescimento = (1.0 + CRESCIMENTO_ANUAL) ** ((idade - dias) / 365.0)
        maturacao = 1.0 - math.exp(-idade / MEIA_VIDA_DE_MATURACAO)
        media = (
            montado["sessoes_dia"]
            * semana[dia.weekday()]
            * mes_a_mes[dia.month - 1]
            * crescimento
            * maturacao
        )

        for ponto in pontos:
            quantidade = _poisson(rng, media / len(pontos))
            if quantidade == 0:
                continue

            for hora in sorted(_sorteia_hora(rng, horas) for _ in range(quantidade)):
                inicio = datetime(
                    dia.year,
                    dia.month,
                    dia.day,
                    hora,
                    rng.randrange(60),
                    tzinfo=FUSO_DO_SITE,
                )
                # O ponto e' um recurso fisico: enquanto um carro esta plugado,
                # nenhum outro entra. Empurrar em vez de descartar preserva a
                # contagem do dia e produz a fila que se ve num local cheio.
                anterior = ultimo_fim.get(ponto.id)
                if anterior is not None and inicio < anterior + FOLGA_ENTRE_SESSOES:
                    inicio = anterior + FOLGA_ENTRE_SESSOES
                if inicio.date() != dia:
                    break

                kwh = rng.lognormvariate(math.log(mediana_kwh), desvio_kwh)
                kwh = round(min(max(kwh, MINIMO_KWH), TETO_KWH), 3)

                potencia = float(ponto.rated_kw) * RENDIMENTO_DO_PONTO
                minutos = max(8, int(round(kwh / potencia * 60)))
                fim = inicio + timedelta(minutes=minutos)
                # Ociosidade: o carro terminou e ninguem veio busca-lo. Comum em
                # escritorio e predio, raro na estrada.
                ocioso = 0
                if rng.random() < (0.08 if e_rodovia else 0.24):
                    ocioso = rng.randrange(5, 90)
                ultimo_fim[ponto.id] = fim + timedelta(minutes=ocioso)

                sessoes.append(
                    {
                        "site_id": montado["site"].id,
                        "charge_point_id": ponto.id,
                        "inicio": inicio,
                        "fim": fim,
                        "ocioso": ocioso,
                        "kwh": kwh,
                        # A hora vem de `inicio`, e nao da `hora` sorteada: a
                        # sessao pode ter sido empurrada para frente pela fila do
                        # ponto. Uma sorteada as 18h que so' comeca as 19h30
                        # levava credito solar noite adentro.
                        "verde": round(kwh * _fracao_solar(inicio.hour), 3),
                        "minutos": minutos,
                        "pico": round(min(float(ponto.rated_kw), kwh / (minutos / 60.0)), 3),
                        "peak_id": montado["peak"].id,
                        "off_peak_id": montado["off_peak"].id,
                        "peak_nome": montado["peak"].name,
                        "off_peak_nome": montado["off_peak"].name,
                    }
                )

    return sessoes


def _atribui_motoristas(
    rng: random.Random,
    sessoes: list[dict],
    motoristas: list[User],
    veiculos: dict[uuid.UUID, Vehicle],
) -> None:
    """Decide quais sessoes pertencem aos motoristas do app.

    Percorre a rede em ordem cronologica e respeita um intervalo pessoal entre
    recargas. Sao os dois motivos de existir: sem a ordem, a mesma pessoa
    apareceria carregando em dois sites simultaneos; sem o intervalo, cada
    motorista teria varias recargas por dia e nenhuma missao com prazo faria
    sentido - "recarregue 5 vezes este mes" estaria cumprida na primeira semana.
    """
    livre_a_partir_de: dict[uuid.UUID, datetime] = {}

    for sessao in sessoes:
        if rng.random() < PROPORCAO_SEM_DONO:
            continue

        candidatos = [
            m
            for m in motoristas
            if sessao["inicio"] >= livre_a_partir_de.get(m.id, sessao["inicio"])
        ]
        if not candidatos:
            continue

        dono = rng.choice(candidatos)
        sessao["user_id"] = dono.id
        sessao["vehicle_id"] = veiculos[dono.id].id if dono.id in veiculos else None
        livre_a_partir_de[dono.id] = sessao["fim"] + timedelta(
            days=rng.uniform(*DIAS_ENTRE_RECARGAS)
        )


async def _gravar_historico(db, sessoes: list[dict], agora: datetime) -> int:
    """Escreve sessoes, faturas e linhas de fatura em lote.

    Em lote, e nao pelo motor de tarifacao, por uma razao de custo: `bill_session`
    reprocessa telemetria e emite consultas por sessao. Vinte mil sessoes por
    esse caminho levariam minutos a cada reseed. O motor ja tem cobertura propria;
    o que o seed precisa e' de faturas coerentes, nao de reprovar o motor de novo.

    Nao ha telemetria para o historico pelo mesmo motivo: seriam milhoes de
    amostras para alimentar graficos que ninguem abre em datas de dois anos atras.
    """
    if not sessoes:
        return 0

    primeiro_ses = await _reservar_codigos(
        db, "session_code_seq", len(sessoes), "charging_sessions"
    )
    primeira_inv = await _reservar_codigos(db, "invoice_code_seq", len(sessoes), "invoices")

    linhas_sessao: list[dict] = []
    linhas_fatura: list[dict] = []
    linhas_item: list[dict] = []

    for indice, s in enumerate(sessoes):
        inicio, fim, ocioso = s["inicio"], s["fim"], s["ocioso"]
        local = inicio.astimezone(FUSO_DO_SITE)
        # Ponta: dia util, das 18h as 21h, hora local. Mesma regra das janelas
        # gravadas na tarifa - se as duas divergirem, o historico contradiz o
        # simulador de tarifa exibido na propria tela.
        na_ponta = local.weekday() < 5 and 18 <= local.hour < 21
        preco = 2.10 if na_ponta else 1.40
        tarifa_id = s["peak_id"] if na_ponta else s["off_peak_id"]
        tarifa_nome = s["peak_nome"] if na_ponta else s["off_peak_nome"]
        taxa_ociosa = round(ocioso * (0.20 if na_ponta else 0.10), 2)

        energia = round(s["kwh"] * preco, 2)
        subtotal = round(energia + taxa_ociosa, 2)
        total = max(subtotal, 5.00)

        pago = (agora - fim).days > DIAS_COM_FATURA_ABERTA
        taxa = round(total * 0.032 + 0.39, 2) if pago else 0.0

        sessao_id = uuid.uuid4()
        fatura_id = uuid.uuid4()

        linhas_sessao.append(
            {
                "id": sessao_id,
                "code": f"SES-{primeiro_ses + indice}",
                "site_id": s["site_id"],
                "charge_point_id": s["charge_point_id"],
                "user_id": s.get("user_id"),
                "vehicle_id": s.get("vehicle_id"),
                "tariff_id": tarifa_id,
                "state": SessionState.BILLED,
                "auth_method": AuthMethod.APP if s.get("user_id") else AuthMethod.RFID,
                "stop_reason": StopReason.EV_DISCONNECTED,
                "authorized_at": inicio - timedelta(minutes=1),
                "started_at": inicio,
                "ended_at": fim,
                "charging_stopped_at": fim,
                "energy_kwh": s["kwh"],
                "green_energy_kwh": s["verde"],
                "duration_s": s["minutos"] * 60,
                "idle_minutes": ocioso,
                "peak_power_kw": s["pico"],
                "estimated_cost": total,
                "created_at": inicio,
                "updated_at": fim,
            }
        )

        linhas_fatura.append(
            {
                "id": fatura_id,
                "code": f"INV-{primeira_inv + indice}",
                "site_id": s["site_id"],
                "session_id": sessao_id,
                "user_id": s.get("user_id"),
                "status": InvoiceStatus.PAID if pago else InvoiceStatus.OPEN,
                "subtotal": subtotal,
                "total": total,
                "processing_fee": taxa,
                "net_amount": round(total - taxa, 2),
                "issued_on": local.date(),
                "paid_at": fim + timedelta(minutes=2) if pago else None,
                "tariff_snapshot": {"name": tarifa_nome, "type": "TIME_OF_USE"},
                "created_at": fim,
                "updated_at": fim,
            }
        )

        posicao = 0
        linhas_item.append(
            {
                "id": uuid.uuid4(),
                "invoice_id": fatura_id,
                "position": posicao,
                "kind": "energy",
                "description": f"Energia — {tarifa_nome}",
                "quantity": s["kwh"],
                "unit": "kWh",
                "unit_price": preco,
                "amount": energia,
            }
        )
        if taxa_ociosa > 0:
            posicao += 1
            linhas_item.append(
                {
                    "id": uuid.uuid4(),
                    "invoice_id": fatura_id,
                    "position": posicao,
                    "kind": "idle",
                    "description": "Taxa de ociosidade",
                    "quantity": ocioso,
                    "unit": "min",
                    "unit_price": 0.20 if na_ponta else 0.10,
                    "amount": taxa_ociosa,
                }
            )
        if total > subtotal:
            posicao += 1
            complemento = round(total - subtotal, 2)
            linhas_item.append(
                {
                    "id": uuid.uuid4(),
                    "invoice_id": fatura_id,
                    "position": posicao,
                    "kind": "min_charge",
                    "description": "Complemento até o valor mínimo",
                    "quantity": 1,
                    "unit": "un",
                    "unit_price": complemento,
                    "amount": complemento,
                }
            )

    # Em blocos: um INSERT com vinte mil linhas monta um comando que o driver
    # precisa manter inteiro em memoria, e o ganho sobre blocos de mil e' nulo.
    for tabela, linhas in (
        (ChargingSession, linhas_sessao),
        (Invoice, linhas_fatura),
        (InvoiceLine, linhas_item),
    ):
        for corte in range(0, len(linhas), 1000):
            await db.execute(insert(tabela), linhas[corte : corte + 1000])

    return len(linhas_sessao)


async def _montar_gamificacao(
    db, montados: list[dict], motoristas: list[User], agora, frota: Fleet
) -> None:
    """Campanha, contrato e o progresso que o historico ja produziu.

    Sem isto, reseedar deixa as telas novas vazias mesmo com dois anos de
    sessoes no banco - e a causa nao seria obvia: as tabelas existem, as rotas
    respondem, e o resultado e' uma lista vazia que parece defeito.

    O PROGRESSO PRECISA SER RECALCULADO AQUI porque o historico entra por
    `bulk_insert_mappings`, sem passar por `bill_session` - que e' quem chama
    `atualizar_progresso` em operacao. Como o progresso e' gravado em valor
    ABSOLUTO, recalculado por consulta, basta uma chamada por motorista: ela
    reconstroi a janela inteira. Fosse incremental, seria preciso reprocessar
    sessao por sessao.
    """
    from app.models.campaign import Campaign, Mission
    from app.models.platform import PlatformPlan, SiteSubscription
    from app.services import campaign_service, platform_service

    principal = montados[0]["site"]
    shopping = next((m["site"] for m in montados if m["site"].slug == "shopping-morumbi-g3"), None)

    # Campanha de REDE, com missoes: cashback na carteira. Quem paga e' a rede,
    # porque credito em carteira e' resgatavel em qualquer site.
    rede = Campaign(
        patrocinador="rede",
        nome="Setembro Verde",
        descricao="Recarregue com energia solar e ganhe de volta.",
        starts_at=agora - timedelta(days=45),
        ends_at=agora + timedelta(days=45),
        ativa=True,
        beneficio_tipo="cashback_fixo",
        beneficio_valor=8.00,
        teto_por_recompensa=8.00,
        orcamento_brl=2000.00,
    )
    db.add(rede)
    await db.flush()

    # Tres missoes em eixos diferentes: frequencia, comportamento e horario. Com
    # tres iguais o motorista cumpre as tres na mesma recarga, e a tela vira uma
    # so' barra repetida.
    for codigo, titulo, descricao, metrica, alvo, janela, ordem in [
        # Janela da CAMPANHA, e nao mensal: a campanha corre ha 45 dias, entao
        # esta missao ja tem historico suficiente para alguem ter cumprido. As
        # outras duas ficam em andamento de proposito - uma tela em que tudo
        # esta concluido nao mostra a barra de progresso funcionando, e uma em
        # que nada esta nunca chega na recompensa.
        (
            "oito-recargas",
            "Recarregue 8 vezes na campanha",
            "Oito recargas ate o fim da campanha.",
            "sessoes",
            8,
            "campanha",
            0,
        ),
        (
            "energia-solar",
            "50 kWh de energia solar",
            "Some 50 kWh vindos do sol carregando durante o dia.",
            "energia_verde_kwh",
            50,
            "mensal",
            1,
        ),
        (
            "fora-de-ponta",
            "3 recargas fora de ponta",
            "Carregue fora do horario de pico e ajude a rede.",
            "sessoes_fora_de_ponta",
            3,
            "semanal",
            2,
        ),
    ]:
        db.add(
            Mission(
                campaign_id=rede.id,
                codigo=codigo,
                titulo=titulo,
                descricao=descricao,
                metrica=metrica,
                alvo=alvo,
                janela=janela,
                ordem=ordem,
            )
        )

    # Campanha de SITE, sem missao: desconto direto na fatura. Quem paga e' o
    # estabelecimento, cedendo a propria margem naquela sessao.
    if shopping is not None:
        db.add(
            Campaign(
                patrocinador="site",
                site_id=shopping.id,
                nome="Terca no Shopping",
                descricao="Desconto para atrair movimento no dia mais fraco.",
                starts_at=agora - timedelta(days=20),
                ends_at=agora + timedelta(days=70),
                ativa=True,
                beneficio_tipo="desconto_pct",
                beneficio_valor=12.00,
                orcamento_brl=1500.00,
            )
        )

    # Campanha dirigida a FROTA: patrocinada pela rede (cashback sai da rede,
    # como sempre) e restrita aos motoristas da empresa. `fleet_id` e'
    # elegibilidade, nao patrocinio - a frota nao paga nada.
    #
    # Existe no seed porque ela e' a unica forma de ver a regra funcionando: o
    # motorista da frota enxerga quatro missoes, o de fora enxerga tres. Sem
    # isso, a clausula de elegibilidade seria codigo que ninguem exercita.
    corporativa = Campaign(
        patrocinador="rede",
        fleet_id=frota.id,
        nome="Frota Logistica SP",
        descricao="Acordo corporativo: cashback para os motoristas da empresa.",
        starts_at=agora - timedelta(days=30),
        ends_at=agora + timedelta(days=60),
        ativa=True,
        beneficio_tipo="cashback_pct",
        beneficio_valor=5.00,
        teto_por_recompensa=15.00,
        orcamento_brl=3000.00,
    )
    db.add(corporativa)
    await db.flush()
    db.add(
        Mission(
            campaign_id=corporativa.id,
            codigo="dez-recargas-corporativas",
            titulo="10 recargas no mes",
            descricao="Dez recargas da frota dentro do mes.",
            metrica="sessoes",
            alvo=10,
            janela="mensal",
            ordem=0,
        )
    )
    await db.flush()

    # Contrato da praca principal com a plataforma, com seis meses de vida - o
    # suficiente para a tela ter cobrancas e para o prazo minimo ainda correr.
    # `scalar_one()` e nao `scalar_one_or_none()`: o catalogo agora e' garantido
    # antes de qualquer coisa, e tolerar a ausencia aqui era como o site
    # principal ficava sem contrato sem ninguem notar.
    plano = (
        await db.execute(select(PlatformPlan).where(PlatformPlan.codigo == "essencial"))
    ).scalar_one()
    inicio = (agora - timedelta(days=180)).date()
    db.add(
        SiteSubscription(
            site_id=principal.id,
            plan_id=plano.id,
            estado="ativa",
            starts_on=inicio,
            minimo_ate=platform_service.somar_meses(inicio, plano.meses_minimos),
            renova_em=platform_service.mes_seguinte(agora.date()),
            renovacao_automatica=True,
            multa_percentual=30.00,
        )
    )
    await db.flush()

    # Progresso a partir do historico: uma chamada por motorista basta, porque o
    # valor gravado e' absoluto e a consulta cobre a janela inteira.
    for motorista in motoristas:
        ultima = (
            await db.execute(
                select(ChargingSession)
                .where(ChargingSession.user_id == motorista.id)
                .order_by(ChargingSession.started_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if ultima is not None:
            await campaign_service.atualizar_progresso(db, ultima, agora)


async def garantir_planos_da_plataforma(db: AsyncSession) -> int:
    """Publica os planos que faltam no catalogo da rede. Devolve quantos entraram.

    Fica FORA do corpo de `seed()`, e o motivo e' um defeito que chegou a
    producao. `seed()` desiste inteiro na primeira linha assim que enxerga um
    site - "ja existem dados" -, e os planos nasciam cento e vinte linhas la
    dentro. Num banco povoado antes de este catalogo existir, a tabela ficou
    vazia PARA SEMPRE: nenhuma rodada de seed voltaria a mexer nela, e nao ha
    rota que crie plano. A aba de Plano & Contrato dizia "escolha um plano
    abaixo" e abaixo nao havia nada.

    Catalogo de plano e' dado de REFERENCIA da rede, nao dado de demonstracao
    preso a um site - e por isso pode ser re-afirmado a cada rodada.

    Insere so o `codigo` que falta. NAO atualiza plano ja publicado: preco de
    plano vivo e' clausula de contrato em vigor (`SiteSubscription.plan_id`
    aponta para ele), e reescrever aqui mudaria por baixo o que o
    estabelecimento assinou.
    """
    publicados = set((await db.execute(select(PlatformPlan.codigo))).scalars().all())
    entraram = 0
    for codigo, nome, desc, mensal, ponto, inclusos, taxa, meses in PLANOS_DA_PLATAFORMA:
        if codigo in publicados:
            continue
        db.add(
            PlatformPlan(
                codigo=codigo,
                nome=nome,
                descricao=desc,
                preco_mensal_brl=mensal,
                preco_por_ponto_brl=ponto,
                pontos_inclusos=inclusos,
                fee_percent_transacao=taxa,
                meses_minimos=meses,
            )
        )
        entraram += 1
    if entraram:
        await db.flush()
    return entraram


async def seed() -> None:
    async with SessionLocal() as db:
        # Antes da desistencia, de proposito: o catalogo da rede precisa chegar
        # a banco que ja tem sites - foi exatamente o caso do staging.
        entraram = await garantir_planos_da_plataforma(db)
        if entraram:
            await db.commit()
            log.info("seed.planos_publicados", quantidade=entraram)

        if (await db.execute(select(Site).limit(1))).scalar_one_or_none() is not None:
            log.info("seed.skipped", reason="ja existem dados")
            return

        agora = datetime.now(UTC)
        montados = [await _montar_site(db, spec) for spec in SITES]
        principal = montados[0]
        site = principal["site"]
        off_peak = principal["off_peak"]

        # ---- usuarios ----
        cfg = get_settings()
        sorteadas: dict[str, str] = {}
        senha_admin = _senha(cfg.seed_admin_password, "admin@chargegrid.com.br", sorteadas)
        senha_operador = _senha(cfg.seed_operator_password, "operador@chargegrid.com.br", sorteadas)
        senha_motorista = _senha(cfg.seed_driver_password, "motoristas", sorteadas)

        db.add(
            User(
                email="admin@chargegrid.com.br",
                full_name="Administrador ChargeGrid",
                hashed_password=hash_password(senha_admin),
                role=UserRole.ADMIN,
                site_id=site.id,
            )
        )
        # O operador continua preso a um site. E' o que da o que demonstrar ao
        # seletor de praca: o admin ve a rede inteira e troca de local, o
        # operador nem recebe o seletor, porque `deps` ignora o site_id que ele
        # pedir e devolve sempre o dele.
        db.add(
            User(
                email="operador@chargegrid.com.br",
                full_name="Operador do Site",
                hashed_password=hash_password(senha_operador),
                role=UserRole.OPERATOR,
                site_id=site.id,
            )
        )

        frota = Fleet(
            name=FROTA["nome"],
            document=FROTA["documento"],
            billing_email=FROTA["email_de_cobranca"],
        )
        db.add(frota)
        await db.flush()

        motoristas: list[User] = []
        veiculos: dict[uuid.UUID, Vehicle] = {}
        for index, (email, full_name, model, _label, battery, max_ac) in enumerate(DRIVERS):
            driver = User(
                email=email,
                full_name=full_name,
                hashed_password=hash_password(senha_motorista),
                role=UserRole.DRIVER,
                wallet_balance=100.0,
            )
            if email in MOTORISTAS_DA_FROTA:
                driver.fleet_id = frota.id
                driver.fleet_manager = email == GESTOR_DA_FROTA
            db.add(driver)
            await db.flush()
            # O saldo inicial precisa da propria linha no razao. Creditar
            # `wallet_balance` direto deixaria `SUM(wallet_entries.amount)`
            # diferente do saldo no primeiro motorista criado - e a invariante
            # que o razao existe para sustentar nasceria falsa no seed.
            db.add(
                WalletEntry(
                    user_id=driver.id,
                    amount=100.0,
                    balance_after=100.0,
                    idempotency_key=f"seed:abertura:{driver.id}",
                    provider="seed",
                    origem="ajuste",
                    motivo="Saldo de abertura do seed",
                )
            )
            veiculo = Vehicle(
                user_id=driver.id,
                model=model,
                battery_kwh=battery,
                max_ac_kw=max_ac,
                # Sem centro de custo o relatorio da frota soma tudo num balde
                # so' - que e' o relatorio que a empresa NAO quer.
                cost_center=MOTORISTAS_DA_FROTA.get(email),
            )
            db.add(veiculo)
            await db.flush()
            motoristas.append(driver)
            veiculos[driver.id] = veiculo
            # Dois cartoes RFID por ponto e o limite pratico do HCA G2 (10 no total).
            if index < 2:
                db.add(
                    RfidCard(
                        uid=f"04A1B2C3D4E{index:03d}"[:14],
                        label=f"Cartao {full_name.split()[0]}",
                        user_id=driver.id,
                        site_id=site.id,
                        tariff_id=off_peak.id,
                    )
                )

        # ---- planos de recarga ----
        for codigo, nome, descricao, preco, desconto, kwh, isenta in PLANOS:
            db.add(
                DriverPlan(
                    codigo=codigo,
                    nome=nome,
                    descricao=descricao,
                    preco_mensal_brl=preco,
                    desconto_pct=desconto,
                    kwh_inclusos=kwh,
                    isenta_taxa_de_conexao=isenta,
                )
            )

        # ---- historico de recargas ----
        rng = random.Random(SEMENTE_DO_HISTORICO)
        sessoes: list[dict] = []
        for montado in montados:
            sessoes.extend(_sessoes_do_site(rng, montado, agora))
        # Ordem cronologica da REDE, nao de cada site: e' o que impede a mesma
        # pessoa de aparecer carregando em dois lugares ao mesmo tempo.
        sessoes.sort(key=lambda s: s["inicio"])
        _atribui_motoristas(rng, sessoes, motoristas, veiculos)
        total_sessoes = await _gravar_historico(db, sessoes, agora)

        # ---- campanhas, contrato e progresso ----
        #
        # Depois do historico, e nao antes: o progresso das missoes e' calculado
        # a partir das sessoes ja gravadas.
        await _montar_gamificacao(db, montados, motoristas, agora, frota)

        # ---- leitura inicial do medidor: sem ela o orcamento so ve a rede ----
        for montado in montados:
            for minutes_ago in (10, 5, 0):
                db.add(
                    SiteMeterReading(
                        site_id=montado["site"].id,
                        recorded_at=agora - timedelta(minutes=minutes_ago),
                        grid_import_kw=32.0,
                        pv_kw=38.4,
                        battery_kw=12.0,
                        battery_soc=68.0,
                        building_load_kw=18.5,
                        ev_load_kw=0.0,
                    )
                )

        await db.commit()
        log.info(
            "seed.done",
            sites=len(montados),
            charge_points=sum(len(m["pontos"]) for m in montados),
            sessoes=total_sessoes,
        )

        # Unica chance de ver as senhas sorteadas: elas nao ficam gravadas em
        # lugar nenhum em texto claro. Quem quiser senhas estaveis define
        # SEED_ADMIN_PASSWORD, SEED_OPERATOR_PASSWORD e SEED_DRIVER_PASSWORD.
        if sorteadas:
            log.warning("seed.senhas_sorteadas", contas=list(sorteadas))
            print()
            print("  Senhas sorteadas para este banco (anote agora):")
            for rotulo, senha in sorteadas.items():
                print(f"    {rotulo:32} {senha}")
            print("    Defina SEED_*_PASSWORD no .env para escolher as suas.")
            print()


async def create_schema() -> None:
    """Constroi o schema pelas migrations, nunca por Base.metadata.create_all.

    O create_all monta o schema a partir dos MODELOS, e nem tudo mora neles: os
    indices BRIN das tabelas de serie temporal, os indices compostos e os
    indices unicos parciais que impedem duas sessoes ativas no mesmo ponto
    existem so nas migrations. Um banco criado por create_all ficava com oito
    indices a menos que producao - entre eles a unica garantia de unicidade -,
    e `alembic check` nao acusava, porque ele compara modelos com migrations e
    esses indices nao estao nos modelos.

    O docker-compose ja rodava `alembic upgrade head` antes deste script; quem
    executasse `python -m app.seed` direto e' que acabava com o schema torto.
    Agora as duas rotas produzem o mesmo banco.
    """
    from alembic.config import Config

    from alembic import command

    raiz = Path(__file__).resolve().parent.parent
    cfg = Config(str(raiz / "alembic.ini"))
    cfg.set_main_option("script_location", str(raiz / "alembic"))
    # Numa thread propria: o env.py chama asyncio.run(), que recusa rodar dentro
    # de um laco de eventos ja em execucao - e este script abriu o dele.
    await asyncio.to_thread(command.upgrade, cfg, "head")


async def main() -> None:
    configure_logging()
    await create_schema()
    await seed()
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
