"""Teste de fumaca ponta a ponta contra uma API ja no ar.

Percorre o produto inteiro: login, orcamento de potencia, ciclo da sessao,
faturamento, cobranca, carteira, missoes, campanhas, assinatura, contrato da
plataforma e previsao. Serve para validar um ambiente recem-subido.

    python -m scripts.smoke_test            # usa http://127.0.0.1:8000
    python -m scripts.smoke_test http://host:porta

E' a unica camada que exercita HTTP, servico, banco e worker juntos, com o seed
real por baixo - e por isso ela ve coisas que os testes de unidade nao veem:
recompensa concedida sem o dinheiro correspondente na carteira, multa que o
servidor calcula de um jeito e o painel de outro, rota de dinheiro aberta para
quem nao devia.

TODA SECAO E' RE-EXECUTAVEL, e isso e' requisito, nao cortesia: um smoke que so'
passa na primeira rodada falha na segunda e ensina todo mundo a ignorar falha.
O que cria, encerra; o que assina, cancela; o que gasta, recarrega antes.

CUIDADO ao usar este arquivo para teste de MUTACAO. Ele escreve num banco de
verdade: uma guarda revertida pode deixar rastro inconsistente que sobrevive a
reversao da mutacao. Ja aconteceu - suprimir a gravacao do debito da carteira
deixou uma fatura paga sem linha no razao, e a divergencia so' apareceu na
rodada seguinte, parecendo defeito do produto. Mutacao aqui pede banco
descartavel.
"""

from __future__ import annotations

import os
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta

import httpx

from app.core.config import get_settings

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
API = f"{BASE}/api/v1"
# Credenciais da configuracao, nunca do codigo: sao as mesmas que o seed usou.
# Le pelo get_settings() e nao por os.environ para enxergar tambem o .env, que
# e' onde elas de fato moram. Sem SEED_*_PASSWORD definido, o seed sorteou as
# senhas - defina as variaveis com os valores que ele imprimiu.
_cfg = get_settings()
_OPERADOR_SENHA = _cfg.seed_operator_password or os.environ.get("SEED_OPERATOR_PASSWORD", "")
_MOTORISTA_SENHA = _cfg.seed_driver_password or os.environ.get("SEED_DRIVER_PASSWORD", "")
_ADMIN_SENHA = _cfg.seed_admin_password or os.environ.get("SEED_ADMIN_PASSWORD", "")
OPERADOR = ("operador@chargegrid.com.br", _OPERADOR_SENHA)
MOTORISTA = ("joao.silva@email.com", _MOTORISTA_SENHA)
# Opcional: so' a baixa manual da cobranca da plataforma precisa de admin. Sem
# ela o smoke roda inteiro e declara esse trecho como pulado, em vez de falhar
# por configuracao - que nao e' o que um teste de fumaca deve reportar.
ADMIN = ("admin@chargegrid.com.br", _ADMIN_SENHA)

def _exigir_credenciais() -> None:
    """Checagem na execucao, nao na importacao: o pytest coleta este arquivo
    (o nome casa com *_test.py) e um SystemExit aqui derrubaria a coleta."""
    if not _OPERADOR_SENHA or not _MOTORISTA_SENHA:
        raise SystemExit(
            "Defina SEED_OPERATOR_PASSWORD e SEED_DRIVER_PASSWORD (as mesmas que o "
            "seed usou) antes de rodar o teste de fumaca."
        )

ATIVOS = {"authorizing", "queued", "starting", "charging", "suspended", "finishing"}

falhas: list[str] = []
passos = 0


def check(nome: str, condicao: bool, detalhe: str = "") -> bool:
    global passos
    passos += 1
    print(f"{'ok   ' if condicao else 'FALHA'} {nome}" + (f" -> {detalhe}" if detalhe else ""))
    if not condicao:
        falhas.append(nome)
    return condicao


def secao(titulo: str) -> None:
    print(f"\n--- {titulo} ---")


def login(client: httpx.Client, email: str, senha: str) -> str:
    r = client.post(f"{API}/auth/login", json={"email": email, "password": senha})
    r.raise_for_status()
    return r.json()["access_token"]


def limpar_sessoes_ativas(client: httpx.Client, op: dict) -> int:
    """Encerra o que ficou aberto de execucoes anteriores.

    Uma sessao ativa bloqueia o ponto, entao sem esta limpeza a segunda rodada
    do smoke falha em cascata com 409 - e a falha parece do codigo, nao do teste.
    """
    encerradas = 0
    for _ in range(3):
        pendentes = [
            s
            for s in client.get(f"{API}/sessions", params={"limit": 50}, headers=op).json()["items"]
            if s["state"] in ATIVOS
        ]
        if not pendentes:
            break
        for s in pendentes:
            client.post(
                f"{API}/sessions/{s['id']}/stop",
                json={"reason": "remote", "auto_bill": False},
                headers=op,
            )
            encerradas += 1
    return encerradas


def resumo() -> int:
    print("\n" + "=" * 52)
    if falhas:
        print(f"{len(falhas)} FALHA(S) de {passos}: " + "; ".join(falhas))
        return 1
    print(f"Todos os {passos} cenarios passaram.")
    return 0


def autenticacao(client: httpx.Client) -> dict:
    secao("Autenticacao")
    r = client.get(f"{BASE}/health")
    check("health responde", r.status_code == 200 and r.json()["database"] == "up", r.text[:80])

    r = client.post(f"{API}/auth/login", json={"email": OPERADOR[0], "password": "errada"})
    check("senha errada rejeitada", r.status_code == 401)

    op = {"Authorization": f"Bearer {login(client, *OPERADOR)}"}
    r = client.get(f"{API}/auth/me", headers=op)
    check("login do operador", r.json().get("role") == "operator", r.json().get("email"))

    r = client.get(f"{API}/power/overview")
    check("rota protegida exige token", r.status_code == 401)

    drv = {"Authorization": f"Bearer {login(client, *MOTORISTA)}"}
    r = client.get(f"{API}/power/overview", headers=drv)
    check("motorista bloqueado no painel", r.status_code == 403, f"HTTP {r.status_code}")
    return op, drv


