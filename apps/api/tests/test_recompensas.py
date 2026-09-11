"""Concessao de recompensa: onde missao cumprida vira dinheiro.

Duas coisas sao guardadas aqui, e a segunda e' a que importa.

A primeira e' a aritmetica: quanto vale, respeitando teto por concessao e
orcamento da campanha.

A segunda e' que ninguem seja pago DUAS VEZES. A checagem da aplicacao e' um
SELECT seguido de um INSERT, e dois workers a atravessam juntos - os dois veem
a missao sem recompensa e os dois concedem. So' o indice unico parcial decide
quem chegou primeiro, e por isso os testes de corrida falam com o banco por
baixo do servico.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models.billing import WalletEntry
from app.models.campaign import Campaign, Mission, MissionProgress, Reward
from app.models.push_device import PushDevice
from app.services import campaign_service, notification_service
from app.services.push_senders import PushError

AGORA = datetime.now(UTC)


async def _campanha(db, **kwargs):
    dados = dict(
        patrocinador="rede",
        nome="Setembro Verde",
        starts_at=AGORA - timedelta(days=7),
        ends_at=AGORA + timedelta(days=7),
        ativa=True,
        beneficio_tipo="cashback_fixo",
        beneficio_valor=Decimal("5"),
        orcamento_brl=Decimal("1000"),
    )
    dados.update(kwargs)
    campanha = Campaign(**dados)
    db.add(campanha)
    await db.flush()
    return campanha


async def _missao_cumprida(db, campanha, motorista, **kwargs):
    """Missao com progresso ja concluido, sem passar por sessao nenhuma."""
    dados = dict(
        campaign_id=campanha.id,
        codigo=f"m-{uuid.uuid4().hex[:6]}",
        titulo="Missao",
        metrica="sessoes",
        alvo=Decimal("1"),
        janela="campanha",
    )
    dados.update(kwargs)
    missao = Mission(**dados)
    db.add(missao)
    await db.flush()

    progresso = MissionProgress(
        mission_id=missao.id,
        user_id=motorista.id,
        periodo=campanha.starts_at.date(),
        valor=Decimal("1"),
        concluida_em=datetime.now(UTC),
    )
    db.add(progresso)
    await db.flush()
    return missao, progresso


async def _recompensas(db, motorista) -> list[Reward]:
    return list(
        (
            await db.execute(
                select(Reward)
                .where(Reward.user_id == motorista.id)
                .execution_options(populate_existing=True)
            )
        )
        .scalars()
        .all()
    )


# ---------------------------------------------------------------- aritmetica


async def test_missao_cumprida_vira_credito_na_carteira(db, motorista):
    campanha = await _campanha(db, beneficio_valor=Decimal("12"))
    await _missao_cumprida(db, campanha, motorista)
    saldo_antes = Decimal(str(motorista.wallet_balance))

    assert await campaign_service.conceder_pendentes(db) == 1

    recompensas = await _recompensas(db, motorista)
    assert len(recompensas) == 1
    assert recompensas[0].estado == "creditada"
    assert Decimal(str(recompensas[0].valor_brl)) == Decimal("12.00")

    await db.refresh(motorista)
    assert Decimal(str(motorista.wallet_balance)) == saldo_antes + Decimal("12.00")


async def test_o_credito_diz_de_onde_veio(db, motorista):
    """Sem `origem`, o extrato mostra R$ 12,00 sem explicar o que e'."""
    campanha = await _campanha(db)
    await _missao_cumprida(db, campanha, motorista)
    await campaign_service.conceder_pendentes(db)

    credito = (
        await db.execute(
            select(WalletEntry).where(
                WalletEntry.user_id == motorista.id, WalletEntry.origem == "cashback"
            )
        )
    ).scalar_one()
    assert credito.origem == "cashback"
    assert credito.origem_ref is not None
    # A chave e' DETERMINISTICA: e' ela que faz o UNIQUE ja existente valer como
    # protecao contra credito duplo, sem tabela de trava nova.
    assert credito.idempotency_key.startswith("reward:")


async def test_teto_limita_a_concessao_individual(db, motorista):
    """Percentual sem teto numa recarga grande gasta o orcamento numa pessoa so'."""
    campanha = await _campanha(
        db,
        beneficio_tipo="cashback_fixo",
        beneficio_valor=Decimal("500"),
        teto_por_recompensa=Decimal("20"),
    )
    await _missao_cumprida(db, campanha, motorista)

    await campaign_service.conceder_pendentes(db)

    recompensas = await _recompensas(db, motorista)
    assert Decimal(str(recompensas[0].valor_brl)) == Decimal("20.00")


async def test_orcamento_esgotado_nao_concede(db, motorista):
    """Teto duro: gastar alem dele compromete dinheiro que ninguem autorizou."""
    campanha = await _campanha(
        db, beneficio_valor=Decimal("50"), orcamento_brl=Decimal("10")
    )
    await _missao_cumprida(db, campanha, motorista)

    assert await campaign_service.conceder_pendentes(db) == 0
    assert await _recompensas(db, motorista) == []


async def test_conceder_consome_o_orcamento_da_campanha(db, motorista):
    campanha = await _campanha(db, beneficio_valor=Decimal("30"))
    await _missao_cumprida(db, campanha, motorista)

    await campaign_service.conceder_pendentes(db)

    await db.refresh(campanha)
    assert Decimal(str(campanha.consumido_brl)) == Decimal("30.00")


# ------------------------------------------------------------------- corrida


