"""Reporte de problema no ponto, e conta corporativa.

O reporte existe para o caso em que o sensor nunca vai confirmar nada: cabo
cortado, tela apagada, vaga tomada por um carro a combustao. Se a manutencao
so' subir a prioridade quando o equipamento concordar, a feature nao serve
para nada — e' justamente onde ele nao ve que ela precisa funcionar.

A frota lida com dinheiro de terceiros: um gestor que enxerga a area errada,
ou uma fatura cancelada somada ao gasto, aparece na conta de alguem.
"""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest

from app.models.charge_point_report import ChargePointReport
from app.models.enums import InvoiceStatus, SessionState
from app.models.fleet import Fleet
from app.services import fleet_service as fs
from app.services import maintenance_service as ms

# ---------------------------------------------------------------- reportes


def _reporte(ponto, motorista, categoria, quando=None, resolvido=False, descricao=None):
    r = ChargePointReport(
        id=uuid.uuid4(),
        charge_point_id=ponto.id,
        user_id=motorista.id,
        categoria=categoria,
        descricao=descricao,
    )
    if quando:
        r.created_at = quando
    if resolvido:
        r.resolved_at = datetime.now(UTC)
        r.resolved_by = motorista.id
    return r


async def test_reporte_sozinho_ja_poe_o_ponto_em_atencao(db, site, ponto, motorista):
    """O caso que da nome a feature.

    Duas reclamacoes, zero sinal do equipamento. Se a manutencao esperasse a
    confirmacao do sensor, esperaria para sempre: o ponto reporta "disponivel"
    com toda a sinceridade, porque do ponto de vista dele esta tudo bem.
    """
    db.add_all([
        _reporte(ponto, motorista, "cabo_danificado", descricao="cabo com fio a mostra"),
        _reporte(ponto, motorista, "cabo_danificado"),
    ])
    await db.flush()

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["reportes_abertos"] == 2
    assert alvo["so_humano"] is True
    assert alvo["prioridade"] == "alta"
    assert alvo["reportes"][0]["ultimo_relato"] == "cabo com fio a mostra"


async def test_um_reporte_isolado_nao_alarma(db, site, ponto, motorista):
    """Uma pessoa pode ter errado de vaga. Duas ja e' padrao."""
    db.add(_reporte(ponto, motorista, "nao_inicia"))
    await db.flush()

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["reportes_abertos"] == 1
    assert alvo["prioridade"] == "baixa"


async def test_reportes_agrupam_por_categoria(db, site, ponto, motorista):
    """Tres pessoas reclamando do mesmo cabo sao um problema, nao tres."""
    db.add_all([
        _reporte(ponto, motorista, "cabo_danificado"),
        _reporte(ponto, motorista, "cabo_danificado"),
        _reporte(ponto, motorista, "tela_apagada"),
    ])
    await db.flush()

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    por_categoria = {x["categoria"]: x for x in alvo["reportes"]}
    assert por_categoria["cabo_danificado"]["quantidade"] == 2
    assert por_categoria["tela_apagada"]["quantidade"] == 1


async def test_reporte_resolvido_sai_da_contagem_de_abertos(db, site, ponto, motorista):
    db.add_all([
        _reporte(ponto, motorista, "nao_inicia", resolvido=True),
        _reporte(ponto, motorista, "nao_inicia", resolvido=True),
    ])
    await db.flush()

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["reportes"][0]["quantidade"] == 2
    assert alvo["reportes_abertos"] == 0
    assert alvo["so_humano"] is False
    assert alvo["prioridade"] == "baixa"


async def test_reporte_com_falha_do_sensor_nao_e_so_humano(db, site, ponto, motorista, agora):
    """Quando as duas fontes concordam, o rotulo muda: aqui o sensor confirma."""
    from app.models.charge_point import ChargePointFault

    db.add(
        ChargePointFault(
            id=uuid.uuid4(), charge_point_id=ponto.id, label="falha da trava",
            terminal=False, first_seen_at=agora - timedelta(days=1),
            last_seen_at=agora, ciclos=10,
        )
    )
    db.add_all([
        _reporte(ponto, motorista, "conector_travado"),
        _reporte(ponto, motorista, "conector_travado"),
    ])
    await db.flush()

    r = await ms.pontos_em_atencao(db, site.id, dias=30)
    alvo = next(p for p in r["pontos"] if p["code"] == ponto.code)
    assert alvo["so_humano"] is False
    assert alvo["reportes_abertos"] == 2
    assert len(alvo["sintomas"]) == 1


