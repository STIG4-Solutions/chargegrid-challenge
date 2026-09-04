"""Tamanho das respostas de lista.

Nenhuma dessas rotas tinha teto. As que crescem com o tempo - agendamentos - ou
com o negocio - estacoes - podiam devolver a tabela inteira numa resposta so.
"""

from datetime import UTC, datetime, timedelta

CAB = "/api/v1/app"


async def _agendamentos(db, motorista, ponto, quantos: int):
    """Cria direto no banco, com janelas ja passadas.

    Nao pela API de proposito: ela recusa janela no passado e limita
    agendamentos EM ABERTO por motorista. A lista, porem, mostra o historico
    inteiro - e' justamente por ele crescer sem teto que a paginacao existe.
    """
    import uuid

    from app.models.enums import ReservationStatus
    from app.models.reservation import Reservation

    base = datetime.now(UTC) - timedelta(days=30)
    for n in range(quantos):
        db.add(
            Reservation(
                id=uuid.uuid4(),
                code=f"RES-{uuid.uuid4().hex[:8].upper()}",
                site_id=ponto.site_id,
                charge_point_id=ponto.id,
                user_id=motorista.id,
                status=ReservationStatus.EXPIRED,
                starts_at=base + timedelta(hours=n * 2),
                ends_at=base + timedelta(hours=n * 2 + 1),
            )
        )
    await db.flush()


async def test_agendamentos_respeitam_o_limite(api, como_motorista, db, motorista, ponto):
    await _agendamentos(db, motorista, ponto, 12)
    r = await api.get(f"{CAB}/reservations?limit=5", headers=como_motorista)
    assert r.status_code == 200
    assert len(r.json()) == 5


async def test_offset_anda_pela_lista_sem_repetir(api, como_motorista, db, motorista, ponto):
    await _agendamentos(db, motorista, ponto, 12)
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