def potencia(client: httpx.Client, op: dict) -> dict:
    secao("Gerenciamento de Potencia")
    ov = client.get(f"{API}/power/overview", headers=op).json()
    b = ov["budget"]
    esperado = (
        b["grid_limit_kw"]
        + b["pv_kw"]
        + b["battery_kw"]
        - max(b["reserved_kw"], b["building_load_kw"])
    )
    check(
        "orcamento calculado", abs(b["available_kw"] - esperado) < 0.01, f"{b['available_kw']} kW"
    )
    check("4 pontos de recarga", ov["total_count"] == 4)
    check("pontos online", all(c["status"] != "offline" for c in ov["charge_points"]))

    cp = next(c for c in ov["charge_points"] if c["code"] == "CP-01")
    r = client.post(
        f"{API}/power/charge-points/{cp['id']}/limit", json={"limit_kw": 15}, headers=op
    )
    check(
        "limite gravado no ponto",
        r.status_code == 200 and float(r.json()["limit_kw"]) == 15.0,
        f"{r.json().get('limit_kw')} kW",
    )

    r = client.post(
        f"{API}/power/charge-points/{cp['id']}/limit", json={"limit_kw": 999}, headers=op
    )
    check("limite acima do maximo rejeitado", r.status_code == 422, f"HTTP {r.status_code}")

    plano = client.get(f"{API}/power/plan", headers=op).json()
    total = plano["total_granted_kw"]
    check(
        "plano nao estoura o orcamento",
        total <= plano["budget"]["available_kw"] + 0.01,
        f"{total} kW de {plano['budget']['available_kw']} kW",
    )
    return cp


def sessao(client: httpx.Client, op: dict, cp: dict) -> dict | None:
    secao("Ciclo da Sessao")
    r = client.post(
        f"{API}/sessions", json={"charge_point_id": cp["id"], "auth_method": "operator"}, headers=op
    )
    if not check("sessao iniciada", r.status_code == 201, f"HTTP {r.status_code} {r.text[:90]}"):
        return None
    ses = r.json()
    check("estado inicial CHARGING", ses["state"] == "charging", ses["state"])
    check(
        "eventos registrados",
        len(ses["events"]) >= 2,
        " / ".join(e["event_type"] for e in ses["events"]),
    )

    r = client.post(
        f"{API}/sessions", json={"charge_point_id": cp["id"], "auth_method": "operator"}, headers=op
    )
    check("segunda sessao no mesmo ponto barrada", r.status_code == 409, f"HTTP {r.status_code}")

    print("      aguardando o simulador entregar energia (18s)...")
    time.sleep(18)

    ses = client.get(f"{API}/sessions/{ses['id']}", headers=op).json()
    check("energia acumulada", float(ses["energy_kwh"]) > 0, f"{float(ses['energy_kwh']):.3f} kWh")
    pico = float(ses["peak_power_kw"])
    check("potencia respeitou o limite aplicado", pico <= 15.01, f"pico {pico} kW de 15 kW")
    # Regressao: apos um congestionamento o ponto ficava com o corte do reg
    # 10000 ativo e entregava so a potencia minima pela sessao inteira.
    check("corte anterior nao segurou a potencia", pico > 5.0, f"pico {pico} kW (minimo e 4,2)")

    prev = client.get(f"{API}/sessions/{ses['id']}/preview", headers=op).json()
    check(
        "previa de custo calculada",
        prev["total"] > 0,
        f"R$ {prev['total']:.2f} em {len(prev['lines'])} linha(s)",
    )

    tel = client.get(f"{API}/sessions/{ses['id']}/telemetry", headers=op).json()
    check("serie de telemetria disponivel", len(tel) > 0, f"{len(tel)} amostras")
    return ses


def faturamento(client: httpx.Client, op: dict, ses: dict) -> dict | None:
    secao("Tarifacao e Pagamento")
    r = client.post(
        f"{API}/sessions/{ses['id']}/stop", json={"reason": "remote", "auto_bill": True}, headers=op
    )
    check("sessao encerrada", r.status_code == 200, f"HTTP {r.status_code}")
    check("estado final BILLED", r.json()["state"] == "billed", r.json()["state"])

    r = client.post(f"{API}/sessions/{ses['id']}/stop", json={"reason": "remote"}, headers=op)
    check("encerrar duas vezes barrado", r.status_code == 409, f"HTTP {r.status_code}")

    inv = client.get(f"{API}/invoices", params={"limit": 5}, headers=op).json()["items"]
    if not check("fatura emitida", len(inv) >= 1, f"{len(inv)} fatura(s)"):
        return None
    fatura = inv[0]
    check(
        "fatura em aberto com valor",
        fatura["status"] == "open" and fatura["total"] > 0,
        f"{fatura['code']} R$ {fatura['total']:.2f} ({fatura['status']})",
    )
    check(
        "fatura detalhada por item",
        len(fatura["lines"]) >= 1,
        " / ".join(f"{ln['kind']}={ln['amount']:.2f}" for ln in fatura["lines"]),
    )
    return fatura


