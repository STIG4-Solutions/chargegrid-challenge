"""Teste de fumaca ponta a ponta contra uma API ja no ar.

Percorre o fluxo comercial completo: login, orcamento de potencia, ciclo da
sessao, faturamento e cobranca. Serve para validar um ambiente recem-subido.

    python -m scripts.smoke_test            # usa http://127.0.0.1:8000
    python -m scripts.smoke_test http://host:porta
"""

from __future__ import annotations

import os
import sys
import time
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
OPERADOR = ("operador@chargegrid.com.br", _OPERADOR_SENHA)
MOTORISTA = ("joao.silva@email.com", _MOTORISTA_SENHA)

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
    return op


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


def main() -> int:
    _exigir_credenciais()
    print(f"Alvo: {BASE}")
    with httpx.Client(timeout=30.0) as client:
        op = autenticacao(client)
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
    return resumo()


if __name__ == "__main__":
    sys.exit(main())
