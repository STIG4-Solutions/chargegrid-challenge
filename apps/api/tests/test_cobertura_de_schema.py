"""Toda coluna de modelo ou aparece na resposta, ou tem motivo declarado.

Este arquivo existe por causa de um defeito que apareceu tres vezes:

  `AllocationOut` sem o campo `regra` - o rateio decidia a faixa pela regra
  nomeada, gravava, e o painel nunca soube qual regra tinha decidido.

  `SessionOut` sem os limites - o motorista definia "pare em 30 kWh" e depois
  nao via aquilo em lugar nenhum, o que e' o mesmo que nao confiar no limite.

  `UserOut` sem `fleet_manager` - o app nao tinha como decidir se mostrava a
  aba de frota.

Nos tres o modelo tinha o campo, o servico preenchia, e o schema Pydantic o
descartava em silencio na serializacao. Nenhum gerou erro, log ou aviso. Todos
foram encontrados porque um teste de camada HTTP falhou por outro motivo.

A guarda aqui NAO e "o schema tem de expor tudo" - varias omissoes sao
deliberadas e algumas sao obrigatorias, como `hashed_password`. E' que cada
coluna ausente precisa estar declarada abaixo, com o motivo. Adicionar coluna
ao modelo passa a exigir uma DECISAO: expor, ou dizer por que nao. O silencio
deixa de ser uma opcao, que era exatamente o que permitia os tres casos acima.
"""

from sqlalchemy import inspect

from app.models.billing import Invoice, InvoiceLine, Payment, SitePaymentMethod
from app.models.charge_point import ChargePoint
from app.models.reservation import Reservation
from app.models.session import ChargingSession, SessionEvent
from app.models.tariff import Tariff, TariffWindow
from app.models.user import RfidCard, User, Vehicle
from app.schemas import auth as A
from app.schemas import ev as E

# Motivos que se repetem, para a tabela abaixo nao virar copia e cola.
AUDITORIA = "carimbo de auditoria; nao e' informacao de produto"
PAI = "o recurso pai ja identifica o vinculo; repetir seria ruido"
ESCOPO = "o escopo vem do token, entao o cliente nunca precisa do id do site"
INTERNO = "estado interno do servidor; o cliente nao age sobre ele"

# Ausencias da sessao, compartilhadas por SessionOut e SessionDetail.
SESSAO_OMITE = {
    "site_id": ESCOPO,
    "vehicle_id": "o app ja sabe qual carro escolheu ao iniciar",
    "rfid_card_id": "carga por cartao nao aparece no app do motorista",
    "reservation_id": "o agendamento vira sessao e a tela ja trocou de contexto",
    "meter_start_kwh": "leitura crua do medidor; `energy_kwh` e' a diferenca ja calculada",
    "meter_stop_kwh": "idem",
    "charging_stopped_at": "insumo do calculo de ociosidade, que sai pronto em `idle_minutes`",
    "created_at": AUDITORIA,
    "updated_at": AUDITORIA,
}

# Coluna ausente do schema -> por que esta ausente.
#
# Trocar um motivo por "nao sei" e' pior que deixar em branco: quem vier
# depois trata o texto como decisao tomada.
OMISSOES = {
    (User, A.UserOut): {
        "hashed_password": "NUNCA expor - e o segredo da conta",
        "last_login_at": INTERNO,
        "updated_at": AUDITORIA,
    },
    (Vehicle, A.VehicleOut): {
        "user_id": "a rota so' devolve os carros do proprio usuario",
        "created_at": AUDITORIA,
        "updated_at": AUDITORIA,
    },
    (RfidCard, A.RfidCardOut): {
        "site_id": ESCOPO,
        "created_at": AUDITORIA,
        "updated_at": AUDITORIA,
    },
    (ChargePoint, E.ChargePointOut): {
        "site_id": ESCOPO,
        "last_fault_code": "o codigo cru do registrador; `active_faults` traz os rotulos legiveis",
        "created_at": AUDITORIA,
        "updated_at": AUDITORIA,
    },
    (SessionEvent, E.SessionEventOut): {
        "id": "o evento e' um item da linha do tempo, nao um recurso enderecavel",
        "session_id": PAI,
        "notified_at": "marca do outbox de push; e' controle do worker, nao do cliente",
    },
    # SessionDetail herda SessionOut, entao herda as mesmas ausencias. Uma
    # constante evita que as duas listas divirjam com o tempo.
    (ChargingSession, E.SessionOut): SESSAO_OMITE,
    (ChargingSession, E.SessionDetail): SESSAO_OMITE,
    (TariffWindow, E.TariffWindowOut): {
        "tariff_id": PAI,
    },
    (Tariff, E.TariffOut): {
        "site_id": ESCOPO,
        "created_at": AUDITORIA,
        "updated_at": AUDITORIA,
    },
    (SitePaymentMethod, E.PaymentMethodOut): {
        "site_id": ESCOPO,
        "provider_config": "NUNCA expor - guarda credencial e segredo de webhook do PSP",
        "created_at": AUDITORIA,
        "updated_at": AUDITORIA,
    },
    (InvoiceLine, E.InvoiceLineOut): {
        "id": "a linha e' item da fatura, nao um recurso enderecavel",
        "invoice_id": PAI,
    },
    (Payment, E.PaymentOut): {
        "invoice_id": PAI,
        "idempotency_key": "NUNCA expor - conhece-la permite forjar a retentativa de outro",
        "raw_response": "NUNCA expor - resposta crua do PSP, pode conter dado de portador",
        "authorized_at": (
            "o par autorizacao/captura e' detalhe do PSP; `status` resume o que importa"
        ),
        "captured_at": "idem",
        "updated_at": AUDITORIA,
    },
    (Invoice, E.InvoiceOut): {
        "site_id": ESCOPO,
        "due_at": "cobranca com prazo ainda nao existe; entra quando existir",
        "tariff_snapshot": "a tarifa congelada alimenta o recibo, que tem rota propria",
        "created_at": AUDITORIA,
        "updated_at": AUDITORIA,
    },
    (Reservation, E.ReservationOut): {
        "site_id": ESCOPO,
        "vehicle_id": "o app ja sabe qual carro agendou",
        "cancelled_at": "`status` ja diz que foi cancelado, e a tela nao mostra quando",
        "pushed_to_hardware": INTERNO,
        "created_at": AUDITORIA,
        "updated_at": AUDITORIA,
    },
}