# ----------------------------------------------------------- reporte por HTTP


async def test_motorista_reporta(api, site, ponto, como_motorista):
    r = await api.post(
        f"/api/v1/app/charge-points/{ponto.id}/reports",
        json={"categoria": "cabo_danificado", "descricao": "cabo com fio à mostra"},
        headers=como_motorista,
    )
    assert r.status_code == 201, r.text
    assert r.json()["ponto"] == ponto.code


async def test_categoria_invalida_e_recusada(api, site, ponto, como_motorista):
    """A lista fechada e' o que faz o relatorio agregar."""
    r = await api.post(
        f"/api/v1/app/charge-points/{ponto.id}/reports",
        json={"categoria": "explodiu"},
        headers=como_motorista,
    )
    assert r.status_code == 422


async def test_ponto_inexistente_da_404(api, site, como_motorista):
    r = await api.post(
        f"/api/v1/app/charge-points/{uuid.uuid4()}/reports",
        json={"categoria": "outro"},
        headers=como_motorista,
    )
    assert r.status_code == 404


async def test_nao_da_para_amarrar_reporte_a_sessao_alheia(
    db, api, site, ponto, segundo_motorista, como_motorista
):
    """Daria ao operador uma pista falsa sobre quando o problema aconteceu."""
    from app.models.session import ChargingSession

    alheia = ChargingSession(
        id=uuid.uuid4(), code="SES-ALHEIA", site_id=site.id, charge_point_id=ponto.id,
        user_id=segundo_motorista.id, state=SessionState.FINISHED,
        energy_kwh=0, duration_s=0, estimated_cost=0, preauth_amount=0, idle_minutes=0,
    )
    db.add(alheia)
    await db.flush()

    r = await api.post(
        f"/api/v1/app/charge-points/{ponto.id}/reports",
        json={"categoria": "outro", "session_id": str(alheia.id)},
        headers=como_motorista,
    )
    assert r.status_code == 404


async def test_motorista_so_ve_os_proprios_reportes(
    db, api, ponto, motorista, segundo_motorista, como_motorista
):
    """A lista de reclamacoes de um ponto e' informacao do operador."""
    db.add_all([
        _reporte(ponto, motorista, "nao_inicia"),
        _reporte(ponto, segundo_motorista, "tela_apagada"),
    ])
    await db.flush()

    r = await api.get(f"/api/v1/app/charge-points/{ponto.id}/reports", headers=como_motorista)
    assert r.status_code == 200
    categorias = {x["categoria"] for x in r.json()}
    assert categorias == {"nao_inicia"}


async def test_operador_nao_reporta_pelo_app(api, site, ponto, como_operador):
    r = await api.post(
        f"/api/v1/app/charge-points/{ponto.id}/reports",
        json={"categoria": "outro"},
        headers=como_operador,
    )
    assert r.status_code == 403


# ------------------------------------------------------------------- frota


@pytest.fixture
async def frota(db):
    f = Fleet(id=uuid.uuid4(), name="Transportes Aurora", document="12345678000199", active=True)
    db.add(f)
    await db.flush()
    return f


@pytest.fixture
async def gestor(db, frota, motorista):
    motorista.fleet_id = frota.id
    motorista.fleet_manager = True
    await db.flush()
    return motorista


@pytest.fixture
def como_gestor(gestor):
    from tests.conftest import _cabecalho

    return _cabecalho(gestor)


