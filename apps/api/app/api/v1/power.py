"""Modulo Gerenciamento de Potencia: orcamento do site, tetos e balanceamento."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.deps import (
    AdminUser,
    Auditor,
    CurrentUser,
    DbSession,
    OperatorUser,
    ScopedSiteId,
)
from app.models.charge_point import ChargePoint, ChargePointConnection
from app.models.enums import ChargePointStatus, SessionState
from app.models.priority_rule import PriorityRule
from app.models.site import Site, SiteMeterReading
from app.schemas.ev import (
    ChargePointCreate,
    ChargePointOut,
    ChargePointUpdate,
    MeterReadingIn,
    PowerBudgetOut,
    PowerBudgetUpdate,
    PowerOverview,
    PowerPlanOut,
    PriorityRuleIn,
    PriorityRuleOut,
    ResolucaoIn,
    SetLimitRequest,
    SiteCreate,
    SiteSettingsOut,
)
from app.services import (
    demand_service,
    maintenance_service,
    portfolio_service,
    power_manager,
    priority_service,
    session_service,
    utilization_service,
)
from app.services.command_service import send_command

router = APIRouter(prefix="/power", tags=["recarga ev · potência"])


async def _points(db, site_id) -> list[ChargePoint]:
    return list(
        (
            await db.execute(
                select(ChargePoint)
                .where(ChargePoint.site_id == site_id)
                .options(selectinload(ChargePoint.connection))
                .order_by(ChargePoint.code)
            )
        )
        .scalars()
        .all()
    )


@router.get("/overview", response_model=PowerOverview)
async def overview(db: DbSession, site_id: ScopedSiteId, _: OperatorUser) -> PowerOverview:
    """Tudo que a tela de potencia precisa em uma chamada."""
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    points = await _points(db, site_id)
    budget = await power_manager.load_budget(db, site)

    # Só conta quem pode efetivamente puxar energia — o mesmo conjunto que o
    # alocador compromete. Somar o limite de pontos ociosos, na fila ou cortados
    # inflava o número com tetos que ninguém está usando e acendia um alarme de
    # "excede a disponibilidade" com o site inteiro tranquilo.
    allocated = sum(float(cp.limit_kw) for cp in points if cp.is_dispatchable)
    current = sum(float(cp.current_kw) for cp in points)
    available = budget.available_kw

    return PowerOverview(
        budget=PowerBudgetOut(**budget.as_dict()),
        settings=SiteSettingsOut.model_validate(site, from_attributes=True),
        allocated_kw=round(allocated, 2),
        current_kw=round(current, 2),
        usage_percent=round(min(100.0, current / available * 100), 1) if available > 0 else 0.0,
        over_budget=allocated > available,
        active_count=sum(1 for cp in points if cp.status == ChargePointStatus.CHARGING),
        total_count=len(points),
        charge_points=[ChargePointOut.model_validate(cp) for cp in points],
    )


@router.get("/budget", response_model=PowerBudgetOut)
async def get_budget(db: DbSession, site_id: ScopedSiteId, _: OperatorUser) -> PowerBudgetOut:
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    return PowerBudgetOut(**(await power_manager.load_budget(db, site)).as_dict())


@router.patch("/budget", response_model=PowerBudgetOut)
async def update_budget(
    payload: PowerBudgetUpdate, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
) -> PowerBudgetOut:
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(site, field, value)
    await db.commit()
    # O orcamento mudou: o rateio precisa ser refeito antes de o operador sair da tela.
    await power_manager.rebalance_site(db, site_id, triggered_by="operator")
    return PowerBudgetOut(**(await power_manager.load_budget(db, site)).as_dict())


@router.post("/meter-readings", status_code=202)
async def push_meter_reading(
    payload: MeterReadingIn, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
) -> dict:
    """Entrada do smart meter / inversor GoodWe.

    Enquanto a API de EV Chargers do SEMS+ nao existe, esta rota e o ponto de
    integracao: um coletor no site empurra as leituras para ca.
    """
    db.add(
        SiteMeterReading(
            site_id=site_id,
            recorded_at=payload.recorded_at or datetime.now(UTC),
            grid_import_kw=payload.grid_import_kw,
            pv_kw=payload.pv_kw,
            battery_kw=payload.battery_kw,
            battery_soc=payload.battery_soc,
            building_load_kw=payload.building_load_kw,
            ev_load_kw=payload.ev_load_kw,
        )
    )
    await db.commit()
    return {"accepted": True}


@router.get("/plan", response_model=PowerPlanOut)
async def preview_plan(db: DbSession, site_id: ScopedSiteId, _: OperatorUser) -> PowerPlanOut:
    """Previa do rateio sem escrever nada no hardware."""
    plan = await power_manager.plan_for_site(db, site_id)
    return PowerPlanOut(**plan.as_dict())


@router.post("/rebalance", response_model=dict)
async def rebalance(
    db: DbSession,
    site_id: ScopedSiteId,
    user: OperatorUser,
    dry_run: bool = Query(default=False, description="calcula e não aplica"),
) -> dict:
    """Redistribuir agora - botao do dashboard."""
    return await power_manager.rebalance_site(
        db, site_id, triggered_by=f"operator:{user.email}", dry_run=dry_run
    )


@router.get("/charge-points", response_model=list[ChargePointOut])
async def list_charge_points(db: DbSession, site_id: ScopedSiteId, _: OperatorUser):
    return await _points(db, site_id)


@router.post("/charge-points", response_model=ChargePointOut, status_code=201)
async def create_charge_point(
    payload: ChargePointCreate, db: DbSession, site_id: ScopedSiteId, _: OperatorUser
):
    exists = (
        await db.execute(
            select(ChargePoint).where(
                ChargePoint.site_id == site_id, ChargePoint.code == payload.code
            )
        )
    ).scalar_one_or_none()
    if exists is not None:
        raise HTTPException(status_code=409, detail="já existe um ponto com esse código")

    cp = ChargePoint(
        site_id=site_id,
        code=payload.code,
        name=payload.name,
        connector=payload.connector,
        phase_type=payload.phase_type,
        rated_kw=payload.rated_kw,
        min_kw=payload.min_kw,
        limit_kw=payload.rated_kw,
        priority=payload.priority,
        tariff_id=payload.tariff_id,
        status=ChargePointStatus.OFFLINE,
    )
    cp.connection = ChargePointConnection(
        protocol=payload.protocol, host=payload.host, port=payload.port, unit_id=payload.unit_id
    )
    db.add(cp)
    await db.commit()
    await db.refresh(cp)
    return cp


@router.patch("/charge-points/{charge_point_id}", response_model=ChargePointOut)
async def update_charge_point(
    charge_point_id: uuid.UUID,
    payload: ChargePointUpdate,
    db: DbSession,
    site_id: ScopedSiteId,
    user: OperatorUser,
):
    cp = await _get_point(db, site_id, charge_point_id)
    data = payload.model_dump(exclude_unset=True)

    # Alterar o teto e um comando de hardware, nao so um UPDATE.
    limit_kw = data.pop("limit_kw", None)
    for field, value in data.items():
        setattr(cp, field, value)
    if limit_kw is not None:
        await _apply_limit(db, cp, limit_kw, user.email)

    await db.commit()
    await db.refresh(cp)
    return cp


@router.post("/charge-points/{charge_point_id}/limit", response_model=ChargePointOut)
async def set_limit(
    charge_point_id: uuid.UUID,
    payload: SetLimitRequest,
    db: DbSession,
    site_id: ScopedSiteId,
    user: OperatorUser,
):
    """Slider de limite por ponto (reg 10029)."""
    cp = await _get_point(db, site_id, charge_point_id)
    await _apply_limit(db, cp, payload.limit_kw, user.email)
    await db.commit()
    await db.refresh(cp)
    return cp


@router.post("/charge-points/{charge_point_id}/throttle", response_model=ChargePointOut)
async def throttle(
    charge_point_id: uuid.UUID,
    db: DbSession,
    site_id: ScopedSiteId,
    user: OperatorUser,
    enabled: bool = Query(default=True),
):
    """Corte de emergencia via reg 10000: derruba para a potencia minima sem encerrar a sessao."""
    cp = await _get_point(db, site_id, charge_point_id)
    result = await send_command(
        db, cp, "set_dispatch_throttle", triggered_by=f"operator:{user.email}", throttled=enabled
    )
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error or "falha ao enviar comando")

    cp.operator_throttled = enabled
    if enabled:
        cp.status = ChargePointStatus.SUSPENDED
    else:
        # Ao liberar, o estado depende de haver sessao em curso. Assumir CHARGING
        # marcava como carregando um ponto ocioso, que entao passava a reservar
        # potencia no rateio sem entregar energia a ninguem. O poller confirma no
        # proximo ciclo; aqui so evitamos o estado impossivel.
        # ACTIVE_SESSION_STATES inclui AUTHORIZING, QUEUED e FINISHING - estados
        # em que o ponto esta ocupado mas nao entrega energia. Marca-lo CHARGING
        # nesses casos torna is_dispatchable verdadeiro e faz o alocador
        # comprometer potencia com quem nao consome: exatamente o que o
        # paragrafo acima diz que esta branch existe para evitar.
        ativa = await session_service.active_session_for(db, cp.id)
        if ativa is None:
            cp.status = ChargePointStatus.AVAILABLE
        elif ativa.state in {
            SessionState.STARTING,
            SessionState.CHARGING,
            SessionState.SUSPENDED,
        }:
            cp.status = ChargePointStatus.CHARGING
        else:
            # AUTHORIZING, QUEUED ou FINISHING: o motorista esta na vaga, mas
            # nada e' entregue. Nem CHARGING - o alocador comprometeria potencia
            # com quem nao consome - nem AVAILABLE, que faria o app anunciar
            # como livre um ponto ocupado e o proximo toque tomar 409.
            # PREPARING diz a verdade, e is_dispatchable ja o exclui do rateio.
            cp.status = ChargePointStatus.PREPARING
    await db.commit()
    await db.refresh(cp)
    return cp


async def _get_point(db, site_id, charge_point_id) -> ChargePoint:
    cp = (
        await db.execute(
            select(ChargePoint)
            .where(ChargePoint.id == charge_point_id, ChargePoint.site_id == site_id)
            .options(selectinload(ChargePoint.connection))
        )
    ).scalar_one_or_none()
    if cp is None:
        raise HTTPException(status_code=404, detail="ponto de recarga não encontrado")
    return cp


async def _apply_limit(db, cp: ChargePoint, limit_kw: float, actor: str) -> None:
    target = max(float(cp.min_kw), min(limit_kw, float(cp.rated_kw)))
    result = await send_command(
        db, cp, "set_power_limit", triggered_by=f"operator:{actor}", kw=target
    )
    if not result.ok:
        raise HTTPException(status_code=502, detail=result.error or "falha ao aplicar limite")
    cp.limit_kw = target
    # Vira teto de politica: o rateio automatico nao sobe acima disso.
    cp.operator_max_kw = target


@router.get("/demand/forecast")
async def demand_forecast(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    horas: int = Query(default=6, ge=1, le=24),
    dias_de_historico: int = Query(default=7, ge=1, le=60),
) -> dict:
    """Projeta a demanda das proximas horas contra o contrato.

    Responde a pergunta que so' aparece na conta do mes seguinte: "com o que
    esta carregando agora, eu estouro a demanda contratada?".
    """
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    previsao = await demand_service.prever_demanda(
        db, site, horizonte_horas=horas, dias_de_historico=dias_de_historico
    )
    return previsao.as_dict()


@router.get("/demand/avoided-cost")
async def demand_avoided_cost(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    dias: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Quanto o rateio poupou de ultrapassagem no periodo."""
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    resultado = await demand_service.custo_evitado(db, site, dias=dias)
    return resultado.as_dict()