# Nomes que nao podem aparecer em NENHUM schema de resposta. E a guarda no
# sentido contrario: a tabela acima protege contra esquecer de expor, esta
# protege contra expor sem querer.
JAMAIS_EXPOR = {
    "hashed_password",
    "provider_config",
    "raw_response",
    "idempotency_key",
    "payment_webhook_secret",
    "webhook_secret",
    "secret_key",
}


def _colunas(modelo) -> set[str]:
    return {c.key for c in inspect(modelo).columns}


def test_toda_coluna_esta_exposta_ou_justificada():
    """O teste que os tres defeitos teriam pego.

    Coluna nova no modelo, sem campo no schema e sem entrada em OMISSOES,
    quebra aqui - com o nome dela na mensagem. A correcao e' uma decisao de
    uma linha: expor, ou dizer por que nao.
    """
    faltando: list[str] = []
    for (modelo, schema), justificadas in OMISSOES.items():
        ausentes = _colunas(modelo) - set(schema.model_fields) - set(justificadas)
        faltando += [
            f"{modelo.__name__}.{campo} nao esta em {schema.__name__} nem em OMISSOES"
            for campo in sorted(ausentes)
        ]

    assert not faltando, (
        "Coluna de modelo que a resposta descarta em silencio:\n  "
        + "\n  ".join(faltando)
        + "\n\nExponha no schema, ou declare em OMISSOES com o motivo."
    )


def test_nenhuma_justificativa_ficou_orfa():
    """Entrada obsoleta transforma a tabela em decoracao.

    Se a coluna sumiu do modelo - ou passou a ser exposta -, a justificativa
    para de proteger qualquer coisa e passa a mentir sobre o estado atual.
    """
    orfas: list[str] = []
    for (modelo, schema), justificadas in OMISSOES.items():
        colunas = _colunas(modelo)
        campos = set(schema.model_fields)
        for campo in sorted(justificadas):
            if campo not in colunas:
                orfas.append(f"{modelo.__name__}.{campo} nao existe mais no modelo")
            elif campo in campos:
                orfas.append(
                    f"{modelo.__name__}.{campo} agora ESTA em {schema.__name__}; "
                    "remova a justificativa"
                )
    assert not orfas, "Justificativas desatualizadas:\n  " + "\n  ".join(orfas)


def test_todo_schema_de_orm_esta_na_tabela():
    """Schema de resposta novo entra na verificação, não passa por fora.

    Sem isto, a proteção cobriria só o que alguém lembrou de listar — e o
    próximo schema nasceria com a mesma brecha dos três anteriores.
    """
    from app.schemas.common import ORMModel

    declarados = {schema for _, schema in OMISSOES}
    # Pares sem nenhuma omissão são legítimos e não precisam de entrada em
    # OMISSOES; por isso a checagem aceita ausência quando o schema cobre tudo.
    conhecidos = declarados | {E.AllocationOut}

    descobertos = {
        obj
        for modulo in (A, E)
        for obj in vars(modulo).values()
        if isinstance(obj, type) and issubclass(obj, ORMModel) and obj is not ORMModel
    }
    fora = sorted(s.__name__ for s in descobertos - conhecidos)
    assert not fora, (
        "Schema que lê de ORM e ficou fora da verificação: "
        + ", ".join(fora)
        + "\nAdicione o par (Modelo, Schema) em OMISSOES."
    )


def test_nenhum_segredo_vaza_por_schema():
    """A guarda no sentido contrário: expor sem querer.

    Um campo com esses nomes numa resposta não é decisão de produto — é
    vazamento. `provider_config` guarda credencial do PSP; `raw_response` pode
    trazer dado de portador; `idempotency_key` conhecida permite forjar a
    retentativa de outra pessoa.
    """
    from app.schemas.common import ORMModel

    vazando: list[str] = []
    for modulo in (A, E):
        for nome, obj in vars(modulo).items():
            if not (isinstance(obj, type) and issubclass(obj, ORMModel)):
                continue
            for campo in set(obj.model_fields) & JAMAIS_EXPOR:
                vazando.append(f"{nome}.{campo}")
    assert not vazando, "Campo sensível exposto em schema de resposta: " + ", ".join(vazando)


def test_o_desconto_da_fatura_chega_ao_cliente():
    """O quarto caso da mesma família, achado por este arquivo.

    `InvoiceOut` trazia `subtotal` e `total` mas não `discount`, e
    `total = subtotal - discount`. Numa tela que mostra os dois, os números
    simplesmente não fechavam — sem erro, sem log, sem ninguém perceber.
    """
    assert "discount" in E.InvoiceOut.model_fields
