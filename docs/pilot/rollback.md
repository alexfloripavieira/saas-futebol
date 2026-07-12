# Ensaio de rollback do piloto

Este runbook complementa [produção: backup e restauração](../runbooks/producao-backup-restauracao.md).

## Antes do deploy

1. Registre versão/tag atual, nova versão e lista de migrations.
2. Gere backup consistente do PostgreSQL e da mídia privada.
3. Registre local, tamanho, checksum, horário e responsável pelos backups.
4. Confirme que as credenciais e o ambiente de restauração estão disponíveis.

## Gatilhos de rollback

- falha na migração;
- jornada vertical ou smoke test reprovado;
- acesso cruzado entre tenants;
- perda ou exposição de evidência;
- erro 5xx persistente ou inconsistência de contrato/negociação.

## Execução

1. Interrompa novas escritas e registre o horário do incidente.
2. Preserve logs e request IDs relacionados.
3. Reverta a aplicação para a tag anterior.
4. Para migration apenas aditiva e compatível, mantenha o schema e execute o smoke test.
5. Para migration destrutiva ou dados inconsistentes, restaure banco e mídia do mesmo ponto.
6. Suba uma única instância, execute `check`, `migrate --check` e `check_pilot_readiness`.
7. Execute a jornada de leitura e depois uma jornada controlada de escrita.
8. Reabra o acesso somente após aprovação do responsável.

## Evidência do ensaio

Registre duração total, RPO observado, RTO observado, backup usado, versão restaurada, resultado dos checks e responsável. Falha no ensaio determina **NO-GO**.
