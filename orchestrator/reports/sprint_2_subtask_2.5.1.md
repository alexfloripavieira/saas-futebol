# Sprint 2 — Núcleo de dados do futebol

## Resultado
Sprint 2 concluída com sucesso no projeto `~/saas-futebol/`.

## Entregas
- Modelos centrais de domínio implementados com integridade:
  - clubes, categorias, competições, edições, fases, partidas
  - atletas/pessoas, vínculos, eventos e escalações
  - regras paramétricas de competição
  - trilha de auditoria, aprovações e integrações
- Regras de integridade com `clean()`/`full_clean()` e constraints:
  - mesma tenant em relações críticas
  - mandante != visitante
  - unicidade por tenant/slug/código
  - contrato ativo único por pessoa/club
  - janela de imutabilidade de partida calculada por regra da competição
- Padrão de listagem implementado:
  - `/clubes/`
  - `/competicoes/`
  - `/partidas/`
  - busca, ordenação e paginação
- Importação/exportação implementadas:
  - CSV e JSON
  - política de conflito `skip`/`overwrite`
  - relatório de falhas por linha
  - overwrite idempotente quando não há mudança real
- Testes adicionados e verificados no container.

## Verificação real
- `make makemigrations` ✅
- `make migrate` ✅
- `make test` ✅
- `docker compose run --rm web python src/manage.py test futebol.tests.IntegrityTests futebol.tests.HomeAndListingTests futebol.tests.ImportExportTests -v 2` ✅
- `docker compose run --rm web python src/manage.py check` ✅

## Observação
As regras paramétricas da competição ficaram materializadas em `CompetitionRuleSet`, cobrindo a área que havia sido marcada como revisão dentro da sprint.