def cobranca(client: httpx.Client, op: dict, fatura: dict) -> None:
    chave = f"smoke-{fatura['id']}"
    r = client.post(
        f"{API}/invoices/{fatura['id']}/charge",
        json={"method": "pix", "idempotency_key": chave},
        headers=op,
    )
    if not check(
        "cobranca Pix criada", r.status_code == 201, f"HTTP {r.status_code} {r.text[:90]}"
    ):
        return
    pag = r.json()
    check("Pix devolve copia-e-cola", bool(pag.get("qr_code")), (pag.get("qr_code") or "")[:38])

    r2 = client.post(
        f"{API}/invoices/{fatura['id']}/charge",
        json={"method": "pix", "idempotency_key": chave},
        headers=op,
    )
    check("idempotencia evita cobranca dupla", r2.json().get("id") == pag["id"], "mesmo pagamento")

    rev = client.get(f"{API}/revenue/summary", params={"days": 1}, headers=op).json()
    check(
        "resumo de receita responde",
        "gross" in rev,
        f"bruto R$ {rev.get('gross', 0):.2f} / {rev.get('open_invoices')} em aberto",
    )

    kpis = client.get(f"{API}/sessions/kpis", headers=op).json()
    check(
        "KPIs consolidados",
        kpis["today"] >= 1,
        f"{kpis['today']} sessao(oes), {kpis['energy_kwh']:.2f} kWh hoje",
    )


def controle_de_demanda(client: httpx.Client, op: dict, cp: dict) -> None:
    """Congestiona o site de proposito e verifica corte e retomada.

    Regressao de dois bugs: o ponto suspenso nunca era liberado (o deadband
    pulava a escrita quando o teto calculado era igual ao ja gravado) e uma
    sessao sem potencia ficava presa em STARTING, bloqueando o eletroposto.
    """
    secao("Controle de Demanda sob congestionamento")
    original = client.get(f"{API}/power/budget", headers=op).json()
    ajustes = client.get(f"{API}/power/overview", headers=op).json()["settings"]

    try:
        # Apertar so' a rede nao basta: o orcamento tambem soma solar e bateria,
        # e num banco recem-semeado essas duas sozinhas passam de 50 kW. Antes
        # este teste so' passava quando a leitura do medidor ja tinha vencido -
        # ai as duas saiam da conta por acaso, e o resultado dependia da idade
        # do banco. Agora o cenario desliga todas as fontes de proposito.
        #
        # 1 kW fica abaixo do minimo de qualquer ponto (1,4 kW no monofasico,
        # 4,2 kW no trifasico), entao nenhum deles pode ser servido.
        client.patch(
            f"{API}/power/budget",
            json={
                "grid_limit_kw": 1,
                "reserved_kw": 0,
                "allow_pv_kw": False,
                "allow_battery_kw": False,
            },
            headers=op,
        )
        orcado = client.get(f"{API}/power/budget", headers=op).json()
        check(
            "site fica sem potencia para qualquer ponto",
            orcado["available_kw"] < 1.4,
            f"{orcado['available_kw']} kW disponiveis",
        )
        plano = client.get(f"{API}/power/plan", headers=op).json()
        check(
            "orcamento apertado suspende em vez de fatiar",
            all(a["granted_kw"] == 0 for a in plano["allocations"]),
            f"{sum(1 for a in plano['allocations'] if a['suspended'])} suspenso(s)",
        )

        r = client.post(
            f"{API}/sessions",
            json={
                "charge_point_id": cp["id"],
                "auth_method": "operator",
                "queue_if_unavailable": False,
            },
            headers=op,
        )
        check("sem fila, a sessao e recusada", r.status_code == 422, f"HTTP {r.status_code}")
        check(
            "codigo de erro identifica a causa",
            r.json().get("code") == "insufficient_power",
            r.json().get("detail", "")[:60],
        )

        ativas = client.get(
            f"{API}/sessions", params={"state": "starting", "limit": 5}, headers=op
        ).json()
        check(
            "nenhuma sessao presa em STARTING", ativas["total"] == 0, f"{ativas['total']} presa(s)"
        )

        # A recusa nao pode ter deixado o eletroposto travado.
        r = client.post(
            f"{API}/sessions",
            json={
                "charge_point_id": cp["id"],
                "auth_method": "operator",
                "queue_if_unavailable": False,
            },
            headers=op,
        )
        check(
            "ponto nao ficou bloqueado apos a recusa", r.status_code == 422, f"HTTP {r.status_code}"
        )

        # Sem o opt-out, o padrao e esperar na fila.
        r = client.post(
            f"{API}/sessions",
            json={"charge_point_id": cp["id"], "auth_method": "operator"},
            headers=op,
        )
        check("por padrao entra na fila", r.status_code == 201, f"HTTP {r.status_code}")
        if r.status_code == 201:
            fila = r.json()
            detalhe = client.get(f"{API}/sessions/{fila['id']}", headers=op).json()
            check(
                "estado QUEUED com posicao",
                detalhe["state"] == "queued" and detalhe["queue_position"] == 1,
                f"{detalhe['state']} posicao {detalhe.get('queue_position')}",
            )
            kpis = client.get(f"{API}/sessions/kpis", headers=op).json()
            check("KPI da fila reflete a espera", kpis["queued"] >= 1, f"{kpis['queued']} na fila")
    finally:
        # O cenario acima deixa uma sessao na fila de proposito: encerra para a
        # proxima execucao encontrar o ponto livre.
        limpar_sessoes_ativas(client, op)
        client.patch(
            f"{API}/power/budget",
            json={
                "grid_limit_kw": original["grid_limit_kw"],
                "reserved_kw": original["reserved_kw"],
                "allow_pv_kw": ajustes["allow_pv_kw"],
                "allow_battery_kw": ajustes["allow_battery_kw"],
            },
            headers=op,
        )

    plano = client.get(f"{API}/power/plan", headers=op).json()
    check(
        "orcamento restaurado volta a conceder",
        plano["budget"]["available_kw"] > 5,
        f"{plano['budget']['available_kw']} kW",
    )

    # O rebalanceador roda a cada 15s e promove quem esta esperando.
    print("      aguardando o rebalanceador esvaziar a fila (20s)...")
    time.sleep(20)
    kpis = client.get(f"{API}/sessions/kpis", headers=op).json()
    check(
        "fila esvazia sozinha quando abre folga", kpis["queued"] == 0, f"{kpis['queued']} na fila"
    )


