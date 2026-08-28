"""Tamanho das respostas de lista.

Nenhuma dessas rotas tinha teto. As que crescem com o tempo - agendamentos - ou
com o negocio - estacoes - podiam devolver a tabela inteira numa resposta so.
"""

from datetime import UTC, datetime, timedelta

CAB = "/api/v1/app"


async def _agendamentos(api, cab, ponto, quantos: int):
    """Cria pela propria API: janelas de 1h, espacadas, para nao conflitarem."""
    base = datetime.now(UTC) + timedelta(days=1)
    for n in range(quantos):
        r = await api.post(
            f"{CAB}/reservations",
            headers=cab,
            json={
                "charge_point_id": str(ponto.id),
                "starts_at": (base + timedelta(hours=n * 2)).isoformat(),
                "ends_at": (base + timedelta(hours=n * 2 + 1)).isoformat(),
            },
        )
        assert r.status_code == 201, r.text


async def test_agendamentos_respeitam_o_limite(api, como_motorista, ponto):
    await _agendamentos(api, como_motorista, ponto, 12)
    r = await api.get(f"{CAB}/reservations?limit=5", headers=como_motorista)
    assert r.status_code == 200
    assert len(r.json()) == 5


async def test_offset_anda_pela_lista_sem_repetir(api, como_motorista, ponto):
    await _agendamentos(api, como_motorista, ponto, 12)
    pagina1 = (await api.get(f"{CAB}/reservations?limit=5&offset=0", headers=como_motorista)).json()
    pagina2 = (await api.get(f"{CAB}/reservations?limit=5&offset=5", headers=como_motorista)).json()

    ids1 = {a["id"] for a in pagina1}
    ids2 = {a["id"] for a in pagina2}
    assert len(ids1) == 5 and len(ids2) == 5
    assert not (ids1 & ids2), "a segunda pagina repetiu itens da primeira"


async def test_limite_absurdo_e_recusado(api, como_motorista):
    """O teto existe para o cliente nao poder pedir a tabela inteira."""
    r = await api.get(f"{CAB}/reservations?limit=100000", headers=como_motorista)
    assert r.status_code == 422


async def test_estacoes_tem_teto(api, como_motorista, ponto, tarifa):
    r = await api.get(f"{CAB}/stations?limit=1", headers=como_motorista)
    assert r.status_code == 200
    assert len(r.json()) <= 1


async def test_veiculos_tem_teto(api, como_motorista):
    for n in range(3):
        await api.post(f"{CAB}/vehicles", headers=como_motorista, json={"model": f"Carro {n}"})
    r = await api.get(f"{CAB}/vehicles?limit=2", headers=como_motorista)
    assert len(r.json()) == 2
