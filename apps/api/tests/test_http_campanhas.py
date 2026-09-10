"""As rotas de campanha, pelo HTTP.

O que se guarda aqui e' quem pode o que. Uma campanha e' dinheiro do
estabelecimento: trocar o identificador na URL nao pode dar acesso a campanha do
vizinho, e o motorista nao pode ler o orcamento de ninguem.

A validacao do formulario tambem entra, porque devolver 422 com explicacao e'
diferente de devolver 500 com um nome de constraint que quem preenche o
formulario nao tem como ler.
"""

from datetime import UTC, datetime, timedelta

AGORA = datetime.now(UTC)


def _corpo(**kwargs) -> dict:
    dados = {
        "nome": "Setembro Verde",
        "patrocinador": "site",
        "starts_at": (AGORA - timedelta(days=1)).isoformat(),
        "ends_at": (AGORA + timedelta(days=30)).isoformat(),
        "beneficio_tipo": "cashback_fixo",
        "beneficio_valor": 5,
        "orcamento_brl": 1000,
        "missoes": [
            {
                "codigo": "tres-recargas",
                "titulo": "Recarregue 3 vezes",
                "metrica": "sessoes",
                "alvo": 3,
                "janela": "mensal",
            }
        ],
    }
    dados.update(kwargs)
    return dados


# ------------------------------------------------------------------- criacao


async def test_operador_cria_campanha_com_missoes(api, como_operador_do_site):
    r = await api.post("/api/v1/campaigns", json=_corpo(), headers=como_operador_do_site)
    assert r.status_code == 201, r.text

    corpo = r.json()
    assert corpo["nome"] == "Setembro Verde"
    assert corpo["site_id"] is not None
    assert len(corpo["missoes"]) == 1
    assert corpo["missoes"][0]["codigo"] == "tres-recargas"


async def test_o_site_vem_do_escopo_e_nao_do_corpo(api, como_operador_do_site, segundo_site):
    """Quem paga sai do token, nunca do payload.

    `site_id` nem existe no schema de entrada: mandar um e' ignorado. Se algum
    dia o campo for aceito, um operador passa a criar campanha bancada pelo
    vizinho - e este teste e' quem avisa.
    """
    r = await api.post(
        "/api/v1/campaigns",
        json=_corpo(site_id=str(segundo_site.id)),
        headers=como_operador_do_site,
    )
    assert r.status_code == 201
    assert r.json()["site_id"] != str(segundo_site.id)


async def test_cashback_sem_missao_e_recusado(api, como_operador_do_site):
    """Cashback sem missao nao premia ninguem: nao ha o que cumprir."""
    r = await api.post(
        "/api/v1/campaigns", json=_corpo(missoes=[]), headers=como_operador_do_site
    )
    assert r.status_code == 422
    assert "missão" in r.text or "missao" in r.text


async def test_desconto_com_missao_e_recusado(api, como_operador_do_site):
    """Desconto age na fatura, na hora. Missao ali nunca premiaria nada."""
    r = await api.post(
        "/api/v1/campaigns",
        json=_corpo(beneficio_tipo="desconto_pct", beneficio_valor=10),
        headers=como_operador_do_site,
    )
    assert r.status_code == 422


async def test_periodo_invertido_e_recusado(api, como_operador_do_site):
    r = await api.post(
        "/api/v1/campaigns",
        json=_corpo(
            starts_at=(AGORA + timedelta(days=10)).isoformat(),
            ends_at=(AGORA + timedelta(days=1)).isoformat(),
        ),
        headers=como_operador_do_site,
    )
    assert r.status_code == 422


async def test_campanha_de_frota_e_recusada_com_explicacao(api, como_operador_do_site):
    """Recusa explicita, e nao silencio.

    Nenhuma fatura aponta para `fleet_id`: a empresa pagaria e o funcionario
    embolsaria. Aceitar e nao fazer nada seria pior que recusar.
    """
    r = await api.post(
        "/api/v1/campaigns", json=_corpo(patrocinador="frota"), headers=como_operador_do_site
    )
    assert r.status_code == 422
    assert "frota" in r.text


async def test_metrica_desconhecida_e_recusada(api, como_operador_do_site):
    corpo = _corpo()
    corpo["missoes"][0]["metrica"] = "numero_de_abracos"
    r = await api.post("/api/v1/campaigns", json=corpo, headers=como_operador_do_site)
    assert r.status_code == 422
    assert "metrica" in r.text