async def _gasto(db, site, ponto, usuario, veiculo, valor, kwh, emitida, status=InvoiceStatus.PAID):
    from app.models.billing import Invoice
    from app.models.session import ChargingSession

    s = ChargingSession(
        id=uuid.uuid4(), code=f"S-{uuid.uuid4().hex[:6]}", site_id=site.id,
        charge_point_id=ponto.id, user_id=usuario.id,
        vehicle_id=veiculo.id if veiculo else None,
        state=SessionState.BILLED, energy_kwh=kwh, duration_s=3600,
        estimated_cost=valor, preauth_amount=0, idle_minutes=0,
    )
    db.add(s)
    await db.flush()
    db.add(
        Invoice(
            id=uuid.uuid4(), code=f"INV-{uuid.uuid4().hex[:6]}", site_id=site.id,
            session_id=s.id, user_id=usuario.id, status=status, currency="BRL",
            subtotal=valor, discount=0, total=valor, processing_fee=0, net_amount=valor,
            issued_on=emitida,
        )
    )
    await db.flush()


async def _veiculo(db, usuario, modelo, centro):
    from app.models.user import Vehicle

    v = Vehicle(id=uuid.uuid4(), user_id=usuario.id, model=modelo, cost_center=centro)
    db.add(v)
    await db.flush()
    return v


async def test_relatorio_agrupa_por_centro_de_custo(db, site, ponto, gestor, frota):
    logistica = await _veiculo(db, gestor, "Kangoo", "Logística")
    vendas = await _veiculo(db, gestor, "Leaf", "Vendas")

    await _gasto(db, site, ponto, gestor, logistica, 80.0, 40, date(2026, 3, 10))
    await _gasto(db, site, ponto, gestor, logistica, 60.0, 30, date(2026, 3, 20))
    await _gasto(db, site, ponto, gestor, vendas, 50.0, 25, date(2026, 3, 15))

    r = await fs.relatorio_mensal(db, gestor, mes="2026-03")
    assert r["disponivel"] is True
    assert r["total_brl"] == 190.0
    assert r["sessoes"] == 3

    # Maior gasto primeiro: e' a ordem em que o financeiro le.
    assert r["centros"][0]["centro_de_custo"] == "Logística"
    assert r["centros"][0]["total_brl"] == 140.0
    assert r["centros"][0]["sessoes"] == 2
    assert r["centros"][1]["total_brl"] == 50.0


async def test_fatura_cancelada_nao_entra_no_gasto(db, site, ponto, gestor):
    """Somaria dinheiro que ninguem pagou a conta de uma area."""
    v = await _veiculo(db, gestor, "Kangoo", "Logística")
    await _gasto(db, site, ponto, gestor, v, 80.0, 40, date(2026, 3, 10))
    await _gasto(db, site, ponto, gestor, v, 999.0, 500, date(2026, 3, 11), InvoiceStatus.VOID)

    r = await fs.relatorio_mensal(db, gestor, mes="2026-03")
    assert r["total_brl"] == 80.0


async def test_carro_sem_centro_aparece_em_vez_de_sumir(db, site, ponto, gestor):
    """Gasto sem area responsavel e' o primeiro que o financeiro precisa ver.

    Escondê-lo num filtro faria o total do relatorio nao bater com a fatura -
    a pior forma de esconder um problema de cadastro.
    """
    sem = await _veiculo(db, gestor, "Zoe", None)
    await _gasto(db, site, ponto, gestor, sem, 45.0, 20, date(2026, 3, 5))

    r = await fs.relatorio_mensal(db, gestor, mes="2026-03")
    assert r["sem_centro_brl"] == 45.0
    assert any(c["centro_de_custo"] == fs.SEM_CENTRO for c in r["centros"])
    assert r["total_brl"] == 45.0


async def test_mes_fecha_pela_emissao_da_fatura(db, site, ponto, gestor):
    """Sessao que vira a meia-noite pertence a fatura, e e' a fatura que se concilia."""
    v = await _veiculo(db, gestor, "Kangoo", "Logística")
    await _gasto(db, site, ponto, gestor, v, 30.0, 15, date(2026, 3, 31))
    await _gasto(db, site, ponto, gestor, v, 70.0, 35, date(2026, 4, 1))

    marco = await fs.relatorio_mensal(db, gestor, mes="2026-03")
    abril = await fs.relatorio_mensal(db, gestor, mes="2026-04")
    assert marco["total_brl"] == 30.0
    assert abril["total_brl"] == 70.0


