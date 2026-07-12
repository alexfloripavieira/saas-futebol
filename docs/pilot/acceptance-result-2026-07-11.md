# Resultado técnico de aceite — 2026-07-11

## Escopo avaliado

- Sprint 13 — Consolidação para piloto
- Tenant local de demonstração: `avai`
- Baseline: commit `41acddd`

## Evidências automáticas

- `118` testes Django aprovados em PostgreSQL 16.
- `makemigrations --check --dry-run`: nenhuma mudança pendente.
- `check --deploy` com `config.settings_production`: nenhum alerta.
- configuração de `docker-compose.prod.yml` validada.
- `check_pilot_readiness --tenant avai`: GO automático para revisão humana.
- health check consulta o banco e exige corpo `{"status": "ok"}`.
- revisão de padrões e revisão contra o PRD executadas; achados P1 corrigidos.
- API v1 usa credencial com hash, header exclusivo e rate limit global no banco.
- upload e download privado de evidências cobertos por testes de isolamento.
- jornada vertical HTTP e matriz dos sete papéis cobertas por testes de regressão.
- banco e mídia possuem scripts separados de backup/restauração com checksum.

## Pendências manuais

- [x] roteiro visual concluído no Chrome em login, painel, pessoas, transferências,
  aprovações, evidências e documentação da API;
- [ ] executar restauração de banco e mídia em ambiente descartável e registrar RPO/RTO;
- [ ] configurar coletor/alerta externo de erros e indisponibilidade;
- [ ] preencher responsáveis e assinaturas no termo de go/no-go.

## Decisão atual

**NO-GO operacional temporário.** O software passou pelo gate técnico automatizado,
mas o piloto não deve ser publicado até a conclusão das três pendências manuais
acima. Não há GO condicional para backup/restauração, observabilidade ou aceite
humano.
