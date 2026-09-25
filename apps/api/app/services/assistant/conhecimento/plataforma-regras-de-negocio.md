<!-- GERADO por scripts/exportar_conhecimento.py a partir de README.md. Nao edite: rode o script. -->
<!-- titulo: Regras de negócio do ChargeGrid -->

## O que cada lado faz

A seção **Recarga EV** tem doze abas. A primeira resume; as três seguintes operam o presente;
as demais decidem o futuro — é onde o painel deixa de relatar e passa a recomendar.

| Aba | Pergunta que responde |
|---|---|
| Analytics | como a operação está indo — receita e energia dia a dia, e de quem ela depende |
| Gerenciamento de Potência | quanto cada ponto pode puxar agora, sem estourar o padrão |
| Ciclo da Sessão | o que está acontecendo em cada recarga, com timeline auditável |
| Tarifação & Pagamento | quanto custa, por janela horária, e como se cobra |
| Demanda Contratada | qual demanda contratar — e quanto o rateio já poupou de multa |
| Ocupação & Retorno | qual ponto se paga, e qual está ocupado sem faturar |
| Regras de Prioridade | quem carrega quando falta potência, e por quê |
| Visão de Rede | qual praça segura a operação (aparece com mais de um site) |
| Campanhas | quanto custa comprar comportamento do motorista, e se comprou |
| Plano & Contrato | o que a praça paga à GoodWe, e quanto custa sair antes do prazo |
| Contas | quem opera a rede — criar, listar, ligar e desligar (**admin**) |
| Auditoria | quem fez o quê, com dinheiro e com permissão (**admin**) |

### App do motorista

O básico já estava lá: encontrar estação, ler o QR do carregador, iniciar e acompanhar a
recarga, agendar vaga, ver faturas e gerenciar veículos e carteira. O que veio depois usa dados
que a API já produzia e ninguém mostrava:

| Recurso | O que muda para quem dirige |
|---|---|
| Teto da recarga | "carregue até 30 kWh / 45 min / R$ 50" — o servidor já parava sozinho, faltava a tela |
| Quando começar | "comece às 21h e pague 33% menos", pelo mesmo motor que vai faturar |
| Notificação push | recarga concluída, vez na fila, parada por falha — sem precisar do app aberto |
| Recibo em PDF | o documento que vai para a prestação de contas da empresa |
| Reportar problema | cabo cortado e vaga ocupada não têm sensor; o motorista vê antes |
| Modo frota | gasto por centro de custo, para quem paga a conta de vários carros |
| Missões | o que falta para o próximo cashback, com o progresso real de cada meta |
| Plano de recarga | assinatura mensal: desconto em toda recarga e franquia de kWh |

Dois deles fecham ciclo com o painel: o reporte alimenta a manutenção preditiva — um ponto com
duas reclamações e nenhum sinal de sensor sobe para prioridade alta —, e o conselho de horário
sai das mesmas janelas tarifárias que o operador configura.

As missões fecham um terceiro: o operador cria a campanha numa aba, e é ela que aparece como
meta no app. O que ele gasta ali volta como número na tela dele — quantas pessoas alcançou,
quantas cumpriram, quanto do orçamento saiu.

## Retenção: quem paga o quê

Três mecanismos, e trocar o bolso de qualquer um produz um modelo que não se sustenta.

| Mecanismo | Quem paga | Quando o motorista sente |
|---|---|---|
| Desconto na fatura | o estabelecimento | na hora de decidir onde carregar |
| Cashback na carteira | a rede | depois, e por isso ele volta |
| Plano de recarga | o próprio motorista | em toda recarga, por assinatura |

Desconto sai da margem do estabelecimento naquela sessão — é comercial clássico, e se consome
onde nasce. Cashback vira crédito de carteira, que só vale **dentro da plataforma** e é
resgatável em qualquer site: um estabelecimento que o bancasse estaria financiando uma recarga
que amanhã acontece no concorrente. Por isso quem banca é a rede.

Quando assinatura e campanha valem juntas, o motorista recebe **o melhor de cada componente,
nunca a soma**. Somar produziria desconto sem teto que ninguém orçou; deixar a campanha vencer
tiraria de quem pagou o que ele comprou.

Do outro lado, o estabelecimento assina a plataforma com prazo mínimo. `minimo_ate` **não
avança na renovação automática** — prender por mais doze meses quem apenas deixou o contrato
correr é abusivo. A cobrança é emitida, não liquidada: não há integração bancária, e a baixa é
manual, feita por admin. Isso está declarado na tela e na resposta da API.

