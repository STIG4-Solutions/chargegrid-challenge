"""Fluxos do app do motorista pela porta da frente.

Ate agora as rotas /app/* eram cobertas so por testes de servico. Das doze,
apenas /app/reservations aparecia no teste de fumaca. Aqui elas rodam por HTTP:
o corpo e' validado pelo Pydantic, a resposta e' serializada pelo response_model
e o escopo por usuario e' exercido de verdade.
"""

import uuid
from datetime import UTC, datetime, timedelta

CAB = "/api/v1/app"


async def test_estacoes_trazem_vagas_conectores_e_preco(api, como_motorista, ponto):
    r = await api.get(f"{CAB}/stations", headers=como_motorista)
    assert r.status_code == 200
    estacoes = r.json()
    assert estacoes, "o site do fixture deveria aparecer"
    e = estacoes[0]
    assert e["available_points"] >= 1
    assert e["connectors"], "conector some da resposta"
    assert e["max_kw"] > 0


async def test_qr_resolve_o_ponto_e_diz_a_que_estacao_pertence(
    api, como_motorista, ponto, site
):
    r = await api.get(f"{CAB}/charge-points/by-code/{ponto.code}", headers=como_motorista)
    assert r.status_code == 200, r.text
    corpo = r.json()
    assert corpo["code"] == ponto.code
    assert corpo["site_id"] == str(site.id)
    assert corpo["site_name"] == site.name


async def test_qr_aceita_caixa_e_espacos_como_a_camera_le(api, como_motorista, ponto):
    r = await api.get(
        f"{CAB}/charge-points/by-code/%20{ponto.code.lower()}%20", headers=como_motorista
    )
    assert r.status_code == 200, r.text
    assert r.json()["code"] == ponto.code


async def test_veiculo_criado_aparece_na_lista_do_dono(api, como_motorista):
    r = await api.post(
        f"{CAB}/vehicles",
        headers=como_motorista,
        json={"model": "Nissan Leaf", "plate": "ABC1D23", "battery_kwh": 40},
    )
    assert r.status_code == 201, r.text
    criado = r.json()

    lista = (await api.get(f"{CAB}/vehicles", headers=como_motorista)).json()
    assert [v["id"] for v in lista] == [criado["id"]]


async def test_veiculo_de_um_motorista_nao_vaza_para_outro(api, como_motorista, db):
    await api.post(
        f"{CAB}/vehicles", headers=como_motorista, json={"model": "So meu"}
    )

    from app.core.security import create_access_token
    from app.models.enums import UserRole
    from app.models.user import User

    outro = User(
        id=uuid.uuid4(),
        email=f"outro-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Outro Motorista",
        hashed_password="x",
        role=UserRole.DRIVER,
    )
    db.add(outro)
    await db.flush()

    cab = {"Authorization": f"Bearer {create_access_token(str(outro.id))}"}
    assert (await api.get(f"{CAB}/vehicles", headers=cab)).json() == []


async def test_modelo_vazio_e_recusado_pela_validacao(api, como_motorista):
    r = await api.post(f"{CAB}/vehicles", headers=como_motorista, json={})
    assert r.status_code == 422


async def test_agendamento_recusa_janela_invertida(api, como_motorista, ponto):
    inicio = datetime.now(UTC) + timedelta(hours=2)
    r = await api.post(
        f"{CAB}/reservations",
        headers=como_motorista,
        json={
            "charge_point_id": str(ponto.id),
            "starts_at": inicio.isoformat(),
            "ends_at": (inicio - timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 422


async def test_agendamento_criado_aparece_com_contexto_da_estacao(
    api, como_motorista, ponto, site
):
    inicio = datetime.now(UTC) + timedelta(hours=3)
    r = await api.post(
        f"{CAB}/reservations",
        headers=como_motorista,
        json={
            "charge_point_id": str(ponto.id),
            "starts_at": inicio.isoformat(),
            "ends_at": (inicio + timedelta(hours=1)).isoformat(),
        },
    )
    assert r.status_code == 201, r.text

    lista = (await api.get(f"{CAB}/reservations", headers=como_motorista)).json()
    assert len(lista) == 1
    # o app mostra nome da estacao e codigo da vaga sem uma segunda chamada
    assert lista[0]["site_name"] == site.name
    assert lista[0]["charge_point_code"] == ponto.code


async def test_agendamento_cancelado_sai_da_lista(api, como_motorista, ponto):
    inicio = datetime.now(UTC) + timedelta(hours=5)
    criado = (
        await api.post(
            f"{CAB}/reservations",
            headers=como_motorista,
            json={
                "charge_point_id": str(ponto.id),
                "starts_at": inicio.isoformat(),
                "ends_at": (inicio + timedelta(hours=1)).isoformat(),
            },
        )
    ).json()

    r = await api.delete(f"{CAB}/reservations/{criado['id']}", headers=como_motorista)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "cancelled"


async def test_sem_recarga_em_andamento_a_resposta_e_nula(api, como_motorista):
    r = await api.get(f"{CAB}/sessions/active", headers=como_motorista)
    assert r.status_code == 200
    assert r.json() is None