def corte_manual(client: httpx.Client, op: dict) -> None:
    """O corte de emergencia do operador precisa sobreviver a automacao.

    Regressao: o corte vivia so no campo status, entao o poller (5s) e o rateio
    (15s) o desfaziam - o botao do painel parecia funcionar e revertia sozinho.
    """
    secao("Corte manual do operador")
    pontos = client.get(f"{API}/power/charge-points", headers=op).json()
    cp = next(p for p in pontos if not p["operator_throttled"])

    r = client.post(
        f"{API}/power/charge-points/{cp['id']}/throttle", params={"enabled": True}, headers=op
    )
    check(
        "corte aplicado",
        r.status_code == 200 and r.json()["operator_throttled"],
        f"{cp['code']} -> {r.json().get('status')}",
    )

    print("      aguardando poller e rebalanceador tentarem reverter (20s)...")
    time.sleep(20)

    atual = next(
        p
        for p in client.get(f"{API}/power/charge-points", headers=op).json()
        if p["id"] == cp["id"]
    )
    check(
        "corte sobrevive a automacao",
        atual["operator_throttled"] and atual["status"] == "suspended",
        f"status={atual['status']} cortado={atual['operator_throttled']}",
    )

    plano = client.get(f"{API}/power/plan", headers=op).json()
    alvo = next(a for a in plano["allocations"] if a["code"] == cp["code"])
    check(
        "ponto cortado nao reserva potencia",
        alvo["granted_kw"] == 0,
        f"{alvo['granted_kw']} kW — {alvo['reason']}",
    )

    r = client.post(
        f"{API}/power/charge-points/{cp['id']}/throttle", params={"enabled": False}, headers=op
    )
    check(
        "operador consegue liberar",
        r.status_code == 200 and not r.json()["operator_throttled"],
        f"status={r.json().get('status')}",
    )


def agendamento(client: httpx.Client, op: dict) -> None:
    """O laco completo da reserva: segura potencia, consome, devolve.

    Regressao: Reservation.reserved_kw era gravado e nunca lido pelo rateio -
    agendar nao garantia capacidade nenhuma no horario marcado.
    """
    secao("Agendamento e orcamento")
    motorista = {"Authorization": f"Bearer {login(client, *MOTORISTA)}"}
    agora = datetime.now(UTC)

    pontos = client.get(f"{API}/power/charge-points", headers=op).json()
    cp = next(p for p in pontos if p["status"] == "available" and not p["operator_throttled"])
    antes = client.get(f"{API}/power/budget", headers=op).json()

    # Limpa reserva em aberto de uma execucao anterior.
    #
    # O cenario termina consumindo a reserva, entao numa execucao completa nao
    # sobra nada. Mas se ela for interrompida no meio - a API reiniciada, por
    # exemplo -, a reserva fica CONFIRMED e a janela de 30 minutos bloqueia
    # todas as execucoes seguintes por sobreposicao. Cancelar antes torna o
    # cenario idempotente de verdade, e nao so quando tudo da certo.
    for antiga in client.get(f"{API}/app/reservations", headers=motorista).json():
        if antiga["status"] in ("pending", "confirmed"):
            client.delete(f"{API}/app/reservations/{antiga['id']}", headers=motorista)

    r = client.post(
        f"{API}/app/reservations",
        json={
            "charge_point_id": cp["id"],
            "starts_at": (agora - timedelta(minutes=2)).isoformat(),
            "ends_at": (agora + timedelta(minutes=30)).isoformat(),
        },
        headers=motorista,
    )
    if not check("agendamento criado", r.status_code == 201, f"HTTP {r.status_code}"):
        return
    reserva = r.json()

    durante = client.get(f"{API}/power/budget", headers=op).json()
    check(
        "agendamento segura potencia",
        durante["booked_kw"] >= float(reserva["reserved_kw"]),
        f"{antes['available_kw']} -> {durante['available_kw']} kW",
    )

    sessao_r = client.post(
        f"{API}/sessions",
        json={"charge_point_id": cp["id"], "auth_method": "operator"},
        headers=op,
    )
    check("sessao inicia no ponto reservado", sessao_r.status_code == 201)

    depois = client.get(f"{API}/power/budget", headers=op).json()
    check(
        "consumir a reserva devolve a potencia",
        depois["booked_kw"] < durante["booked_kw"],
        f"{durante['booked_kw']} -> {depois['booked_kw']} kW (sem contagem dupla)",
    )

    agendamentos = client.get(f"{API}/app/reservations", headers=motorista).json()
    atual = next(a for a in agendamentos if a["id"] == reserva["id"])
    check("reserva marcada como consumida", atual["status"] == "consumed", atual["status"])

    if sessao_r.status_code == 201:
        client.post(
            f"{API}/sessions/{sessao_r.json()['id']}/stop",
            json={"reason": "remote"},
            headers=op,
        )


def coerencia_da_tarifa(client: httpx.Client, op: dict) -> None:
    """O tipo declarado precisa restringir os precos que a tarifa cobra."""
    secao("Coerencia da tarifa")
    r = client.post(
        f"{API}/tariffs",
        json={
            "name": "Smoke Incoerente",
            "type": "per_time",
            "price_per_min": 0.35,
            "price_per_kwh": 1.40,
        },
        headers=op,
    )
    check("tipo incoerente e recusado", r.status_code == 422, f"HTTP {r.status_code}")
    check(
        "erro identifica a causa",
        r.json().get("code") == "tariff_inconsistent",
        r.json().get("detail", "")[:56],
    )

    r = client.post(
        f"{API}/tariffs",
        json={
            "name": "Smoke Coerente",
            "type": "per_time",
            "price_per_min": 0.35,
            "price_per_kwh": 0,
        },
        headers=op,
    )
    if not check("tipo coerente e aceito", r.status_code == 201, f"HTTP {r.status_code}"):
        return
    nova = r.json()["id"]

    r = client.patch(f"{API}/tariffs/{nova}", json={"price_per_kwh": 1.40}, headers=op)
    check("PATCH parcial tambem e validado", r.status_code == 422, f"HTTP {r.status_code}")

    r = client.delete(f"{API}/tariffs/{nova}", headers=op)
    check("tarifa sem uso pode ser excluida", r.status_code == 204, f"HTTP {r.status_code}")

    # Precisa ser uma tarifa que REALMENTE tem sessao: escolher "qualquer ativa"
    # pegava uma sem historico, o delete passava, e o teste apagava dado do seed.
    sessoes = client.get(f"{API}/sessions", params={"limit": 50}, headers=op).json()["items"]
    com_historico = next((s["tariff_id"] for s in sessoes if s["tariff_id"]), None)
    if com_historico is None:
        check("tarifa com historico e protegida", True, "nenhuma sessao faturada ainda")
        return
    r = client.delete(f"{API}/tariffs/{com_historico}", headers=op)
    check("tarifa com historico e protegida", r.status_code == 409, f"HTTP {r.status_code}")




