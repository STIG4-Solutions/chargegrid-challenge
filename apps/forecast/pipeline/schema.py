"""
Schema canonico do painel diario.
=================================

Este e o CONTRATO do pipeline. Toda fonte de dados (Modbus, OCPP, CDR OCPI)
precisa produzir exatamente esta estrutura. Tudo a jusante - features, treino,
previsao - consome so isto e nao sabe de onde o dado veio.

E por isso que trocar Modbus por OCPP nao quebra nada: escreve-se um adaptador
novo em ingest/, o resto do codigo nao muda.

Nomenclatura alinhada ao OCPI 2.2.1 (mod_cdrs / mod_locations) para que a
migracao futura seja um mapeamento direto, sem renomear coluna.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

import pandas as pd

# --- Painel diario: uma linha por (estacao, dia) ---------------------------

COLUNAS_PAINEL = {
    "location_id": "string",    # OCPI CdrLocation.id - identificador da estacao
    "date": "datetime64[ns]",   # dia civil, normalizado a meia-noite local
    "kwh": "float64",           # energia entregue no dia. NaN se indisponivel
    "sessions": "float64",      # nº de sessoes. NaN se a fonte nao souber
    "revenue": "float64",       # faturamento. NaN se a fonte nao souber
    "price_per_kwh": "float64",  # tarifa vigente. NaN se vier de outro sistema
    "is_available": "bool",     # False = equipamento fora do ar naquele dia
}

# --- Cadastro de estacoes: uma linha por estacao ---------------------------

COLUNAS_ESTACOES = {
    "location_id": "string",
    "location_name": "string",
    "archetype": "string",       # rodovia | shopping | corporativo | condominio
    "power_type": "string",      # OCPI Connector.power_type: AC_1_PHASE/AC_3_PHASE/DC
    "n_connectors": "int64",
    "max_electric_power": "float64",  # kW nominal
    "opened_at": "datetime64[ns]",
}

ARQUETIPOS_VALIDOS = {"rodovia", "shopping", "corporativo", "condominio"}
POWER_TYPES_VALIDOS = {"AC_1_PHASE", "AC_3_PHASE", "DC"}


@dataclass
class ResultadoValidacao:
    ok: bool
    erros: list[str]
    avisos: list[str]

    def levantar_se_invalido(self) -> None:
        if not self.ok:
            raise ValueError(
                "Painel invalido:\n  - " + "\n  - ".join(self.erros))

    def imprimir(self) -> None:
        for a in self.avisos:
            print(f"  [aviso] {a}")
        for e in self.erros:
            print(f"  [ERRO]  {e}")
        if self.ok and not self.avisos:
            print("  painel ok")


def validar_painel(painel: pd.DataFrame,
                   estacoes: pd.DataFrame | None = None) -> ResultadoValidacao:
    """Portao de qualidade entre ingestao e modelo.

    Roda SEMPRE antes do treino e antes da previsao. Sai mais barato falhar
    aqui do que descobrir na apresentacao que o contador resetou.
    """
    erros: list[str] = []
    avisos: list[str] = []

    faltando = set(COLUNAS_PAINEL) - set(painel.columns)
    if faltando:
        erros.append(f"colunas ausentes: {sorted(faltando)}")
        return ResultadoValidacao(False, erros, avisos)

    if painel.empty:
        erros.append("painel vazio")
        return ResultadoValidacao(False, erros, avisos)

    # Chave primaria
    dup = painel.duplicated(["location_id", "date"]).sum()
    if dup:
        erros.append(f"{dup} linhas duplicadas em (location_id, date)")

    # Energia negativa: sintoma classico de reset de contador em Modbus.
    neg = (painel["kwh"] < 0).sum()
    if neg:
        erros.append(f"{neg} dias com kwh negativo "
                     "(provavel reset/overflow de contador nao tratado)")

    # Buracos na grade: dia faltando nao e o mesmo que dia com zero.
    for loc, g in painel.groupby("location_id"):
        esperado = pd.date_range(g["date"].min(), g["date"].max(), freq="D")
        buracos = len(esperado) - g["date"].nunique()
        if buracos:
            avisos.append(f"{loc}: {buracos} dias ausentes na grade "
                          "(preencher com is_available=False)")

    # Historico minimo para o modelo ter o que aprender.
    for loc, g in painel.groupby("location_id"):
        n = g["kwh"].notna().sum()
        if n < 180:
            avisos.append(f"{loc}: apenas {n} dias com dado valido "
                          "(minimo recomendado 180) - sera ignorada no treino")

    # Zero suspeito: dia marcado como disponivel mas com energia zerada.
    # Quase sempre e downtime nao detectado pela ingestao.
    z = painel[painel["is_available"] & (painel["kwh"] == 0)]
    if len(z) > 0.02 * len(painel):
        avisos.append(f"{len(z)} dias com kwh=0 marcados como disponiveis "
                      "- revisar deteccao de indisponibilidade")

    # Outlier grosseiro: acima do teto fisico do parque.
    if estacoes is not None and "max_electric_power" in estacoes:
        cap = estacoes.set_index("location_id")["max_electric_power"] * \
            estacoes.set_index("location_id")["n_connectors"] * 24
        teto = painel["location_id"].map(cap)
        acima = (painel["kwh"] > teto).sum()
        if acima:
            erros.append(f"{acima} dias com kwh acima da capacidade fisica "
                         "instalada (potencia x conectores x 24h)")

    return ResultadoValidacao(not erros, erros, avisos)


def normalizar_painel(painel: pd.DataFrame) -> pd.DataFrame:
    """Coage tipos e ordena. Chamar no fim de todo adaptador de ingestao."""
    p = painel.copy()
    p["date"] = pd.to_datetime(p["date"]).dt.normalize()
    for col in ("sessions", "revenue", "price_per_kwh"):
        if col not in p:
            p[col] = pd.NA
    p["is_available"] = p.get("is_available", True).astype(bool)
    # Regra invariante: dia indisponivel tem alvo NaN, nunca zero.
    p.loc[~p["is_available"], ["kwh", "sessions", "revenue"]] = pd.NA
    for col, tipo in COLUNAS_PAINEL.items():
        if tipo.startswith("float") or tipo.startswith("int"):
            p[col] = pd.to_numeric(p[col], errors="coerce")
    return p[list(COLUNAS_PAINEL)].sort_values(
        ["location_id", "date"]).reset_index(drop=True)


def preencher_grade(painel: pd.DataFrame,
                    estacoes: pd.DataFrame,
                    ate: dt.date | None = None) -> pd.DataFrame:
    """Garante um registro por (estacao, dia) desde a abertura.

    Dia sem leitura vira is_available=False, nao kwh=0. A diferenca importa:
    um preenche o modelo com demanda falsa, o outro nao ensina nada.
    """
    fim = pd.Timestamp(ate) if ate else painel["date"].max()
    grades = []
    for _, e in estacoes.iterrows():
        dias = pd.date_range(pd.Timestamp(e["opened_at"]).normalize(), fim, freq="D")
        grades.append(pd.DataFrame({"location_id": e["location_id"], "date": dias}))
    grade = pd.concat(grades, ignore_index=True)

    out = grade.merge(painel, on=["location_id", "date"], how="left")
    out["is_available"] = out["is_available"].fillna(False).astype(bool)
    return normalizar_painel(out)
