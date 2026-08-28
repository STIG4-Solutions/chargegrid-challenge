"""Tamanho da serie de telemetria.

A janela em minutos nao limitava a resposta: o poller grava a cada 5 s, entao
24 h de sessao dao mais de 17 mil amostras - e o painel pede 4 h a cada 12 s.

Cortar com LIMIT truncaria a serie e o grafico mentiria, mostrando o comeco da
recarga como se fosse a recarga inteira. Por isso reamostra, em vez de cortar.
"""

import uuid
from datetime import UTC, datetime, timedelta

from app.models.telemetry import TelemetrySample

CAB = "/api/v1/sessions"


async def _amostras(db, ponto, sessao_id, quantas: int, passo_s: int = 5):
    inicio = datetime.now(UTC) - timedelta(seconds=quantas * passo_s)
    for n in range(quantas):
        db.add(
            TelemetrySample(
                id=uuid.uuid4(),
                charge_point_id=ponto.id,
                session_id=sessao_id,
                recorded_at=inicio + timedelta(seconds=n * passo_s),
                power_kw=7 + (n % 5),
                session_energy_kwh=n * 0.01,
            )
        )
    await db.flush()


async def test_serie_curta_volta_inteira(api, como_operador, db, ponto, motorista):
    from app.services import session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    await _amostras(db, ponto, sessao.id, 40)

    r = await api.get(f"{CAB}/{sessao.id}/telemetry?minutes=1440", headers=como_operador)
    assert r.status_code == 200, r.text
    assert len(r.json()) == 40, "sem excesso, nada deveria ser descartado"


async def test_serie_longa_e_reamostrada_ate_o_teto(api, como_operador, db, ponto, motorista):
    from app.services import session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    await _amostras(db, ponto, sessao.id, 1000)

    r = await api.get(
        f"{CAB}/{sessao.id}/telemetry?minutes=1440&max_points=100", headers=como_operador
    )
    assert r.status_code == 200
    pontos = r.json()
    assert 0 < len(pontos) <= 101, f"o teto nao foi respeitado: {len(pontos)}"


async def test_reamostragem_cobre_a_janela_inteira(api, como_operador, db, ponto, motorista):
    """O ponto da reamostragem: nao pode virar 'so o comeco da recarga'."""
    from app.services import session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    await _amostras(db, ponto, sessao.id, 1000)

    completa = (
        await api.get(f"{CAB}/{sessao.id}/telemetry?minutes=1440&max_points=5000",
                      headers=como_operador)
    ).json()
    reduzida = (
        await api.get(f"{CAB}/{sessao.id}/telemetry?minutes=1440&max_points=50",
                      headers=como_operador)
    ).json()

    assert len(completa) == 1000
    assert len(reduzida) < len(completa)
    # comeca no mesmo lugar e termina no mesmo lugar
    assert reduzida[0]["recorded_at"] == completa[0]["recorded_at"]
    assert reduzida[-1]["recorded_at"] == completa[-1]["recorded_at"]


async def test_serie_continua_em_ordem_cronologica(api, como_operador, db, ponto, motorista):
    from app.services import session_service

    sessao = await session_service.authorize(db, ponto, user=motorista)
    await _amostras(db, ponto, sessao.id, 600)

    pontos = (
        await api.get(f"{CAB}/{sessao.id}/telemetry?minutes=1440&max_points=60",
                      headers=como_operador)
    ).json()
    marcas = [p["recorded_at"] for p in pontos]
    assert marcas == sorted(marcas), "a reamostragem embaralhou a serie"