# ---------------------------------------------------------------------------
# Fases 2 a 5: carteira, gamificacao, campanhas, assinatura e contrato.
#
# Cobrem o que os testes da API nao alcancam: a travessia HTTP -> servico ->
# banco -> worker, com o seed real por baixo. Sao tambem as features mais novas,
# e ate aqui as unicas sem nenhuma prova ponta a ponta.
#
# Toda secao aqui e' RE-EXECUTAVEL. O que cria, apaga; o que assina, cancela.
# Um smoke que so' passa na primeira rodada e' pior que nenhum: ele falha na
# segunda e todo mundo aprende a ignorar a falha.
# ---------------------------------------------------------------------------


def _fecha(extrato: dict) -> bool:
    """A invariante da carteira: os movimentos somam o saldo."""
    return abs(round(sum(m["valor"] for m in extrato["movimentos"]), 2) - extrato["saldo"]) < 0.01


def carteira(client: httpx.Client, drv: dict) -> None:
    """O razao fecha com o saldo, pela API.

    `SUM(wallet_entries.amount) = users.wallet_balance` e' conferida no banco
    pelos testes de unidade; aqui ela e' conferida onde o motorista a ve - o
    extrato contra o perfil.
    """
    secao("Carteira e razao")

    extrato = client.get(f"{API}/app/wallet/statement", headers=drv).json()
    perfil = client.get(f"{API}/auth/me", headers=drv).json()
    check(
        "extrato bate com o saldo do perfil",
        abs(extrato["saldo"] - perfil["wallet_balance"]) < 0.01,
        f"extrato R$ {extrato['saldo']:.2f} / perfil R$ {perfil['wallet_balance']:.2f}",
    )
    check(
        "movimentos somam o saldo",
        _fecha(extrato),
        f"{len(extrato['movimentos'])} movimento(s)",
    )

    # `balance_after` tem de ser o acumulado ate aquela linha. Uma coluna de
    # saldo que nao acompanha os valores e' pior que coluna nenhuma.
    corrido, coerente = 0.0, True
    for m in reversed(extrato["movimentos"]):
        corrido = round(corrido + m["valor"], 2)
        if abs(corrido - m["saldo_apos"]) > 0.01:
            coerente = False
            break
    check("saldo_apos acompanha a soma corrida", coerente, f"{len(extrato['movimentos'])} linha(s)")

    creditos_antes = len([m for m in extrato["movimentos"] if m["origem"] == "topup"])
    chave = f"smoke-{uuid.uuid4().hex[:12]}"
    antes = extrato["saldo"]

    r = client.post(
        f"{API}/app/wallet/topup", json={"amount": "1.00", "idempotency_key": chave}, headers=drv
    )
    check(
        "credito entra na carteira",
        r.status_code == 200 and abs(r.json()["wallet_balance"] - (antes + 1)) < 0.01,
        f"R$ {r.json().get('wallet_balance')}",
    )

    r = client.post(
        f"{API}/app/wallet/topup", json={"amount": "1.00", "idempotency_key": chave}, headers=drv
    )
    check(
        "mesma chave nao credita de novo",
        r.status_code == 200 and abs(r.json()["wallet_balance"] - (antes + 1)) < 0.01,
        f"R$ {r.json().get('wallet_balance')}",
    )

    depois = client.get(f"{API}/app/wallet/statement", headers=drv).json()
    creditos = len([m for m in depois["movimentos"] if m["origem"] == "topup"])
    check(
        "o credito virou UMA linha no razao",
        creditos == creditos_antes + 1,
        f"{creditos_antes} -> {creditos}",
    )
    check("o razao fecha depois do credito", _fecha(depois), f"R$ {depois['saldo']:.2f}")


def gamificacao(client: httpx.Client, drv: dict) -> None:
    """Missao concluida, recompensa concedida, dinheiro na carteira.

    A travessia que nenhum teste de unidade percorre inteira: o progresso e'
    gravado no commit da fatura, a concessao roda no worker, o credito cai na
    carteira e o extrato mostra. Se um elo quebrar, o motorista le "missao
    concluida" e nao encontra o dinheiro.
    """
    secao("Missoes e recompensas")

    missoes = client.get(f"{API}/app/missions", headers=drv).json()
    ha_missoes = isinstance(missoes, list) and len(missoes) > 0
    if not check("missoes listadas", ha_missoes, str(len(missoes))):
        return

    campos = {"progresso", "concluida", "alvo", "campanha"}
    check("missao traz progresso e alvo", campos <= set(missoes[0]), ", ".join(sorted(campos)))
    check("progresso nunca e negativo", all(float(m["progresso"]) >= 0 for m in missoes))
    concluidas = [m for m in missoes if m["concluida"]]
    check(
        "missao concluida tem instante",
        all(m.get("concluida_em") for m in concluidas),
        f"{len(concluidas)} concluida(s)",
    )

    recompensas = client.get(f"{API}/app/rewards", headers=drv).json()
    creditadas = [r for r in recompensas if r["estado"] == "creditada"]
    if not check(
        "recompensa concedida e creditada",
        len(creditadas) > 0,
        f"{len(creditadas)} de {len(recompensas)}",
    ):
        return

    # O elo que so' aparece aqui: recompensa creditada PRECISA ter dinheiro
    # correspondente no razao. Sem esta checagem, `estado='creditada'` podia ser
    # uma etiqueta sem lastro nenhum.
    extrato = client.get(f"{API}/app/wallet/statement", headers=drv).json()
    cashbacks = [m for m in extrato["movimentos"] if m["origem"] == "cashback"]
    check(
        "toda recompensa creditada tem credito no razao",
        len(cashbacks) >= len(creditadas),
        f"{len(creditadas)} recompensa(s) / {len(cashbacks)} credito(s)",
    )
    concedido = round(sum(float(r["valor_brl"]) for r in creditadas), 2)
    creditado = round(sum(m["valor"] for m in cashbacks), 2)
    check(
        "os valores batem centavo a centavo",
        abs(concedido - creditado) < 0.01,
        f"R$ {concedido:.2f} concedidos / R$ {creditado:.2f} creditados",
    )
    check(
        "o cashback aparece traduzido no extrato",
        all("ashback" in m["rotulo"] for m in cashbacks),
        cashbacks[0]["rotulo"],
    )