@router.get("/demand/contract-simulator")
async def demand_contract_simulator(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    dias: int = Query(default=30, ge=7, le=365),
    passo_kw: float = Query(default=5.0, ge=1.0, le=25.0),
) -> dict:
    """Qual demanda contratar, dado o consumo real medido.

    Contratar demais paga folga o ano todo; de menos, paga ultrapassagem ao
    dobro. O minimo dessa soma so' aparece com a medicao na mao.
    """
    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    return (await demand_service.simular_contrato(db, site, dias=dias, passo_kw=passo_kw)).as_dict()


@router.get("/maintenance/attention")
async def maintenance_attention(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    dias: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Pontos que vem falhando com frequencia, pela recorrencia dos episodios.

    O painel de estado mostra o que esta ruim agora. Este mostra o que vai
    quebrar - um conector que abre "falha da trava" tres vezes na semana ainda
    funciona, e nao vai continuar funcionando.
    """
    return await maintenance_service.pontos_em_atencao(db, site_id, dias=dias)


@router.get("/maintenance/reports")
async def maintenance_reports(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    abertos: bool = Query(default=True),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[dict]:
    """Os problemas que as pessoas reportaram nesta praca.

    `/maintenance/attention` agrupa por categoria e diz QUANTOS estao abertos;
    esta lista diz QUAIS - e' dela que sai o trabalho de quem vai ate o ponto.

    Escopo pelo site do PONTO: `charge_point_reports` nao tem `site_id`, e ler
    sem o JOIN devolveria a reclamacao do vizinho.
    """
    return await maintenance_service.listar_reportes(db, site_id, abertos=abertos, limite=limit)


@router.post("/maintenance/reports/{reporte_id}/resolve")
async def resolve_report(
    reporte_id: uuid.UUID,
    payload: ResolucaoIn,
    db: DbSession,
    site_id: ScopedSiteId,
    operador: OperatorUser,
) -> dict:
    """Fecha o reporte, dizendo o que foi feito.

    Ate aqui nao existia: o motorista reportava, `resolved_at` era LIDO pelo app
    e pelo indice de abertos, e nenhuma rota o escrevia. A fila nunca drenava.

    A descricao do que foi feito e' obrigatoria - fechar sem dizer transforma a
    fila num botao de sumir com a reclamacao.

    QUEM BARRA O MOTORISTA E' `ScopedSiteId`, que ja depende de `OperatorUser` -
    nao a anotacao abaixo. Ela esta aqui pelo VALOR: `resolved_by` precisa de
    quem fechou. O teste de mutacao mostrou isso ao trocar `OperatorUser` por
    `CurrentUser` sem quebrar nada, e a distincao vale escrita: quem ler pode
    achar que removendo a anotacao abre a rota, e nao abre.
    """
    return await maintenance_service.resolver_reporte(
        db, reporte_id, site_id, por=operador, resolucao=payload.resolucao
    )


@router.get("/analytics/daily")
async def analytics_daily(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    dias: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Sessoes, energia e receita de CADA DIA da janela.

    As outras rotas de analise devolvem total de janela, que responde "quanto" e
    nao responde "para onde esta indo" - duas quinzenas com a mesma receita sao
    negocios diferentes se uma sobe e a outra cai.

    Dia sem movimento vem com zero, e nao omitido: serie furada desenha uma linha
    continua por cima do buraco e some justamente com a queda. O agrupamento e'
    pelo fuso do site, senao toda sessao do fim da noite migra de dia.
    """
    from app.services import analytics_service

    return await analytics_service.serie_diaria(db, site_id, dias=dias)


@router.get("/utilization/by-point")
async def utilization_by_point(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    dias: int = Query(default=30, ge=1, le=365),
) -> dict:
    """Ocupacao, receita e ociosidade de cada ponto.

    Responde onde colocar o proximo ponto e onde tirar um: o ranking e por
    receita por hora DISPONIVEL, entao um ponto que passou a semana em falha
    nao aparece como ocioso - aparece com menos horas no denominador.
    """
    return await utilization_service.ocupacao_por_ponto(db, site_id, dias=dias)


# --------------------------------------------------------- regras de prioridade
#
# A prioridade decide quem fica sem carregar quando falta potencia. Ate aqui era
# um inteiro sem nome em charge_points.priority: o operador via "100" e nao tinha
# como saber o que significava, nem por que aquele ponto ficou com esse valor.


@router.get("/priority-rules", response_model=list[PriorityRuleOut])
async def list_priority_rules(db: DbSession, site_id: ScopedSiteId, _: OperatorUser) -> list[dict]:
    return [priority_service.como_dict(r) for r in await priority_service.listar(db, site_id)]


@router.post("/priority-rules", response_model=PriorityRuleOut, status_code=201)
async def create_priority_rule(
    db: DbSession, site_id: ScopedSiteId, _: OperatorUser, payload: PriorityRuleIn
) -> dict:
    regra = PriorityRule(id=uuid.uuid4(), site_id=site_id, **payload.model_dump())
    db.add(regra)
    await db.commit()
    await db.refresh(regra)
    return priority_service.como_dict(regra)


async def _regra_do_site(db: DbSession, regra_id: uuid.UUID, site_id: uuid.UUID) -> PriorityRule:
    """Carrega a regra checando o site no mesmo SELECT.

    404 e nao 403 quando pertence a outro site: responder 403 confirmaria que o
    id existe, e um operador nao precisa saber quais regras o vizinho tem.
    """
    regra = (
        await db.execute(
            select(PriorityRule).where(PriorityRule.id == regra_id, PriorityRule.site_id == site_id)
        )
    ).scalar_one_or_none()
    if regra is None:
        raise HTTPException(status_code=404, detail="regra não encontrada")
    return regra


@router.put("/priority-rules/{regra_id}", response_model=PriorityRuleOut)
async def update_priority_rule(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    regra_id: uuid.UUID,
    payload: PriorityRuleIn,
) -> dict:
    regra = await _regra_do_site(db, regra_id, site_id)
    for campo, valor in payload.model_dump().items():
        setattr(regra, campo, valor)
    await db.commit()
    await db.refresh(regra)
    return priority_service.como_dict(regra)


@router.delete(
    "/priority-rules/{regra_id}", status_code=204, response_class=Response, response_model=None
)
async def delete_priority_rule(
    db: DbSession, site_id: ScopedSiteId, _: OperatorUser, regra_id: uuid.UUID
) -> Response:
    regra = await _regra_do_site(db, regra_id, site_id)
    await db.delete(regra)
    await db.commit()
    return Response(status_code=204)


@router.get("/priority-rules/preview")
async def preview_priority_rules(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    hora: str | None = Query(default=None, description="HH:MM local; padrão = agora"),
) -> dict:
    """Qual regra pegaria cada ponto, no horário informado.

    Existe porque a regra so' se manifesta quando falta potencia - e ai' ja e'
    tarde para descobrir que a janela da frota noturna estava invertida. Aqui o
    operador testa "as 23h, quem tem prioridade?" antes de precisar.
    """
    from datetime import time as _time

    momento: _time | None = None
    if hora:
        try:
            h, m = hora.split(":")
            momento = _time(hour=int(h), minute=int(m))
        except (ValueError, TypeError):
            raise HTTPException(status_code=422, detail="hora deve estar em HH:MM") from None

    site = (await db.execute(select(Site).where(Site.id == site_id))).scalar_one()
    pontos = list(
        (
            await db.execute(
                select(ChargePoint).where(ChargePoint.site_id == site_id).order_by(ChargePoint.code)
            )
        )
        .scalars()
        .all()
    )
    regras = await priority_service.listar(db, site_id)

    if momento is None:
        resolvidas = await priority_service.resolver_para_site(db, site, pontos)
        rotulo = "agora"
    else:
        resolvidas = priority_service.resolver(regras, pontos, agora_local=momento)
        rotulo = hora

    return {
        "hora": rotulo,
        "timezone": site.timezone,
        "regras_ativas": sum(1 for r in regras if r.ativo),
        "pontos": [
            {
                "code": p.code,
                "name": p.name,
                "prioridade_base": int(p.priority),
                "prioridade_efetiva": resolvidas[str(p.id)].prioridade,
                "regra": resolvidas[str(p.id)].regra,
            }
            for p in pontos
        ],
    }


# ------------------------------------------------------------------- multi-site


@router.get("/sites")
async def list_visible_sites(db: DbSession, user: CurrentUser) -> list[dict]:
    """Sites que este usuário pode escolher no seletor do painel.

    Operador recebe só o próprio. A lista também é superfície de informação:
    não adianta o escopo barrar a consulta se o seletor entrega os nomes e as
    cidades da rede inteira.
    """
    return await portfolio_service.sites_visiveis(db, user)


@router.post("/sites", status_code=201)
async def create_site(
    db: DbSession,
    admin: AdminUser,
    aud: Auditor,
    payload: SiteCreate,
) -> dict:
    """Abre uma praca na rede.

    ADMIN, e nao operador: quem opera uma praca nao decide que a rede tem outra.
    E' a mesma fronteira de `/users` - decisao de rede fica com quem administra
    a rede.

    Ate esta rota existir, `Site` so' nascia no `seed()`. A falta aparecia na
    tela, nao no log: seletor de praca e Visao de Rede so' se mostram com mais
    de um site, entao um ambiente real ficava preso ao que o seed criou e a
    promessa multi-praca nao tinha caminho nenhum.

    A praca nasce SEM pontos de recarga, tarifa ou metodo de pagamento - e isso
    e' deliberado. Criar um ponto padrao seria inventar hardware que ninguem
    instalou, e uma tarifa padrao cobraria um preco que ninguem definiu. O
    comissionamento segue por `POST /power/charge-points`.
    """
    criada = await portfolio_service.criar_site(db, payload)
    await aud.registrar(
        db,
        "site.criado",
        "site",
        entidade_id=criada["site_id"],
        depois={"slug": payload.slug, "nome": payload.nome},
    )
    await db.commit()
    return criada


@router.get("/sites/portfolio")
async def sites_portfolio(
    db: DbSession,
    _: AdminUser,
    dias: int = Query(default=30, ge=1, le=365),
) -> dict:
    """As praças lado a lado. Só admin — é a visão da rede, não a de um site."""
    return await portfolio_service.visao_da_rede(db, dias=dias)


@router.get("/demand/energy-forecast/series")
async def demand_energy_forecast_series(
    db: DbSession,
    site_id: ScopedSiteId,
    _: OperatorUser,
    janela: str = Query(default="mes", pattern="^(hora|dia|semana|mes|ano)$"),
    quantos: int | None = Query(default=None, ge=1, le=3360),
) -> dict:
    """A previsao desta praca na janela pedida, em serie.

    A rota irma sem `/series` responde UM numero: o total do proximo mes. Esta
    responde a curva - as proximas 48 horas, os proximos 30 dias, os proximos 12
    meses. As duas coexistem de proposito: a aba de demanda contratada precisa do
    numero unico, e o painel de analise precisa da serie.

    NAO tem janela de HORA por praca com valor pontual util, e a resposta nao
    esconde isso: a celula hora x praca tem 20% de ocupacao contra 54% da rede, e
    a faixa p10-p90 e' o que se entrega ali. Quem quiser a hora com densidade
    pede a rota `/network`.
    """
    from app.services import forecast_service

    return await forecast_service.serie_por_janela(db, janela, site_id, quantos)


@router.get("/demand/energy-forecast/network")
async def demand_energy_forecast_network(
    db: DbSession,
    _: AdminUser,
    janela: str = Query(default="mes", pattern="^(hora|dia|semana|mes|ano)$"),
    quantos: int | None = Query(default=None, ge=1, le=3360),
) -> dict:
    """A previsao da REDE INTEIRA, somando todas as pracas.

    Por que existe: a celula hora x praca tem 20% de ocupacao e 1,26 sessao
    quando ocupada - prever quanto uma praca vende as 15h de uma quarta e' prever
    se um carro especifico aparece. A mesma celula na rede tem 54%, e no plato
    diurno chega a 79% dos dias. A janela de uma hora so' tem sentido aqui.

    ADMINISTRADOR, e nao operador. Nao ha `ScopedSiteId` nesta rota porque nao ha
    site: a linha da rede tem `site_id NULL`. E um total de rede com poucas pracas
    permite inferir o movimento das outras - com duas, por subtracao exata. Quem
    opera uma praca ve' a praca dele.
    """
    from app.services import forecast_service

    return await forecast_service.serie_por_janela(db, janela, None, quantos)


@router.get("/demand/energy-forecast")
async def demand_energy_forecast(db: DbSession, site_id: ScopedSiteId, _: OperatorUser) -> dict:
    """Quanto este site deve VENDER no proximo mes, em kWh e em reais.

    A aba ja responde "quanto vou puxar" - kW, contrato, custo evitado. Isto
    responde "quanto vou vender", e as duas alimentam a MESMA decisao: quanta
    demanda contratar. Por isso mora aqui e nao numa aba propria.

    A API so' LE: quem escreve e' o job de `apps/forecast`, que roda fora do
    processo da API. Sem linha para a competencia, a resposta e' `disponivel:
    false` - e a tela diz que nao ha previsao, em vez de inventar um numero.

    Seguranca: filtra por `site_id` do escopo, que para operador comum e' sempre
    o site dele, independentemente do que a query pedir.
    """
    from app.services import forecast_service

    return await forecast_service.previsao_do_site(db, site_id)
