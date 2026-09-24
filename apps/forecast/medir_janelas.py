"""Quanta folga cada janela tem para um modelo ocupar.

    python medir_janelas.py --ate 2026-08-31

Roda ANTES de treinar qualquer modelo por janela. A pergunta que responde: entre
a melhor regua sem ML e o piso de ruido irredutivel, ha distancia? Onde nao ha,
treinar modelo e' gastar por nada - e foi medindo isso que se descobriu que no
eixo diario a regua ja' empatava com as 700 arvores.

Nao escreve nada: le o banco e imprime.
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

from banco import carregar, conectar
from janelas import medida
from janelas.painel import na_rede, painel_horario, serie


def main() -> int:
    ap = argparse.ArgumentParser(description="Folga por janela de previsao")
    ap.add_argument(
        "--ate",
        help="ultimo dia do historico (AAAA-MM-DD). Padrao: ultimo dia do mes passado",
    )
    ap.add_argument("--praca", help="slug de uma praca, para medir o escopo dela tambem")
    args = ap.parse_args()

    # Mesmo padrao de `treinar.py`: o mes CORRENTE fica fora. O seed ancora em
    # `now()`, e sem corte explicito a mesma linha de comando mede dados
    # diferentes a cada dia.
    ate = (
        date.fromisoformat(args.ate)
        if args.ate
        else date.today().replace(day=1) - timedelta(days=1)
    )

    engine = conectar()
    print(f"corte do historico: {ate}")

    diario, estacoes, _ = carregar(engine, ate=ate)
    horario = painel_horario(engine, ate=ate)

    print(
        f"painel diario:  {len(diario):,} linhas, {diario['location_id'].nunique()} pracas\n"
        f"painel horario: {len(horario):,} linhas, {horario['location_id'].nunique()} pracas"
    )

    # ------------------------------------------------------------------ rede
    s_hora = serie(na_rede(horario))
    s_dia = serie(na_rede(diario.rename(columns={"date": "bucket"})))
    medida.imprimir(medida.tabela(s_hora, s_dia), "REDE INTEIRA (todas as pracas somadas)")

    # ----------------------------------------------------------------- praca
    alvo = args.praca
    if alvo is None:
        # A maior praca por energia: e' a que mais pesa no WAPE da rede, e a que
        # um operador olharia primeiro.
        alvo = str(diario.groupby("location_id", observed=True)["kwh"].sum().idxmax())
    uma_hora = horario[horario["location_id"] == alvo]
    uma_dia = diario[diario["location_id"] == alvo].rename(columns={"date": "bucket"})
    if uma_hora.empty or uma_dia.empty:
        print(f"\n[aviso] praca '{alvo}' nao esta' no painel - escopo de praca nao medido")
        return 0

    medida.imprimir(medida.tabela(serie(uma_hora), serie(uma_dia)), f"UMA PRACA: {alvo}")

    print(
        "\nO que a tabela decide: janela com folga perto de zero nao ganha modelo -\n"
        "a regua ja' esta' no limite do que o dado permite, e `fonte` serve a regua."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