## Previsão de demanda, e por que ela mora fora

`apps/forecast/` prevê quanto cada eletroposto deve vender no próximo mês. É um job offline, e
a API apenas **lê** a tabela que ele escreve.

A separação não é estética. O processo do FastAPI também roda os workers de potência: um
`import lightgbm` que falhe derrubaria junto o rebalanceamento — que é o que impede o disjuntor
de abrir. Previsão de faturamento não pode compartilhar processo com controle de carga.

**O modelo ganha das réguas nos dois eixos, e por pouco no mensal** — que é a granularidade
que a tela mostra. WAPE, de `apps/forecast/modelos/metricas_atual.json`:

| granularidade | modelo | média móvel de 28 dias | por dia da semana | ano-a-ano |
|---|---|---|---|---|
| diário | **27,50%** | 36,31% | 29,85% | 34,67% |
| mensal | **8,06%** | 13,95% | 14,20% | 8,67% |

Medido em doze meses fora da amostra, 84 estação-meses e 2.555 dias. A faixa p10–p90 cobre
79,6% dos dias, contra os 80% que declara — dentro da tolerância, e o número medido vai para a
tela ao lado do declarado. O arquivo traz o comando que o refaz; se esta tabela divergir dele,
o arquivo manda.

Três coisas a dizer junto com esses números:

- **No mês a vantagem é de 0,61 ponto** sobre a régua de ano-a-ano. A dispersão da grade de
  hiperparâmetros do modelo mensal vai de 7,51% a 8,72% — maior que a vantagem. O próximo
  retreino pode perdê-la.
- **Nenhuma régua ganha nos dois eixos**: no mês a de ano-a-ano, no dia a de dia da semana. É
  por isso que as três ficam medidas nos dois.
- **Todo o histórico é sintético.** O gerador repete a sazonalidade mensal ano a ano por
  construção, então o eixo de ano-a-ano acerta aqui de um jeito que não se repete em rede real.
  O mecanismo é real; a magnitude é circular.

O job grava **o preditor que mede melhor**, e a coluna `fonte` diz qual foi — hoje o modelo,
e a régua de volta sozinha no dia em que ele perder, sem ninguém mexer em código.
`apps/forecast/README.md` detalha.

## Assistente do operador

Um botão no canto do painel abre um assistente (Azure OpenAI) que responde perguntas de
operação em português: "vou estourar a demanda nas próximas horas?", "qual ponto se paga?",
"tenho cobrança em atraso?". Ele não é uma interface a mais sobre os dados: é a camada que
traduz o que as nove abas já calculam — potência, rateio, receita, ocupação, previsão,
manutenção — em resposta gerencial, que é o papel de NLP que o desafio pede.

**Todo número vem de uma ferramenta, e toda ferramenta é a rota GET da aba.** O modelo não
consulta o banco e não recebe uma cópia dos dados: ele escolhe entre 24 ferramentas, e cada uma
chama a mesma rota que a aba correspondente chama. Uma consulta "equivalente" escrita de novo
divergiria na primeira correção que só uma das duas recebesse, e o assistente passaria a
responder um número que a aba não mostra.

As guardas que valem mesmo se o modelo desobedecer ficam no código, não no prompt:

| Guarda | Onde |
|---|---|
| A praça vem do token (`ScopedSiteId`); nenhuma ferramenta aceita `site_id`, e argumento desconhecido é erro | `tools.py` |
| Ferramenta roda em savepoint `READ ONLY` com `statement_timeout`: escrever falha no Postgres | `guardrails.py` |
| Ferramenta de rede (`visao_da_rede`) só existe para admin — nem aparece na lista do operador | `tools.py` |
| Cota por usuário (minuto e dia), contada no banco | `guardrails.py` |
| Canário no system prompt: se aparecer na saída, a resposta é barrada | `guardrails.py` |
| Filtro de conteúdo e Prompt Shields do deployment Azure, traduzidos em evento `bloqueado` | `client.py` |
| Teto de rodadas de ferramenta; a última vai sem ferramentas e obriga a responder | `orchestrator.py` |
| Conversa presa à praça em que nasceu; trocar de praça abre outra | `api/v1/assistant.py` |

