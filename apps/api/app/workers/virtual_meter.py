"""Medidor virtual do site.

O desafio pede gerenciamento de potencia "com base no medidor", mas nao ha
smart meter fisico ligado a esta instalacao. Este worker ocupa esse lugar:
gera leituras plausiveis na mesma tabela que um medidor real alimentaria
(`site_meter_readings`), no mesmo intervalo, pelos mesmos campos.

Nada mais no sistema sabe que a origem e' sintetica. O power_manager le a
leitura mais recente sem perguntar de onde veio, e trocar por um coletor
Modbus de verdade e' substituir este arquivo - nao mexer no dominio.

A curva e' determinada pela hora do dia, nao aleatoria: a geracao solar sobe
de manha, satura ao meio-dia e zera a noite, e o predio consome mais em
horario comercial. Assim o painel conta uma historia coerente ao longo do dia
em vez de oscilar sem sentido.
"""

from __future__ import annotations

import math
import random
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.core.config import get_settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models.charge_point import ChargePoint
from app.models.site import Site, SiteMeterReading

log = get_logger(__name__)


def _hora_local(agora: datetime, fuso: str | None) -> float:
    """Hora do dia com fracao (13.5 = 13h30), no fuso do site.

    O deslocamento era um inteiro cravado (-3). Funcionava para Sao Paulo e
    para mais nenhum lugar: um site em outro fuso teria a curva solar deslocada,
    com o pico de geracao fora do meio-dia dele. O resto do sistema ja resolve
    fuso por site - a tarifacao inclusive -, e agora este tambem.
    """
    local = agora.astimezone(ZoneInfo(fuso or "America/Sao_Paulo"))
    return local.hour + local.minute / 60 + local.second / 3600


def geracao_solar_kw(hora: float, pico_kw: float) -> float:
    """Meia senoide entre o nascer e o por do sol; zero fora disso."""
    nascer, por = 6.0, 18.0
    if not nascer <= hora <= por:
        return 0.0
    fase = (hora - nascer) / (por - nascer)
    return round(pico_kw * math.sin(math.pi * fase), 2)


def carga_do_predio_kw(hora: float, base_kw: float) -> float:
    """Consumo nao-EV: patamar noturno com platô em horario comercial."""
    if 8 <= hora < 18:
        fator = 1.0
    elif 6 <= hora < 8 or 18 <= hora < 22:
        fator = 0.65
    else:
        fator = 0.35
    return round(base_kw * fator, 2)


def bateria_kw(
    hora: float, solar: float, predio: float, capacidade_kw: float
) -> tuple[float, float]:
    """Descarrega no pico da tarifa, carrega com sobra de sol. (kw, soc)."""
    # Ponta local 18h-21h: a bateria entra para segurar o pico.
    if 18 <= hora < 21:
        return round(capacidade_kw, 2), 45.0
    sobra = solar - predio
    if sobra > 2:
        # Carregando: potencia negativa nao entra no orcamento como fonte.
        return 0.0, min(95.0, 50.0 + sobra)
    return 0.0, 60.0


async def gerar_leitura() -> dict:
    """Grava uma leitura para cada site. Uma execucao do laco."""
    agora = datetime.now(UTC)
    registros = 0

    async with SessionLocal() as db:
        sites = (await db.execute(select(Site))).scalars().all()
        for site in sites:
            # Cada site tem o seu meio-dia.
            hora = _hora_local(agora, site.timezone)
            # Escala as curvas pelo porte do site, para nao inventar um solar
            # de 40 kW num condominio com um ponto de 7 kW.
            teto = float(site.grid_limit_kw or 75)
            solar = geracao_solar_kw(hora, pico_kw=teto * 0.5)
            predio = carga_do_predio_kw(hora, base_kw=teto * 0.25)
            bat_kw, soc = bateria_kw(hora, solar, predio, capacidade_kw=teto * 0.16)

            # Ruido pequeno: um medidor real nunca repete o mesmo numero.
            solar = max(0.0, round(solar * random.uniform(0.94, 1.04), 2))
            predio = max(0.0, round(predio * random.uniform(0.95, 1.05), 2))

            ev = (
                (
                    await db.execute(
                        select(ChargePoint.current_kw).where(ChargePoint.site_id == site.id)
                    )
                )
                .scalars()
                .all()
            )
            ev_kw = round(sum(float(v or 0) for v in ev), 2)

            # O que falta depois do sol e da bateria vem da rede.
            rede = max(0.0, round(predio + ev_kw - solar - bat_kw, 2))

            db.add(
                SiteMeterReading(
                    site_id=site.id,
                    recorded_at=agora,
                    grid_import_kw=rede,
                    pv_kw=solar,
                    battery_kw=bat_kw,
                    battery_soc=soc,
                    building_load_kw=predio,
                    ev_load_kw=ev_kw,
                )
            )
            registros += 1
        await db.commit()

    log.debug("virtual_meter.tick", sites=registros, hora_local=round(hora, 2))
    return {"sites": registros}


def habilitado() -> bool:
    return get_settings().meter_source == "virtual"
