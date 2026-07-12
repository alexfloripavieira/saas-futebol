# Checklist de aceite do piloto

Registre data, responsável, versão da aplicação e tenant em cada execução. Um item P0 reprovado determina **NO-GO**.

## Gate automático

- [x] `python src/manage.py check --deploy` foi revisado sem alerta crítico.
- [x] `python src/manage.py migrate --check` não aponta migração pendente.
- [x] `python src/manage.py check_pilot_readiness --tenant avai` termina com sucesso.
- [x] A suíte completa está verde.
- [x] O teste HTTP da jornada vertical está verde.

## Jornada pessoa → contrato → transferência

- [x] Gestor cadastra uma pessoa no tenant ativo.
- [x] Gestor registra o contrato de origem.
- [x] Gestor abre a negociação com o clube destino.
- [x] O sistema abre uma única solicitação para a negociação.
- [x] Etapas fora de ordem, autoaprovação e papel incorreto são bloqueados.
- [x] Etapa que exige evidência é bloqueada antes do anexo.
- [x] Evidência válida pode ser enviada e baixada apenas por usuário autorizado.
- [x] Aprovação encerra o contrato de origem, cria o destino ativo e aceita a negociação.
- [x] Auditoria registra solicitação, contratos, negociação e ator.

## Isolamento e operação

- [x] Usuário de outro tenant não lista, altera, aprova nem baixa os dados do piloto.
- [x] Eventos de uso, falha, 403 e duração são registrados sem dados pessoais nos metadados.
- [x] Logs preservam `X-Request-ID` e permitem correlacionar a operação.
- [ ] Backup de banco e mídia foi identificado e a restauração foi ensaiada.
- [x] Smoke test visual local foi concluído no Chrome com o tenant `avai`.