async def test_teto_maior_que_o_orcamento_e_recusado(api, como_operador_do_site):
    r = await api.post(
        "/api/v1/campaigns",
        json=_corpo(orcamento_brl=100, teto_por_recompensa=500),
        headers=como_operador_do_site,
    )
    assert r.status_code == 422


# ---------------------------------------------------------------- isolamento


async def _criada_por(api, headers) -> str:
    r = await api.post("/api/v1/campaigns", json=_corpo(), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


async def test_operador_nao_edita_campanha_do_vizinho(
    api, como_operador_do_site, como_operador_vizinho
):
    campanha = await _criada_por(api, como_operador_do_site)

    r = await api.patch(
        f"/api/v1/campaigns/{campanha}", json={"nome": "Sequestrada"}, headers=como_operador_vizinho
    )
    assert r.status_code == 403


async def test_operador_nao_encerra_campanha_do_vizinho(
    api, como_operador_do_site, como_operador_vizinho
):
    campanha = await _criada_por(api, como_operador_do_site)

    r = await api.delete(f"/api/v1/campaigns/{campanha}", headers=como_operador_vizinho)
    assert r.status_code == 403


async def test_a_lista_nao_traz_campanha_do_vizinho(
    api, como_operador_do_site, como_operador_vizinho
):
    await _criada_por(api, como_operador_do_site)

    r = await api.get("/api/v1/campaigns", headers=como_operador_vizinho)
    assert r.status_code == 200
    assert all(c["nome"] != "Setembro Verde" for c in r.json())


async def test_motorista_nao_acessa_a_gestao_de_campanhas(api, como_motorista):
    r = await api.get("/api/v1/campaigns", headers=como_motorista)
    assert r.status_code == 403


# ------------------------------------------------------------------- edicao


async def test_campos_nao_editaveis_sao_recusados(api, como_operador_do_site):
    """Mudar quem paga depois de o dinheiro ter saido reescreveria a historia."""
    campanha = await _criada_por(api, como_operador_do_site)

    r = await api.patch(
        f"/api/v1/campaigns/{campanha}",
        json={"patrocinador": "rede", "consumido_brl": 0},
        headers=como_operador_do_site,
    )
    assert r.status_code == 422
    assert "patrocinador" in r.text


async def test_encerrar_desativa_sem_apagar(api, como_operador_do_site):
    """Apagar levaria junto o progresso de quem estava no meio da campanha."""
    campanha = await _criada_por(api, como_operador_do_site)

    r = await api.delete(f"/api/v1/campaigns/{campanha}", headers=como_operador_do_site)
    assert r.status_code == 204

    lista = await api.get("/api/v1/campaigns", headers=como_operador_do_site)
    encontrada = next(c for c in lista.json() if c["id"] == campanha)
    assert encontrada["ativa"] is False


async def test_desempenho_responde_com_os_numeros_do_operador(api, como_operador_do_site):
    campanha = await _criada_por(api, como_operador_do_site)

    r = await api.get(f"/api/v1/campaigns/{campanha}/desempenho", headers=como_operador_do_site)
    assert r.status_code == 200

    corpo = r.json()
    assert corpo["orcamento_brl"] == 1000
    assert corpo["consumido_brl"] == 0
    assert corpo["motoristas_alcancados"] == 0
    assert corpo["percentual_consumido"] == 0


# ------------------------------------------------------------- lado do app


async def test_motorista_ve_missoes_sem_numero_de_orcamento(
    api, como_operador_do_site, como_motorista
):
    """Expor orcamento aqui vazaria a estrategia comercial de quem paga."""
    await _criada_por(api, como_operador_do_site)

    r = await api.get("/api/v1/app/missions", headers=como_motorista)
    assert r.status_code == 200

    missoes = r.json()
    assert len(missoes) == 1
    assert missoes[0]["titulo"] == "Recarregue 3 vezes"
    assert missoes[0]["progresso"] == 0
    assert missoes[0]["concluida"] is False
    assert missoes[0]["recompensa"] == "R$ 5,00"
    assert "orcamento_brl" not in missoes[0]
    assert "consumido_brl" not in missoes[0]


async def test_operador_nao_acessa_as_missoes_do_app(api, como_operador_do_site):
    r = await api.get("/api/v1/app/missions", headers=como_operador_do_site)
    assert r.status_code == 403


async def test_recompensas_comecam_vazias(api, como_motorista):
    r = await api.get("/api/v1/app/rewards", headers=como_motorista)
    assert r.status_code == 200
    assert r.json() == []
