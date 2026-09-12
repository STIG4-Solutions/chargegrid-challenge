# Como contribuir

Este repositorio reune a API, o dashboard comercial, o aplicativo mobile e o SDK do ChargeGrid. Prepare o ambiente seguindo [desenvolvimento local](docs/development.md) e consulte as [convencoes de estrutura](docs/repository-structure.md).

## Fluxo de trabalho

1. Crie uma branch curta a partir de `main`, como `feat/42-reservar-carregador`, `fix/erro-no-login` ou `chore/repository-layout`.
2. Mantenha cada mudanca focada em uma entrega revisavel. Uma funcionalidade pode envolver API, SDK e suas telas no mesmo PR.
3. Execute as verificacoes das partes afetadas. Mudancas no SDK devem validar dashboard e mobile.
4. Abra um PR para `main`, preenchendo o modelo e solicitando revisao de outra pessoa da equipe.
5. Prefira squash merge e remova a branch depois da integracao.

Esta convencao orienta o trabalho; regras de protecao de branches sao configuradas separadamente no GitHub.

## Commits

Use Conventional Commits, com o escopo quando ele ajudar:

```text
feat(api): adicionar reserva de carregador
fix(dashboard): corrigir filtro de sessoes
docs: atualizar configuracao local
chore(repo): padronizar estrutura do repositorio
```

Os nomes de diretorios e pacotes seguem a convencao em ingles. A documentacao e as descricoes de commits podem continuar em portugues.

## Dependencias e contrato

- Use npm na raiz. Versione `package-lock.json` quando alterar dependencias ou workspaces.
- Preserve as versoes compativeis de React entre dashboard, mobile e SDK; confira com `npm ls react`.
- O SDK permanece em `packages/sdk` e e consumido como codigo-fonte TypeScript.
- Ao alterar o contrato, atualize `apps/api/openapi.json`, execute `npm run gen:types` e valide os consumidores. Nao edite `packages/sdk/src/schema.ts` manualmente.
- Migrations, testes e configuracoes especificas permanecem na aplicacao responsavel.
- Coluna nova num modelo exige decisao: exponha no schema de resposta ou declare em
  `OMISSOES`, em `tests/test_cobertura_de_schema.py`, com o motivo. O Pydantic descarta em
  silencio o que o schema nao lista, e esse defeito ja apareceu quatro vezes.
- Schema novo que le de ORM herda de `ORMModel` e o modulo dele entra na varredura do mesmo
  teste. Um schema fora dela passa por baixo da guarda — foi assim que `app/schemas/campanha.py`
  nasceu invisivel a ela.

## Migrations

- Indice ou constraint declarado apenas na migration **some** de um banco criado por
  `create_all`. Declare nos dois lugares: `tests/test_deriva_de_schema.py` roda
  `alembic check` e reprova quando os dois lados divergem.
- Nomes de constraint vao **sem** o prefixo `ck_<tabela>_`: a `NAMING_CONVENTION` o acrescenta.
  Escrever o nome completo o duplica, e passando de 63 caracteres o Postgres trunca com hash —
  o nome no banco deixa de bater com o do metadata. Ver as migrations `0018` e `0022`.
  `alembic check` **não** pega isso: com o modelo e a migration usando o mesmo nome completo,
  os dois concordam e o check fica verde com o prefixo dobrado nos dois lados. Quem pega é
  `test_nenhum_nome_de_constraint_tem_prefixo_dobrado`.
- Mexeu numa migration? O banco de teste **persiste** entre execuções e o `conftest` só roda
  `alembic upgrade head`, que não faz nada num banco já no head — a suíte passa sem exercitar
  a mudança. Derrube `chargegrid_test` antes de acreditar no verde.
- Nao edite migration ja aplicada. O schema passa a depender de *quando* cada banco rodou, e
  quem clonou antes fica com colunas a menos. Corrija numa migration nova, com
  `ADD COLUMN IF NOT EXISTS` quando houver bancos dos dois lados.
- Toda guarda nova merece um teste de mutacao: reverta a condicao e confirme que algo quebra.
  Guarda que ninguem consegue quebrar e' decorativa.

## Configuracao e dados locais

Versione apenas os exemplos de ambiente. Arquivos `.env`, configuracoes da IDE, caches, builds e credenciais ficam fora do Git. Antes de publicar, revise `git diff --cached` para confirmar o escopo.

Use `npm run infra:down` para parar o ambiente mantendo os dados. Remover volumes e uma operacao separada e apaga o banco local.

## `npm audit`: o que foi corrigido e o que fica

Estado atual: **18 avisos moderados, nenhum alto ou crítico**, todos na árvore do Expo. Eram 26,
com 3 altos.

O que foi resolvido:

| pacote | de → para | onde roda |
|---|---|---|
| `vite` (+ `@vitejs/plugin-react`, `esbuild`) | 5 → **8** | servidor de desenvolvimento e build |
| `vitest` | 3 → **5** | executor de teste |
| `react-router-dom` | 6 → **7** | **vai no bundle** — é o único que o usuário final executa |
| `js-yaml` e outros transitivos | via `npm audit fix` | geração de tipos |

O `react-router-dom` era o que exigia cuidado, e por isso foi verificado no navegador e não só
no build: o painel usa apenas a API clássica (`HashRouter`, `Routes`, `Route`, `NavLink`,
`Outlet`, `Navigate`, `useLocation`), que o v7 mantém. Rota profunda (`#/ev/contract`) redireciona
para o login pela guarda de autenticação, sem uma única mensagem de console.

### Por que os 18 restantes ficam

**`npm audit fix --force` destruiria o app do motorista.** As "correções" que ele propõe são
downgrades, não upgrades:

| pacote | instalado | "correção" proposta |
|---|---|---|
| `expo` | **57.0.22** | 46.0.21 |
| `@react-navigation/native-stack` | **7.18.10** | 5.0.5 |
| `expo-sharing` | **57.0.19** | 14.0.8 |

Onze majors para trás no Expo. O npm chega a isso porque procura *qualquer* versão cuja árvore
não contenha o transitivo marcado, e a mais antiga satisfaz. Não é upgrade — é apagar a
aplicação.

Os 18 são transitivos dentro do próprio Expo (`@expo/config-plugins` → `xcode` → `uuid`,
`@react-navigation/core` → `query-string` → `decode-uri-component`). Saem quando o Expo publicar
uma SDK que os atualize; não há o que fazer daqui além de acompanhar.

**Rodar `npm audit fix` (sem `--force`) é seguro e continua valendo.** O `--force` neste
repositório, não.