**Especificação técnica vem da documentação, não da memória do modelo.** A ferramenta
`buscar_documentacao` faz busca textual (BM25) no manual, no datasheet e no mapa Modbus do HCA G2,
na mentoria da GoodWe e nas regras de negócio deste README. A imagem Docker só leva `apps/api`,
então os documentos têm uma cópia gerada em `app/services/assistant/conhecimento/`
(`python -m scripts.exportar_conhecimento`), e `test_conhecimento.py` recusa a cópia desatualizada
— o mesmo arranjo do `openapi.json`.

**Custo, medido no `gpt-5.4-mini`:** uma pergunta típica usa ~5,8 mil tokens de entrada, dos quais
~78% saem do cache de prompt do Azure (a parte fixa — ferramentas e instruções — vem primeiro de
propósito), e ~100 de saída: cerca de US$ 0,002 por pergunta. Três tetos em tokens protegem o
crédito da conta: por resposta (`ASSISTANT_MAX_INPUT_TOKENS_PER_ANSWER`, a rodada seguinte vai
sem ferramentas), por usuário e por instalação a cada 24 h (`ASSISTANT_DAILY_TOKENS_PER_USER`,
`ASSISTANT_DAILY_TOKENS_TOTAL`, 429 na pergunta seguinte).

Cada pergunta, cada chamada de ferramenta (com argumentos e resultado) e cada resposta ficam em
`assistant_messages`, com tokens e latência — é o rastro de onde saiu cada número. Mensagem
barrada sai do histórico que volta ao modelo; senão a conversa inteira seria recusada dali em
diante.

Desligado por padrão (`ASSISTANT_ENABLED=false`): a API sobe sem Azure nenhum e o widget não
aparece. O SDK do `openai` só é importado na primeira conversa, pelo mesmo motivo que o
LightGBM mora fora — o processo da API também roda o rebalanceamento de potência.

`pytest` cobre o código com um modelo roteirizado. O que o modelo **de verdade** faz diante de
jailbreak, pedido do prompt, injeção escondida num reporte de motorista e perguntas-ouro (o
número tem de bater com a aba) é medido por `python -m scripts.redteam_assistente`, fora do CI:
custa tokens e não é determinístico. Rode ao trocar de deployment, de modelo ou de prompt.

### Medição do site

Não há smart meter físico ligado a esta instalação, então um worker sintetiza a curva do dia
na mesma tabela que um medidor real alimentaria: geração solar em meia senoide entre 6h e 18h,
consumo do prédio maior em horário comercial, bateria descarregando na ponta (18h–21h).
Nada mais no sistema sabe que a origem é sintética — trocar por um coletor Modbus é substituir
`apps/api/app/workers/virtual_meter.py`, sem tocar no domínio.

Controlado por `METER_SOURCE`: `virtual` (padrão) ou `push`, que só aceita o que chegar por
`POST /power/meter-readings`.

Os comandos acima partem da raiz do repositorio. Veja [desenvolvimento local](docs/development.md),
[estrutura do repositorio](docs/repository-structure.md), [deploy da API](docs/api-deployment.md)
e [como contribuir](CONTRIBUTING.md).

> No Windows, use `POSTGRES_HOST=127.0.0.1` e não `localhost`: o nome resolve para `::1` e o
> asyncpg morre na negociação SSL.

## Quem vê o quê no painel

Três papéis, e só dois entram no painel comercial:

| Papel | No painel | Escopo |
|---|---|---|
| `admin` | Tudo, incluindo **Contas** (`/ev/users`) e **Auditoria** (`/ev/audit`) | A rede inteira — escolhe qualquer praça pelo seletor |
| `operator` | Tudo menos essas duas abas | Uma praça só, a do próprio `site_id` |
| `driver` | Só o app | — |

**O front esconde, o servidor recusa.** Um motorista consegue fazer login no painel — o
emissor de token é o mesmo do app —, e encontra um painel que responde 403 em cada chamada.
Esconder a aba de Auditoria de um operador é conveniência, não permissão: a rota recusaria
de qualquer jeito. Uma aba que só devolve 403 é pior que aba nenhuma.

O admin não precisa de conta de operador para ver uma praça pelos olhos dela: o seletor de
praça injeta `site_id` em toda requisição, e cada aba passa a responder como se ele fosse o
operador daquele estabelecimento. `apps/dashboard/README.md` detalha as abas, os perfis e a
troca de praça.