def campanhas(client: httpx.Client, op: dict, drv: dict) -> None:
    """Ciclo de vida da campanha, pelo operador.

    Deixa rastro de proposito: `DELETE` ENCERRA a campanha, nao a apaga - apagar
    levaria junto o progresso de quem estava no meio dela, e o RESTRICT em
    `rewards.campaign_id` recusaria a exclusao assim que a primeira recompensa
    fosse concedida. Entao cada rodada deixa uma campanha inativa chamada
    "Smoke (pode apagar) ...". E' o custo de exercitar a criacao de verdade, e o
    nome diz o que fazer com ela.
    """
    secao("Campanhas")

    r = client.get(f"{API}/campaigns", headers=drv)
    check("motorista nao administra campanha", r.status_code == 403, f"HTTP {r.status_code}")

    existentes = client.get(f"{API}/campaigns", headers=op).json()
    check("campanhas do seed visiveis", len(existentes) > 0, f"{len(existentes)}")

    inicio = datetime.now(UTC)
    fim = inicio + timedelta(days=30)
    corpo = {
        "nome": f"Smoke (pode apagar) {uuid.uuid4().hex[:8]}",
        "patrocinador": "site",
        "starts_at": inicio.isoformat(),
        "ends_at": fim.isoformat(),
        # Cashback, e nao desconto: missao premia o ACUMULADO, e desconto se
        # aplica na hora, sem nada a acumular. O schema recusa a combinacao, e
        # as duas recusas estao cobertas logo abaixo.
        "beneficio_tipo": "cashback_fixo",
        "beneficio_valor": 5,
        "teto_por_recompensa": 5,
        "orcamento_brl": 500,
        "missoes": [
            {
                "codigo": "smoke-tres",
                "titulo": "Tres recargas",
                "metrica": "sessoes",
                "alvo": 3,
                "janela": "mensal",
            }
        ],
    }

    invertido = dict(corpo, starts_at=fim.isoformat(), ends_at=inicio.isoformat())
    r = client.post(f"{API}/campaigns", json=invertido, headers=op)
    check("periodo invertido rejeitado", r.status_code == 422, f"HTTP {r.status_code}")

    r = client.post(f"{API}/campaigns", json=dict(corpo, beneficio_valor=0), headers=op)
    check("beneficio zerado rejeitado", r.status_code == 422, f"HTTP {r.status_code}")

    # A recusa deliberada: nenhuma fatura aponta para `fleet_id`, entao a empresa
    # pagaria e o funcionario embolsaria.
    r = client.post(f"{API}/campaigns", json=dict(corpo, patrocinador="frota"), headers=op)
    check("campanha de frota recusada", r.status_code == 422, f"HTTP {r.status_code}")

    # Os dois lados da mesma regra: missao premia acumulado, desconto acontece na
    # hora. Juntar os dois criaria campanha cuja missao nunca premia ninguem.
    r = client.post(
        f"{API}/campaigns",
        json=dict(corpo, beneficio_tipo="desconto_pct", teto_por_recompensa=None),
        headers=op,
    )
    check("missao com desconto recusada", r.status_code == 422, f"HTTP {r.status_code}")

    r = client.post(f"{API}/campaigns", json=dict(corpo, missoes=[]), headers=op)
    check("cashback sem missao recusado", r.status_code == 422, f"HTTP {r.status_code}")

    r = client.post(f"{API}/campaigns", json=corpo, headers=op)
    if not check("campanha criada", r.status_code == 201, f"HTTP {r.status_code} {r.text[:90]}"):
        return
    nova = r.json()
    check("missao veio junto", len(nova["missoes"]) == 1, nova["missoes"][0]["codigo"])
    check("orcamento comeca sem consumo", float(nova["consumido_brl"]) == 0.0)

    r = client.patch(f"{API}/campaigns/{nova['id']}", json={"ativa": False}, headers=op)
    check("campanha pausada", r.status_code == 200 and r.json()["ativa"] is False)

    r = client.patch(f"{API}/campaigns/{nova['id']}", json={"patrocinador": "rede"}, headers=op)
    check("trocar quem paga e recusado", r.status_code == 422, f"HTTP {r.status_code}")

    r = client.get(f"{API}/campaigns/{nova['id']}/desempenho", headers=op)
    check("desempenho responde", r.status_code == 200, f"HTTP {r.status_code}")

    r = client.delete(f"{API}/campaigns/{nova['id']}", headers=op)
    check("campanha encerrada", r.status_code == 204, f"HTTP {r.status_code}")

    # `DELETE` aqui significa ENCERRAR, e a diferenca importa: a campanha
    # continua na lista, inativa, com o rastro de quem participou intacto. Um
    # operador que espere sumico vai achar que o botao falhou - e quem for
    # trocar isto por um DELETE de verdade esbarra neste check antes de esbarrar
    # no RESTRICT de `rewards.campaign_id`.
    encerrada = next(
        (c for c in client.get(f"{API}/campaigns", headers=op).json() if c["id"] == nova["id"]),
        None,
    )
    check(
        "encerrar desativa sem apagar o rastro",
        encerrada is not None and encerrada["ativa"] is False,
        "continua listada, inativa" if encerrada else "SUMIU da lista",
    )


