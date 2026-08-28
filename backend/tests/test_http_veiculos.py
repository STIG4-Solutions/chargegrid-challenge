"""Cadastro de veiculos: corrigir e remover.

Dava para adicionar um carro e nunca mais mexer nele - nem consertar uma placa
digitada errada, nem tirar um carro vendido da lista.
"""

CAB = "/api/v1/app"


async def _criar(api, cab, **campos):
    r = await api.post(f"{CAB}/vehicles", headers=cab, json={"model": "Leaf", **campos})
    assert r.status_code == 201, r.text
    return r.json()


async def test_corrige_a_placa_sem_mexer_no_resto(api, como_motorista):
    v = await _criar(api, como_motorista, plate="ABC0000", battery_kwh=40)

    r = await api.patch(
        f"{CAB}/vehicles/{v['id']}", headers=como_motorista, json={"plate": "XYZ9876"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["plate"] == "XYZ9876"
    assert r.json()["battery_kwh"] == 40, "o campo nao enviado foi apagado"


async def test_remove_o_carro_vendido(api, como_motorista):
    v = await _criar(api, como_motorista)

    r = await api.delete(f"{CAB}/vehicles/{v['id']}", headers=como_motorista)
    assert r.status_code == 204
    assert (await api.get(f"{CAB}/vehicles", headers=como_motorista)).json() == []


async def test_nao_mexe_no_carro_de_outra_pessoa(api, como_motorista, db):
    """404, nao 403: um 403 confirmaria que o identificador existe."""
    import uuid

    from app.core.security import create_access_token
    from app.models.enums import UserRole
    from app.models.user import User

    v = await _criar(api, como_motorista)

    outro = User(
        id=uuid.uuid4(),
        email=f"outro-{uuid.uuid4().hex[:8]}@example.com",
        full_name="Outro",
        hashed_password="x",
        role=UserRole.DRIVER,
    )
    db.add(outro)
    await db.flush()
    cab = {"Authorization": f"Bearer {create_access_token(str(outro.id))}"}

    alterar = await api.patch(f"{CAB}/vehicles/{v['id']}", headers=cab, json={"plate": "X"})
    apagar = await api.delete(f"{CAB}/vehicles/{v['id']}", headers=cab)
    assert alterar.status_code == 404
    assert apagar.status_code == 404


async def test_carro_em_recarga_nao_pode_sair(api, como_motorista, db, motorista, ponto):
    """A sessao em curso ficaria sem carro - e o rateio usa a potencia dele."""
    from app.services import session_service

    v = await _criar(api, como_motorista)
    await session_service.authorize(db, ponto, user=motorista, vehicle_id=v["id"])

    r = await api.delete(f"{CAB}/vehicles/{v['id']}", headers=como_motorista)
    assert r.status_code == 409, r.text


async def test_carro_removido_nao_apaga_o_historico(api, como_motorista, db, motorista, ponto):
    """ON DELETE SET NULL: a fatura antiga continua de pe, so perde o vinculo."""
    from app.models.enums import StopReason
    from app.services import session_service

    v = await _criar(api, como_motorista)
    sessao = await session_service.authorize(db, ponto, user=motorista, vehicle_id=v["id"])
    sessao = await session_service.start(db, sessao, ponto)
    await session_service.stop(db, sessao, ponto, reason=StopReason.REMOTE)

    apagado = await api.delete(f"{CAB}/vehicles/{v['id']}", headers=como_motorista)
    assert apagado.status_code == 204

    historico = (await api.get(f"{CAB}/sessions", headers=como_motorista)).json()
    assert any(s["id"] == str(sessao.id) for s in historico), "a sessao sumiu junto com o carro"