async def test_gasto_de_outra_frota_nao_entra(db, site, ponto, gestor, segundo_motorista):
    """O consolidado e' da propria frota. Sem isso o gestor veria gasto alheio."""
    de_fora = await _veiculo(db, segundo_motorista, "Model 3", "Diretoria")
    await _gasto(db, site, ponto, segundo_motorista, de_fora, 500.0, 200, date(2026, 3, 10))

    r = await fs.relatorio_mensal(db, gestor, mes="2026-03")
    assert r["total_brl"] == 0.0


async def test_em_aberto_e_contado_a_parte(db, site, ponto, gestor):
    v = await _veiculo(db, gestor, "Kangoo", "Logística")
    await _gasto(db, site, ponto, gestor, v, 40.0, 20, date(2026, 3, 10))
    await _gasto(db, site, ponto, gestor, v, 60.0, 30, date(2026, 3, 11), InvoiceStatus.OPEN)

    r = await fs.relatorio_mensal(db, gestor, mes="2026-03")
    assert r["total_brl"] == 100.0
    assert r["em_aberto_brl"] == 60.0


async def test_conta_sem_frota(db, motorista):
    r = await fs.relatorio_mensal(db, motorista, mes="2026-03")
    assert r["disponivel"] is False


def test_mes_malformado_estoura():
    with pytest.raises(ValueError):
        fs._limites("2026-13")


def test_fevereiro_bissexto():
    inicio, fim = fs._limites("2028-02")
    assert (inicio.day, fim.day) == (1, 29)


# -------------------------------------------------------------- frota por HTTP


async def test_rota_do_relatorio(api, db, site, ponto, gestor, como_gestor):
    v = await _veiculo(db, gestor, "Kangoo", "Logística")
    await _gasto(db, site, ponto, gestor, v, 80.0, 40, date(2026, 3, 10))

    r = await api.get("/api/v1/app/fleet/report?mes=2026-03", headers=como_gestor)
    assert r.status_code == 200
    assert r.json()["total_brl"] == 80.0


async def test_motorista_comum_nao_ve_relatorio(api, site, como_motorista):
    """Ele veria o gasto de todos os colegas."""
    r = await api.get("/api/v1/app/fleet/report?mes=2026-03", headers=como_motorista)
    assert r.status_code == 403


async def test_operador_nao_ve_relatorio_de_frota(api, site, como_operador):
    r = await api.get("/api/v1/app/fleet/report?mes=2026-03", headers=como_operador)
    assert r.status_code == 403


async def test_mes_invalido_na_rota(api, site, gestor, como_gestor):
    for mes in ("2026-3", "marco", "2026-13"):
        r = await api.get(f"/api/v1/app/fleet/report?mes={mes}", headers=como_gestor)
        assert r.status_code == 422, f"{mes} deveria ser recusado, veio {r.status_code}"


async def test_gestor_define_centro_de_custo(api, db, gestor, como_gestor):
    v = await _veiculo(db, gestor, "Kangoo", None)
    r = await api.put(
        f"/api/v1/app/fleet/vehicles/{v.id}/cost-center",
        json={"centro_de_custo": "Logística"},
        headers=como_gestor,
    )
    assert r.status_code == 200
    assert r.json()["centro_de_custo"] == "Logística"


async def test_centro_vazio_limpa(api, db, gestor, como_gestor):
    v = await _veiculo(db, gestor, "Kangoo", "Logística")
    r = await api.put(
        f"/api/v1/app/fleet/vehicles/{v.id}/cost-center",
        json={"centro_de_custo": "   "},
        headers=como_gestor,
    )
    assert r.status_code == 200
    assert r.json()["centro_de_custo"] is None


async def test_gestor_nao_mexe_em_carro_de_outra_frota(
    api, db, gestor, segundo_motorista, como_gestor
):
    de_fora = await _veiculo(db, segundo_motorista, "Model 3", "Diretoria")
    r = await api.put(
        f"/api/v1/app/fleet/vehicles/{de_fora.id}/cost-center",
        json={"centro_de_custo": "Sequestrado"},
        headers=como_gestor,
    )
    assert r.status_code == 404