def assinatura_do_motorista(client: httpx.Client, drv: dict) -> None:
    """Assinar cobra da carteira, e o razao registra.

    Assina e cancela na mesma passada: o mes pago continua valendo, mas o estado
    volta a permitir nova assinatura - entao a rodada seguinte encontra o
    ambiente como achou.

    A secao se FINANCIA: cada rodada debita uma mensalidade da carteira do
    motorista do seed, e sem recarregar antes o smoke funciona algumas vezes e
    depois passa a falhar com 402 - uma falha de ambiente que parece defeito de
    codigo. Foi o que aconteceu aqui na quinta rodada, com o saldo em R$ 14,50.
    """
    secao("Assinatura do motorista")

    planos = client.get(f"{API}/app/plans", headers=drv).json()
    if not check("planos publicados", len(planos) > 0, ", ".join(p["codigo"] for p in planos)):
        return
    plano = min(planos, key=lambda p: float(p["preco_mensal_brl"]))

    if client.get(f"{API}/app/subscription", headers=drv).json().get("assinante"):
        client.delete(f"{API}/app/subscription", headers=drv)

    r = client.post(f"{API}/app/subscription", json={"codigo": "nao-existe"}, headers=drv)
    check("plano inexistente recusado", r.status_code in (404, 422), f"HTTP {r.status_code}")

    r = client.post(f"{API}/app/subscription", json={}, headers=drv)
    check("assinatura sem codigo recusada", r.status_code == 422, f"HTTP {r.status_code}")

    mensalidade = float(plano["preco_mensal_brl"])
    saldo = client.get(f"{API}/auth/me", headers=drv).json()["wallet_balance"]
    if saldo < mensalidade:
        client.post(
            f"{API}/app/wallet/topup",
            json={"amount": f"{mensalidade:.2f}", "idempotency_key": f"smoke-{uuid.uuid4().hex}"},
            headers=drv,
        )

    saldo_antes = client.get(f"{API}/auth/me", headers=drv).json()["wallet_balance"]
    r = client.post(f"{API}/app/subscription", json={"codigo": plano["codigo"]}, headers=drv)
    if not check("assinatura criada", r.status_code == 201, f"HTTP {r.status_code} {r.text[:90]}"):
        return
    check("assinante ativo", r.json().get("assinante") is True, plano["codigo"])

    saldo_depois = client.get(f"{API}/auth/me", headers=drv).json()["wallet_balance"]
    check(
        "mensalidade debitada da carteira",
        abs((saldo_antes - saldo_depois) - mensalidade) < 0.01,
        f"R$ {saldo_antes:.2f} -> R$ {saldo_depois:.2f} (plano R$ {mensalidade:.2f})",
    )

    extrato = client.get(f"{API}/app/wallet/statement", headers=drv).json()
    ultimo = extrato["movimentos"][0] if extrato["movimentos"] else {}
    check(
        "o debito da mensalidade esta no razao",
        ultimo.get("origem") == "pagamento" and abs(ultimo.get("valor", 0) + mensalidade) < 0.01,
        f"{ultimo.get('rotulo')} R$ {ultimo.get('valor')}",
    )
    check("o razao fecha depois da cobranca", _fecha(extrato), f"R$ {extrato['saldo']:.2f}")

    r = client.post(f"{API}/app/subscription", json={"codigo": plano["codigo"]}, headers=drv)
    check("segunda assinatura barrada", r.status_code == 409, f"HTTP {r.status_code}")

    r = client.delete(f"{API}/app/subscription", headers=drv)
    check("assinatura cancelada", r.status_code == 204, f"HTTP {r.status_code}")

    # Cancelar para a RENOVACAO, nao o mes que ja foi pago. Cobrar o mes inteiro
    # e cortar o beneficio no instante do cancelamento seria vender trinta dias e
    # entregar cinco - entao `assinante` continua verdadeiro e `renova` vira
    # falso. E' a diferenca que a tela precisa mostrar, e que este check trava.
    depois = client.get(f"{API}/app/subscription", headers=drv).json()
    check(
        "o mes ja pago continua valendo",
        depois.get("assinante") is True and depois.get("renova") is False,
        f"assinante={depois.get('assinante')} renova={depois.get('renova')} "
        f"ate {depois.get('periodo_ate')}",
    )


