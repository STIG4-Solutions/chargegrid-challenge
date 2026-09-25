"""Motor de tarifacao.

A cobranca nao pode ser um simples kWh x preco: uma sessao das 17h40 as 19h20
atravessa a fronteira ponta/fora-de-ponta, e o cliente precisa pagar cada trecho
pelo preco vigente. Por isso o motor rateia energia e tempo sobre as amostras de
telemetria, atribuindo cada pedaco a janela tarifaria daquele instante.

Toda a aritmetica usa Decimal - float em dinheiro acumula erro de centavo.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

from app.models.session import ChargingSession
from app.models.tariff import Tariff, TariffWindow
from app.models.telemetry import TelemetrySample

CENTS = Decimal("0.01")
UNIT = Decimal("0.0001")


def money(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(CENTS, rounding=ROUND_HALF_UP)


def qty(value: Decimal | float | int) -> Decimal:
    return Decimal(str(value)).quantize(UNIT, rounding=ROUND_HALF_UP)


@dataclass(slots=True)
class RatedLine:
    kind: str
    description: str
    quantity: Decimal
    unit: str
    unit_price: Decimal
    amount: Decimal


@dataclass(slots=True)
class Beneficio:
    """Vantagem que o pagador leva para esta sessao, ja resolvida.

    O motor NAO descobre quem tem direito a que: isso depende de assinatura
    ativa e de campanha vigente, e as duas moram no banco. `rate_session` e' uma
    funcao pura sobre (sessao, tarifa, amostras), e e' essa pureza que torna
    `test_tariff_engine.py` possivel sem subir Postgres. Quem consulta o banco e
    monta este objeto e' o `billing_service`, que ja tem a sessao aberta.

    `rotulo` vai para a descricao da linha na fatura e no recibo: "Plano Mensal"
    diz ao motorista de onde veio o abatimento; "Desconto" sozinho nao diz.
    """

    rotulo: str
    desconto_pct: Decimal = Decimal("0")
    kwh_inclusos: Decimal = Decimal("0")
    isenta_session_fee: bool = False


@dataclass(slots=True)
class RatingResult:
    lines: list[RatedLine] = field(default_factory=list)
    subtotal: Decimal = Decimal("0.00")
    # Soma dos abatimentos, em modulo. A fatura documenta `total = subtotal -
    # discount` desde a primeira migration, e ate agora nada preenchia o campo:
    # a conta fechava porque o desconto era sempre zero.
    desconto: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")
    energy_kwh: Decimal = Decimal("0")
    billable_minutes: int = 0
    idle_minutes: int = 0
    tariff_snapshot: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "subtotal": float(self.subtotal),
            "desconto": float(self.desconto),
            "total": float(self.total),
            "energy_kwh": float(self.energy_kwh),
            "billable_minutes": self.billable_minutes,
            "idle_minutes": self.idle_minutes,
            "lines": [
                {
                    "kind": line.kind,
                    "description": line.description,
                    "quantity": float(line.quantity),
                    "unit": line.unit,
                    "unit_price": float(line.unit_price),
                    "amount": float(line.amount),
                }
                for line in self.lines
            ],
            "tariff_snapshot": self.tariff_snapshot,
        }


@dataclass(slots=True)
class _Rates:
    """Precos vigentes em um instante, ja resolvidos janela x tarifa base."""

    label: str
    per_kwh: Decimal
    per_min: Decimal
    idle_per_min: Decimal


def resolve_rates(tariff: Tariff, moment_local: datetime) -> _Rates:
    """Primeira janela que casa vence; sem janela, valem os precos base da tarifa."""
    window: TariffWindow | None = next((w for w in tariff.windows if w.matches(moment_local)), None)
    if window is None:
        # Nenhuma janela cobre este instante: vale o preco base da tarifa. O
        # rotulo marca isso para nao parecer que uma janela foi aplicada.
        return _Rates(
            label=f"{tariff.name} (padrão)",
            per_kwh=Decimal(str(tariff.price_per_kwh)),
            per_min=Decimal(str(tariff.price_per_min)),
            idle_per_min=Decimal(str(tariff.idle_fee_per_min)),
        )
    return _Rates(
        label=window.label or tariff.name,
        per_kwh=Decimal(str(window.price_per_kwh)),
        per_min=Decimal(str(window.price_per_min)),
        idle_per_min=Decimal(str(window.idle_fee_per_min)),
    )


def _split_energy_by_window(
    tariff: Tariff, samples: list[TelemetrySample], tz: ZoneInfo
) -> dict[str, tuple[Decimal, Decimal]]:
    """Rateia a energia da sessao entre janelas: {label: (kWh, preco_kwh)}.

    Usa o incremento entre amostras consecutivas do contador da sessao (reg 10016)
    e atribui cada incremento a janela vigente no instante da amostra.
    """
    buckets: dict[str, list] = {}
    previous = None
    for sample in samples:
        energy = Decimal(str(sample.session_energy_kwh or 0))
        if previous is not None:
            delta = energy - previous
            # Contador zerado (reg 10176) ou ruido: ignora o degrau negativo.
            if delta > 0:
                rates = resolve_rates(tariff, sample.recorded_at.astimezone(tz))
                entry = buckets.setdefault(rates.label, [Decimal("0"), rates.per_kwh])
                entry[0] += delta
        previous = energy
    return {label: (value, price) for label, (value, price) in buckets.items()}


def _split_minutes_by_window(
    tariff: Tariff, start: datetime, end: datetime, tz: ZoneInfo, attr: str
) -> dict[str, tuple[int, Decimal]]:
    """Rateia minutos entre janelas caminhando de minuto em minuto.

    O passo de 1 minuto e a granularidade de cobranca e limita o laco a 1440
    iteracoes por dia de sessao - custo irrelevante e resultado exato na virada.
    """
    buckets: dict[str, list] = {}
    if end <= start:
        return {}
    cursor = start
    while cursor < end:
        rates = resolve_rates(tariff, cursor.astimezone(tz))
        price = getattr(rates, attr)
        entry = buckets.setdefault(rates.label, [0, price])
        entry[0] += 1
        cursor += timedelta(minutes=1)
    return {label: (minutes, price) for label, (minutes, price) in buckets.items()}


def multiplicador_efetivo(session: ChargingSession, tariff: Tariff) -> tuple[Decimal, str]:
    """O multiplicador que vale para esta sessao, e de onde ele veio.

    O travado na sessao (a bandeira do site no inicio da recarga) vence sempre,
    mesmo em tarifa com o dinamico desligado: a bandeira vale para a praca toda.
    Sem ele - sessao anterior a feature, ou flag desligada - vale a regra antiga,
    o multiplicador digitado na tarifa, e so' quando ela o habilita.
    """
    if session.multiplicador_travado is not None:
        return Decimal(str(session.multiplicador_travado)), "bandeira"
    if tariff.dynamic_enabled:
        return Decimal(str(tariff.dynamic_multiplier or 1)), "tarifa"
    return Decimal("1"), "tarifa"


def rate_session(
    session: ChargingSession,
    tariff: Tariff,
    samples: list[TelemetrySample],
    *,
    timezone: str = "America/Sao_Paulo",
    idle_grace_minutes: int = 10,
    now: datetime | None = None,
    beneficio: Beneficio | None = None,
) -> RatingResult:
    """Calcula o valor de uma sessao. Serve tanto para previa quanto para faturar.

    `beneficio` e' opcional e, quando ausente, o resultado e' o de sempre: nao ha
    linha negativa, `desconto` fica zero e `total` sai identico ao que saia antes
    de este parametro existir. E' o contrato que permite mexer no caminho do
    dinheiro tendo os testes existentes como rede.
    """
    tz = ZoneInfo(timezone)
    now = now or datetime.now(UTC)
    result = RatingResult()

    start = session.started_at or session.authorized_at or now
    end = session.ended_at or now
    charging_end = session.charging_stopped_at or end

    # ---------------------------------------------------------------- energia
    energy_buckets = _split_energy_by_window(tariff, samples, tz)
    measured = sum(value for value, _ in energy_buckets.values())
    total_energy = Decimal(str(session.energy_kwh or 0))

    if not energy_buckets and total_energy > 0:
        # Sem telemetria (ex.: importacao do registro do proprio ponto):
        # aplica o preco vigente no inicio da sessao.
        rates = resolve_rates(tariff, start.astimezone(tz))
        energy_buckets = {rates.label: (total_energy, rates.per_kwh)}
    elif measured > 0 and total_energy > measured:
        # A telemetria pode ter perdido amostras; a diferenca vai para a janela
        # do encerramento, que e onde o contador final foi lido.
        rates = resolve_rates(tariff, charging_end.astimezone(tz))
        value, price = energy_buckets.get(rates.label, (Decimal("0"), rates.per_kwh))
        energy_buckets[rates.label] = (value + (total_energy - measured), price)

    for label, (kwh, price) in sorted(energy_buckets.items()):
        if kwh <= 0:
            continue
        result.energy_kwh += kwh
        if price <= 0:
            continue
        result.lines.append(
            RatedLine(
                kind="energy",
                description=f"Energia — {label}",
                quantity=qty(kwh),
                unit="kWh",
                unit_price=qty(price),
                amount=money(kwh * price),
            )
        )

    # ------------------------------------------------------------------ tempo
    free = timedelta(minutes=tariff.free_minutes or 0)
    billable_start = min(start + free, charging_end)
    time_buckets = _split_minutes_by_window(tariff, billable_start, charging_end, tz, "per_min")
    for label, (minutes, price) in sorted(time_buckets.items()):
        result.billable_minutes += minutes
        if price <= 0 or minutes <= 0:
            continue
        result.lines.append(
            RatedLine(
                kind="time",
                description=f"Tempo de recarga — {label}",
                quantity=qty(minutes),
                unit="min",
                unit_price=qty(price),
                amount=money(Decimal(minutes) * price),
            )
        )

    # -------------------------------------------------------------- ociosidade
    # Cobrada so depois da tolerancia: o motorista precisa de uma janela justa
    # para voltar ao carro. E o que destrava a vaga em estabelecimento comercial.
    idle_start = charging_end + timedelta(minutes=idle_grace_minutes)
    idle_buckets = _split_minutes_by_window(tariff, idle_start, end, tz, "idle_per_min")
    for label, (minutes, price) in sorted(idle_buckets.items()):
        result.idle_minutes += minutes
        if price <= 0 or minutes <= 0:
            continue
        result.lines.append(
            RatedLine(
                kind="idle",
                description=f"Ociosidade após {idle_grace_minutes} min — {label}",
                quantity=qty(minutes),
                unit="min",
                unit_price=qty(price),
                amount=money(Decimal(minutes) * price),
            )
        )

    # ------------------------------------------------------- taxas e minimos
    session_fee = Decimal(str(tariff.session_fee or 0))
    # A isencao SUPRIME a linha, em vez de descontar o mesmo valor depois. A
    # diferenca aparece quando ha valor minimo: descontada no fim, a taxa voltaria
    # embutida no complemento ate o minimo, e o assinante pagaria de novo por uma
    # isencao que o app ja lhe prometeu.
    if session_fee > 0 and not (beneficio and beneficio.isenta_session_fee):
        result.lines.append(
            RatedLine(
                kind="session_fee",
                description="Taxa de conexão",
                quantity=Decimal("1"),
                unit="un",
                unit_price=qty(session_fee),
                amount=money(session_fee),
            )
        )

    # ------------------------------------------------------- kWh do plano
    # Abate da janela MAIS CARA primeiro. Comecar pela mais barata entregaria ao
    # assinante o pior uso possivel da franquia dele - e ele nao escolhe a ordem.
    #
    # Vira linha propria negativa em vez de reduzir a quantidade da linha de
    # energia: o recibo precisa continuar dizendo quanta energia foi entregue.
    # Um recibo que mostra 8 kWh numa recarga de 30 kWh nao serve para prestacao
    # de contas, e e' o documento que a empresa do motorista recebe.
    if beneficio and beneficio.kwh_inclusos > 0 and energy_buckets:
        restante = beneficio.kwh_inclusos
        abatido = Decimal("0")
        valor_abatido = Decimal("0")
        for _label, (kwh, price) in sorted(
            energy_buckets.items(), key=lambda item: item[1][1], reverse=True
        ):
            if restante <= 0:
                break
            if kwh <= 0 or price <= 0:
                continue
            usado = min(kwh, restante)
            restante -= usado
            abatido += usado
            valor_abatido += usado * price
        if valor_abatido > 0:
            result.lines.append(
                RatedLine(
                    kind="plano",
                    description=f"{beneficio.rotulo} — {qty(abatido)} kWh inclusos",
                    quantity=qty(abatido),
                    unit="kWh",
                    unit_price=qty(valor_abatido / abatido),
                    amount=-money(valor_abatido),
                )
            )

    # O subtotal soma apenas o que se cobra; os abatimentos sao contados a parte,
    # em `desconto`. E' o que faz `total = subtotal - desconto` valer sempre, que
    # e' o que a fatura documenta desde a primeira migration.
    result.subtotal = money(
        sum((line.amount for line in result.lines if line.amount > 0), Decimal("0"))
    )

    # Precificacao dinamica: o multiplicador vem da bandeira do site, travado na
    # sessao no inicio da recarga (`multiplicador_efetivo`).
    multiplier, origem = multiplicador_efetivo(session, tariff)
    if multiplier != 1:
        adjustment = money(result.subtotal * (multiplier - 1))
        if adjustment != 0:
            result.lines.append(
                RatedLine(
                    kind="dynamic",
                    description=(
                        f"Bandeira {session.cor_travada} (x{multiplier:.2f})".replace(".", ",")
                        if origem == "bandeira"
                        else f"Ajuste dinâmico de demanda (x{multiplier})"
                    ),
                    quantity=Decimal("1"),
                    unit="un",
                    unit_price=adjustment,
                    amount=adjustment,
                )
            )
            # Multiplicador abaixo de 1 e' reducao de preco, e entra em
            # `desconto` como qualquer outro abatimento - o subtotal segue sendo
            # o que se cobra antes de reduzir.
            if adjustment > 0:
                result.subtotal = money(result.subtotal + adjustment)

    # O minimo e' comparado ao BRUTO, antes dos abatimentos. Ele existe para que
    # uma sessao de dois minutos nao saia de graca - nao para retomar do
    # assinante a franquia que o plano dele acabou de conceder.
    min_charge = Decimal(str(tariff.min_charge or 0))
    if min_charge > 0 and result.subtotal < min_charge and result.energy_kwh > 0:
        complement = money(min_charge - result.subtotal)
        result.lines.append(
            RatedLine(
                kind="min_charge",
                description="Complemento até o valor mínimo",
                quantity=Decimal("1"),
                unit="un",
                unit_price=complement,
                amount=complement,
            )
        )
        result.subtotal = money(min_charge)

    # O percentual vem por ultimo, sobre o subtotal ja ajustado. Aplicado antes
    # do ajuste dinamico, o assinante pagaria MAIS caro pelo mesmo desconto em
    # horario de pico - o inverso do que o plano anuncia.
    if beneficio and beneficio.desconto_pct > 0:
        valor = money(result.subtotal * beneficio.desconto_pct / Decimal("100"))
        if valor > 0:
            result.lines.append(
                RatedLine(
                    kind="desconto",
                    description=f"{beneficio.rotulo} — {qty(beneficio.desconto_pct)}%",
                    quantity=Decimal("1"),
                    unit="un",
                    unit_price=-valor,
                    amount=-valor,
                )
            )

    result.desconto = money(
        sum((-line.amount for line in result.lines if line.amount < 0), Decimal("0"))
    )
    # O desconto PODE deixar o total abaixo do minimo, e isso e' deliberado. Se o
    # complemento fosse recalculado aqui no fim, um assinante com 20% numa sessao
    # pequena pagaria exatamente o mesmo que quem nao assina nada - depois de a
    # tela do app ja ter anunciado o desconto a ele.
    total = result.subtotal - result.desconto

    result.total = money(total)
    result.tariff_snapshot = {
        "tariff_id": str(tariff.id),
        "name": tariff.name,
        "type": str(tariff.type),
        "currency": tariff.currency,
        "price_per_kwh": float(tariff.price_per_kwh),
        "price_per_min": float(tariff.price_per_min),
        "idle_fee_per_min": float(tariff.idle_fee_per_min),
        "session_fee": float(tariff.session_fee),
        "min_charge": float(tariff.min_charge),
        "free_minutes": tariff.free_minutes,
        "dynamic_multiplier": float(tariff.dynamic_multiplier),
        "dynamic_enabled": tariff.dynamic_enabled,
        "multiplicador_aplicado": float(multiplier),
        "origem_do_multiplicador": origem,
        "idle_grace_minutes": idle_grace_minutes,
        "windows": [
            {
                "label": w.label,
                "day_mask": w.day_mask,
                "starts_at": w.starts_at.isoformat(),
                "ends_at": w.ends_at.isoformat(),
                "price_per_kwh": float(w.price_per_kwh),
                "price_per_min": float(w.price_per_min),
                "idle_fee_per_min": float(w.idle_fee_per_min),
            }
            for w in tariff.windows
        ],
    }
    return result


def simulate(
    tariff: Tariff,
    *,
    energy_kwh: float,
    minutes: int,
    idle_minutes: int = 0,
    at: datetime | None = None,
    timezone: str = "America/Sao_Paulo",
) -> RatingResult:
    """Simulador do dashboard: precifica um cenario hipotetico sem criar sessao."""
    tz = ZoneInfo(timezone)
    moment = (at or datetime.now(UTC)).astimezone(tz)
    rates = resolve_rates(tariff, moment)
    result = RatingResult()

    if energy_kwh > 0 and rates.per_kwh > 0:
        amount = Decimal(str(energy_kwh)) * rates.per_kwh
        result.lines.append(
            RatedLine(
                "energy",
                f"Energia — {rates.label}",
                qty(energy_kwh),
                "kWh",
                qty(rates.per_kwh),
                money(amount),
            )
        )
    billable = max(0, minutes - (tariff.free_minutes or 0))
    if billable > 0 and rates.per_min > 0:
        amount = Decimal(billable) * rates.per_min
        result.lines.append(
            RatedLine(
                "time",
                f"Tempo — {rates.label}",
                qty(billable),
                "min",
                qty(rates.per_min),
                money(amount),
            )
        )
    if idle_minutes > 0 and rates.idle_per_min > 0:
        amount = Decimal(idle_minutes) * rates.idle_per_min
        result.lines.append(
            RatedLine(
                "idle",
                "Ociosidade",
                qty(idle_minutes),
                "min",
                qty(rates.idle_per_min),
                money(amount),
            )
        )
    if tariff.session_fee and Decimal(str(tariff.session_fee)) > 0:
        fee = Decimal(str(tariff.session_fee))
        result.lines.append(
            RatedLine("session_fee", "Taxa de conexão", Decimal("1"), "un", qty(fee), money(fee))
        )

    result.energy_kwh = qty(energy_kwh)
    result.billable_minutes = billable
    result.idle_minutes = idle_minutes
    result.subtotal = money(sum((line.amount for line in result.lines), Decimal("0")))

    multiplier = Decimal(str(tariff.dynamic_multiplier or 1))
    if tariff.dynamic_enabled and multiplier != 1:
        result.subtotal = money(result.subtotal * multiplier)
    min_charge = Decimal(str(tariff.min_charge or 0))
    result.total = money(max(result.subtotal, min_charge) if energy_kwh > 0 else result.subtotal)
    return result
