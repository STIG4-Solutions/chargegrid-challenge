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

## Configuracao e dados locais

Versione apenas os exemplos de ambiente. Arquivos `.env`, configuracoes da IDE, caches, builds e credenciais ficam fora do Git. Antes de publicar, revise `git diff --cached` para confirmar o escopo.

Use `npm run infra:down` para parar o ambiente mantendo os dados. Remover volumes e uma operacao separada e apaga o banco local.