def contrato_da_plataforma(client: httpx.Client, op: dict, drv: dict) -> None:
    """O contrato do estabelecimento com a GoodWe.

    NAO rescinde, de proposito: a rescisao nao tem volta pela API, e um smoke que
    destroi o ambiente roda uma vez so'. A multa e' conferida pela ARITMETICA que
    a propria rota publica.
    """
    secao("Contrato da plataforma")

    r = client.get(f"{API}/platform/contract", headers=drv)
    check("motorista nao ve o contrato", r.status_code == 403, f"HTTP {r.status_code}")

    planos = client.get(f"{API}/platform/plans", headers=op).json()
    check(
        "planos da plataforma publicados",
        len(planos) > 0,
        ", ".join(p["codigo"] for p in planos),
    )

    c = client.get(f"{API}/platform/contract", headers=op).json()
    if not check("contrato do seed presente", c.get("contratado") is True, c.get("estado")):
        return

    check(
        "prazo minimo depois do inicio",
        c["minimo_ate"] > c["starts_on"],
        f"{c['starts_on']} -> {c['minimo_ate']}",
    )
    check(
        "dentro do prazo tem meses restantes",
        (c["meses_restantes"] > 0) == c["dentro_do_prazo_minimo"],
        f"{c['meses_restantes']} mes(es)",
    )

    # A multa incide sobre a MENSALIDADE DO PLANO - nao sobre a cobranca cheia,
    # que ainda soma pontos excedentes e a taxa por transacao. O painel usa a
    # mesma base (`Contract.jsx` passa `d.plano.preco_mensal_brl` para
    # `multaPorRescisao`), entao este check trava os dois lados na mesma conta:
    # se um deles passar a somar os pontos, aqui quebra.
    plano = c["plano"]
    esperada = round(
        plano["preco_mensal_brl"] * c["meses_restantes"] * c["multa_percentual"] / 100, 2
    )
    check(
        "multa e a mesma conta do painel",
        abs(c["multa_se_rescindir_hoje"] - esperada) < 0.02,
        f"R$ {c['multa_se_rescindir_hoje']:.2f} = {plano['preco_mensal_brl']} x "
        f"{c['meses_restantes']} x {c['multa_percentual']}%",
    )

    cobrancas = c.get("cobrancas", [])
    check("cobrancas emitidas", len(cobrancas) > 0, f"{len(cobrancas)}")
    competencias = [b["competencia"] for b in cobrancas]
    check(
        "nenhuma competencia faturada duas vezes",
        len(competencias) == len(set(competencias)),
        f"{len(set(competencias))} competencia(s)",
    )

    aberta = next((b for b in cobrancas if b["estado"] != "paga"), None)

    # Quem recebe e' a rede, nao a praca. Deixar o proprio estabelecimento
    # declarar que pagou nao seria baixa manual, seria baixa nenhuma.
    alvo = aberta["id"] if aberta else uuid.uuid4()
    r = client.post(f"{API}/platform/invoices/{alvo}/settle", headers=op)
    check(
        "operador nao da baixa na propria cobranca",
        r.status_code == 403,
        f"HTTP {r.status_code}",
    )

    if not _ADMIN_SENHA:
        check("baixa manual nao verificada (defina SEED_ADMIN_PASSWORD)", True, "pulado")
        return
    adm = {"Authorization": f"Bearer {login(client, *ADMIN)}"}

    r = client.post(f"{API}/platform/invoices/{uuid.uuid4()}/settle", headers=adm)
    check("baixa de cobranca inexistente e 404", r.status_code == 404, f"HTTP {r.status_code}")

    if aberta is None:
        check("nenhuma cobranca em aberto para baixar", True, "todas ja pagas")
        return
    r = client.post(f"{API}/platform/invoices/{aberta['id']}/settle", headers=adm)
    check(
        "baixa manual registrada pelo admin",
        r.status_code == 200 and r.json().get("estado") == "paga",
        f"HTTP {r.status_code}",
    )
    r = client.post(f"{API}/platform/invoices/{aberta['id']}/settle", headers=adm)
    check("baixa repetida e inofensiva", r.status_code == 200, "idempotente")


def previsao(client: httpx.Client, op: dict) -> None:
    """A previsao, e o que a tela promete sobre ela.

    O que se confere nao e' acuracia - e' HONESTIDADE: banda so' quando o numero
    vem do modelo, e aviso sempre que a origem nao for o modelo.
    """
    secao("Previsao de energia")

    d = client.get(f"{API}/power/demand/energy-forecast", headers=op).json()
    if not check("previsao disponivel", d.get("disponivel") is True, d.get("motivo", "")):
        return

    check("competencia e primeiro do mes", d["competencia"].endswith("-01"), d["competencia"])
    check("energia prevista positiva", float(d["kwh_previsto"]) > 0, f"{d['kwh_previsto']:.0f} kWh")
    check("fonte declarada", d["fonte"] in ("modelo", "media_movel"), d["fonte"])

    tem_banda = d["kwh_p10"] is not None or d["kwh_p90"] is not None
    check(
        "banda so existe quando o numero vem do modelo",
        (d["fonte"] == "modelo") or not tem_banda,
        f"fonte={d['fonte']}, banda={'sim' if tem_banda else 'nao'}",
    )
    if d["fonte"] == "modelo" and tem_banda:
        check(
            "a banda contem o previsto",
            float(d["kwh_p10"]) <= float(d["kwh_previsto"]) <= float(d["kwh_p90"]),
            f"{d['kwh_p10']:.0f} <= {d['kwh_previsto']:.0f} <= {d['kwh_p90']:.0f}",
        )

    avisos = d.get("avisos", [])
    if d["fonte"] != "modelo":
        check(
            "media movel vem com aviso",
            len(avisos) > 0,
            avisos[0]["texto"][:60] if avisos else "NENHUM",
        )
        check(
            "o WAPE publicado sustenta a escolha",
            d["wape_modelo_pct"] is None
            or float(d["wape_modelo_pct"]) >= float(d["wape_baseline_pct"]),
            f"modelo {d['wape_modelo_pct']}% / regua {d['wape_baseline_pct']}%",
        )


def main() -> int:
    _exigir_credenciais()
    print(f"Alvo: {BASE}")
    with httpx.Client(timeout=30.0) as client:
        op, drv = autenticacao(client)
        limpas = limpar_sessoes_ativas(client, op)
        if limpas:
            print(f"      {limpas} sessão(ões) de execução anterior encerrada(s)")
        cp = potencia(client, op)
        controle_de_demanda(client, op, cp)
        corte_manual(client, op)
        agendamento(client, op)
        coerencia_da_tarifa(client, op)
        ses = sessao(client, op, cp)
        if ses is not None:
            fatura = faturamento(client, op, ses)
            if fatura is not None:
                cobranca(client, op, fatura)
        carteira(client, drv)
        gamificacao(client, drv)
        campanhas(client, op, drv)
        assinatura_do_motorista(client, drv)
        contrato_da_plataforma(client, op, drv)
        previsao(client, op)
    return resumo()


if __name__ == "__main__":
    sys.exit(main())