async def test_banco_recusa_duas_recompensas_para_o_mesmo_progresso(db, motorista):
    """O indice unico parcial e' a unica garantia real.

    Fala com o banco por baixo do servico de proposito: e' a constraint que esta
    sendo verificada, nao a checagem da aplicacao.
    """
    campanha = await _campanha(db)
    _missao, progresso = await _missao_cumprida(db, campanha, motorista)

    db.add(
        Reward(
            user_id=motorista.id,
            campaign_id=campanha.id,
            mission_progress_id=progresso.id,
            tipo="cashback_fixo",
            valor_brl=Decimal("5"),
            estado="pendente",
        )
    )
    await db.flush()

    with pytest.raises(IntegrityError):
        db.add(
            Reward(
                user_id=motorista.id,
                campaign_id=campanha.id,
                mission_progress_id=progresso.id,
                tipo="cashback_fixo",
                valor_brl=Decimal("5"),
                estado="pendente",
            )
        )
        await db.flush()


async def test_recompensa_cancelada_libera_o_lugar(db, motorista):
    """Cancelar permite reconceder sem apagar o historico do que foi cancelado."""
    campanha = await _campanha(db)
    _missao, progresso = await _missao_cumprida(db, campanha, motorista)

    cancelada = Reward(
        user_id=motorista.id,
        campaign_id=campanha.id,
        mission_progress_id=progresso.id,
        tipo="cashback_fixo",
        valor_brl=Decimal("5"),
        estado="cancelada",
    )
    db.add(cancelada)
    await db.flush()

    # O indice ignora canceladas, entao esta passa.
    db.add(
        Reward(
            user_id=motorista.id,
            campaign_id=campanha.id,
            mission_progress_id=progresso.id,
            tipo="cashback_fixo",
            valor_brl=Decimal("5"),
            estado="pendente",
        )
    )
    await db.flush()

    assert len(await _recompensas(db, motorista)) == 2


async def test_rodar_o_worker_duas_vezes_nao_credita_duas_vezes(db, motorista):
    """A protecao que o operador realmente exercita: reprocessar a fila."""
    campanha = await _campanha(db, beneficio_valor=Decimal("7"))
    await _missao_cumprida(db, campanha, motorista)
    saldo_antes = Decimal(str(motorista.wallet_balance))

    assert await campaign_service.conceder_pendentes(db) == 1
    assert await campaign_service.conceder_pendentes(db) == 0

    assert len(await _recompensas(db, motorista)) == 1
    await db.refresh(motorista)
    assert Decimal(str(motorista.wallet_balance)) == saldo_antes + Decimal("7.00")


async def test_creditar_exige_dizer_onde(db, motorista):
    """Uma recompensa nao pode se declarar paga sem existir credito nenhum."""
    campanha = await _campanha(db)
    _missao, progresso = await _missao_cumprida(db, campanha, motorista)

    with pytest.raises(IntegrityError):
        db.add(
            Reward(
                user_id=motorista.id,
                campaign_id=campanha.id,
                mission_progress_id=progresso.id,
                tipo="cashback_fixo",
                valor_brl=Decimal("5"),
                estado="creditada",  # sem wallet_topup_id
            )
        )
        await db.flush()


# ---------------------------------------------------------------------- push


async def _com_aparelho(db, motorista):
    db.add(PushDevice(user_id=motorista.id, token="ExponentPushToken[teste]", platform="android"))
    await db.flush()


async def test_recompensa_velha_ainda_e_notificada(db, motorista, monkeypatch):
    """A divergencia deliberada em relacao ao push de sessao.

    `IDADE_MAXIMA_MIN` descarta evento de sessao com mais de 30 minutos porque
    "venha buscar o carro" perde valor - o motorista ja foi embora. "Voce ganhou
    R$ 12" nao perde valor nunca. Se alguem aplicar a constante aqui por
    simetria, o motorista deixa de saber do proprio dinheiro e o silencio vai
    parecer intencional.
    """
    await _com_aparelho(db, motorista)
    campanha = await _campanha(db)
    await _missao_cumprida(db, campanha, motorista)
    await campaign_service.conceder_pendentes(db)

    recompensa = (await _recompensas(db, motorista))[0]
    recompensa.created_at = datetime.now(UTC) - timedelta(days=3)
    await db.flush()

    resultado = await notification_service.enviar_recompensas_pendentes(db)

    assert resultado["recompensas"] == 1
    assert resultado["mensagens"] == 1
    await db.refresh(recompensa)
    assert recompensa.notified_at is not None


async def test_falha_no_push_nao_marca_como_avisada(db, motorista, monkeypatch):
    """Marcar aqui transformaria "nao entreguei" em "entreguei", para sempre."""
    await _com_aparelho(db, motorista)
    campanha = await _campanha(db)
    await _missao_cumprida(db, campanha, motorista)
    await campaign_service.conceder_pendentes(db)

    class Quebrado:
        def send(self, mensagens):
            raise PushError("servico fora do ar")

    monkeypatch.setattr(notification_service, "get_sender", lambda: Quebrado())

    resultado = await notification_service.enviar_recompensas_pendentes(db)

    assert resultado["recompensas"] == 0
    assert "erro" in resultado
    recompensa = (await _recompensas(db, motorista))[0]
    assert recompensa.notified_at is None, "a recompensa nunca mais seria avisada"


async def test_recompensa_pendente_nao_e_anunciada(db, motorista):
    """So' se avisa dinheiro que ja esta na carteira."""
    await _com_aparelho(db, motorista)
    campanha = await _campanha(db)
    _missao, progresso = await _missao_cumprida(db, campanha, motorista)
    db.add(
        Reward(
            user_id=motorista.id,
            campaign_id=campanha.id,
            mission_progress_id=progresso.id,
            tipo="cashback_fixo",
            valor_brl=Decimal("5"),
            estado="pendente",
        )
    )
    await db.flush()

    resultado = await notification_service.enviar_recompensas_pendentes(db)
    assert resultado["recompensas"] == 0
