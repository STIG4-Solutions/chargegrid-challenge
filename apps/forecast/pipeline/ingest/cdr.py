"""
Ingestao via CDR (OCPI) e via OCPP.
===================================

Siglas:
  OCPI = Open Charge Point Interface   - backend do CPO <-> backend do eMSP
  OCPP = Open Charge Point Protocol    - carregador <-> backend do operador
  CDR  = Charge Detail Record          - registro de uma sessao (objeto do OCPI)

Ambos produzem o MESMO painel canonico que o adaptador Modbus. E esse o ponto
da arquitetura: quando a empresa migrar de Modbus para OCPP, troca-se a funcao
de ingestao e nada mais no pipeline muda.

Vantagem sobre Modbus: sessao vem pronta, sem precisar sessionizar. Com isso
`sessions` deixa de ser NaN e o faturamento vem do proprio registro.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from ..schema import normalizar_painel


def cdrs_para_painel(cdrs: pd.DataFrame) -> pd.DataFrame:
    """CDRs no schema OCPI 2.2.1 -> painel diario.

    Colunas esperadas (nomes originais do OCPI):
      location_id, start_date_time, total_energy, total_cost_incl_vat,
      price_per_kwh
    """
    df = cdrs.copy()
    df["start_date_time"] = pd.to_datetime(df["start_date_time"])
    df["date"] = df["start_date_time"].dt.normalize()

    diario = df.groupby(["location_id", "date"]).agg(
        sessions=("total_energy", "size"),
        kwh=("total_energy", "sum"),
        revenue=("total_cost_incl_vat", "sum"),
        price_per_kwh=("price_per_kwh", "mean"),
    ).reset_index()
    diario["is_available"] = True
    return normalizar_painel(diario)


def ocpp_para_painel(transacoes: pd.DataFrame) -> pd.DataFrame:
    """Transacoes OCPP (StopTransaction) -> painel diario.

    O OCPP nao emite CDR: ele emite eventos de transacao. A energia da sessao
    e a diferenca entre os medidores de inicio e fim.

    Colunas esperadas:
      location_id, transaction_id, start_timestamp, stop_timestamp,
      meter_start (Wh), meter_stop (Wh)

    Nota: OCPP reporta medidor em Wh, nao kWh. Erro de fator 1000 aqui e
    comum e passa despercebido ate alguem estranhar o faturamento.
    """
    df = transacoes.copy()
    df["start_timestamp"] = pd.to_datetime(df["start_timestamp"])
    df["date"] = df["start_timestamp"].dt.normalize()
    df["kwh_sessao"] = (df["meter_stop"] - df["meter_start"]) / 1000.0

    # Sessao com energia negativa ou absurda = medidor trocado/resetado.
    df.loc[df["kwh_sessao"] < 0, "kwh_sessao"] = np.nan
    df.loc[df["kwh_sessao"] > 350, "kwh_sessao"] = np.nan  # teto fisico generoso

    diario = df.groupby(["location_id", "date"]).agg(
        sessions=("transaction_id", "nunique"),
        kwh=("kwh_sessao", "sum"),
    ).reset_index()
    diario["revenue"] = np.nan        # OCPP nao carrega preco
    diario["price_per_kwh"] = np.nan  # vem da tabela de tarifas
    diario["is_available"] = True
    return normalizar_painel(diario)
