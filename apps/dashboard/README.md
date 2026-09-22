# Painel comercial

Interface de quem **opera** o estabelecimento: potência, sessões, cobrança, campanhas,
contrato e — para quem administra a rede — contas e auditoria.

React 19 + Vite 8, sem framework de estado. As chamadas passam todas pelo
`@chargegrid/sdk`; nenhuma tela monta URL na mão.

## As abas

O painel tem duas metades, e a diferença importa para quem for demonstrá-lo.

### Recarga EV (`/ev/*`) — é o produto

| Aba | Rota | O que faz | Quem vê |
|---|---|---|---|
| **Analytics** | `/ev/analytics` | Visão executiva: evolução diária de receita e energia, tendência e concentração por ponto | operador · admin |
| Gerenciamento de Potência | `/ev/power` | Orçamento do site, rateio por prioridade, corte de emergência, fila de reportes | operador · admin |
| Ciclo da Sessão | `/ev/sessions` | Da autorização ao faturamento, com a linha do tempo de eventos | operador · admin |
| Tarifação & Pagamento | `/ev/tariff` | Tarifas, janelas horárias, faturas e cobrança | operador · admin |
| Demanda Contratada | `/ev/demand` | Projeção contra o contrato, simulador de demanda, previsão de energia | operador · admin |
| Ocupação & Retorno | `/ev/utilization` | Ocupação, receita e ociosidade por ponto | operador · admin |
| Regras de Prioridade | `/ev/priority` | Regras nomeadas e prévia de qual pegaria cada ponto | operador · admin |
| Campanhas | `/ev/campaigns` | Desconto e cashback, com missões e orçamento | operador · admin |
| Plano & Contrato | `/ev/contract` | Plano da plataforma, cobranças e multa de rescisão | operador · admin |
| **Visão de Rede** | `/ev/portfolio` | As praças lado a lado | **quem enxerga mais de uma praça** |
| **Contas** | `/ev/users` | Operadores e admins da rede: criar, listar, ligar e desligar | **admin** |
| **Auditoria** | `/ev/audit` | Quem fez o quê, com dinheiro e com permissão | **admin** |

### SEMS+ (`/station_monitor`, `/device`, `/alarm`, `/report`, `/statistics`, `/om`)

**São estáticas.** Reproduzem a casca do SEMS+ original para o painel não parecer um
produto solto, e **não fazem chamada de API nenhuma** — conferido: zero em todas as seis.
Quem for demonstrar deve saber que os números ali são fixos.

## Perfis de acesso

Três papéis, e só dois entram aqui.

| Papel | No painel | Escopo |
|---|---|---|
| `admin` | Tudo, incluindo Contas e Auditoria | **A rede inteira.** Escolhe qualquer praça |
| `operator` | Tudo menos Contas e Auditoria | **Uma praça só**, a do próprio `site_id` |
| `driver` | Não é o lugar dele | — |

### A guarda real está no servidor

Um motorista **consegue** fazer login aqui: o emissor de token é o mesmo do app, e a tela
de login não olha o papel. O que ele encontra é um painel que responde **403** em cada
chamada.

Isso é deliberado, mas vale dizer em voz alta: **o front esconde, o servidor recusa.**
Esconder a aba de Auditoria de um operador é conveniência — a rota
`GET /api/v1/audit` recusaria de qualquer jeito. Nenhuma decisão de permissão depende do
navegador.

As duas abas de admin somem pelo mesmo mecanismo (`abasDaSecao`, em
`src/views/ev/auditoria.js`), e pelo mesmo motivo: **uma aba que só devolve 403 é pior que
aba nenhuma**.

### O que o operador não vê, além das abas

O botão de **estornar fatura** (`podeEstornar`) só aparece para admin, e só em fatura paga.
Em aberto devolveria dinheiro que nunca entrou; como operador, devolveria do caixa da rede.

## Ver a rede como o operador de cada praça

O admin não precisa de conta de operador para enxergar uma praça pelos olhos dela. O
**seletor de praça**, no topo da seção de Recarga EV, resolve isso:

1. `SiteSwitcher` lista as praças visíveis (`GET /power/sites`).
2. Ao escolher, ele chama `configureSdk({ siteId })`.
3. O SDK passa a injetar `site_id` em **toda** requisição.

O efeito é que cada aba responde como se você fosse o operador daquela praça — sem que
nenhuma tela precise saber que multi-site existe. A escolha fica no `localStorage`, e trocar
de praça **remonta** as telas filhas: sem isso o seletor mudaria a URL das próximas
requisições e a tela continuaria mostrando os números da praça anterior, que é o tipo de
erro que ninguém percebe porque a tela parece funcionar.

O seletor **some quando há uma praça só** — o caso do operador. Ele não escolhe nada: a API
ignora o parâmetro para quem não é admin, e um seletor inerte prometeria um poder que ele
não tem.

## Rodar

```bash
npm run dev          # servidor de desenvolvimento, porta 5173
npm run build        # pacote de produção  → aponta para api.stig4.com
npm run build:staging # pacote de staging  → aponta para api.staging.stig4.com
```

**O endereço da API vai assado no pacote.** `config/domains.json` é a fonte única, e o Vite
o lê em tempo de build. Trocar o domínio depois de publicado não adianta — é preciso
reconstruir. `VITE_API_URL` vence o arquivo, para quem precisar apontar para outro lugar sem
editar nada versionado.

O roteamento é **`HashRouter`** (`#/ev/power`), igual ao SEMS+ original. Consequência útil na
hospedagem: o servidor nunca vê o caminho, então **não é preciso configurar fallback de SPA**.

## Verificação

```bash
npm run verify:dashboard   # 180 cenários da lógica pura, sem navegador
npm run test:dashboard     # 113 testes de renderização (vitest + jsdom)
```

A divisão não é arbitrária. O `verify` cobre o que decide **o que vai para o servidor** — o
diff do editor de orçamento, a validação do formulário de campanha, o corpo do POST de
conta. O `test` cobre **o que o operador lê**: as funções puras podiam estar todas certas e a
tela ainda mentir, bastando o card ignorar `fonte` e chamar de "energia prevista" um número
que é média móvel.

Só o segundo precisa de DOM, e é por isso que ele veio depois.

**Teste de mutação é o padrão de aceite:** reverter a guarda e confirmar que o teste quebra.
