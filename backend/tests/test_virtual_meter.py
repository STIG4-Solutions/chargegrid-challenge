"""O medidor virtual substitui o smart meter fisico, entao a curva que ele
produz precisa ser plausivel: um valor absurdo aqui vira potencia concedida
a mais no rateio, e ninguem perceberia olhando so' o painel."""

from app.workers.virtual_meter import bateria_kw, carga_do_predio_kw, geracao_solar_kw

TETO = 75.0
PICO_SOLAR = TETO * 0.5
BASE_PREDIO = TETO * 0.25
CAPACIDADE_BATERIA = TETO * 0.16


def test_sem_sol_a_noite():
    for hora in (0, 3, 5, 18.1, 21, 23.9):
        assert geracao_solar_kw(hora, PICO_SOLAR) == 0.0


def test_solar_satura_ao_meio_dia():
    meio_dia = geracao_solar_kw(12, PICO_SOLAR)
    assert meio_dia == PICO_SOLAR
    # Manha e tarde geram menos que o pico, e de forma simetrica.
    assert geracao_solar_kw(9, PICO_SOLAR) == geracao_solar_kw(15, PICO_SOLAR)
    assert geracao_solar_kw(9, PICO_SOLAR) < meio_dia


def test_solar_nunca_passa_do_pico():
    for passo in range(0, 240):
        hora = passo / 10
        assert 0.0 <= geracao_solar_kw(hora, PICO_SOLAR) <= PICO_SOLAR


def test_predio_consome_mais_em_horario_comercial():
    comercial = carga_do_predio_kw(14, BASE_PREDIO)
    madrugada = carga_do_predio_kw(3, BASE_PREDIO)
    assert comercial > madrugada
    assert madrugada > 0  # o predio nunca zera


def test_bateria_entra_na_ponta():
    """18h-21h e' a janela de ponta: a bateria tem que descarregar."""
    for hora in (18, 19.5, 20.9):
        kw, _ = bateria_kw(hora, solar=0, predio=20, capacidade_kw=CAPACIDADE_BATERIA)
        assert kw > 0


def test_bateria_nao_descarrega_fora_da_ponta():
    for hora in (10, 12, 22, 3):
        kw, _ = bateria_kw(hora, solar=30, predio=20, capacidade_kw=CAPACIDADE_BATERIA)
        assert kw == 0.0


def test_soc_fica_em_faixa_valida():
    for hora in range(24):
        _, soc = bateria_kw(hora, solar=40, predio=15, capacidade_kw=CAPACIDADE_BATERIA)
        assert 0.0 <= soc <= 100.0
