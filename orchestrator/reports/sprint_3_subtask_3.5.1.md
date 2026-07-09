# Sprint 3 — Fluxos operacionais

## Resultado
Sprint 3 concluída com sucesso no projeto `~/saas-futebol/`.

## Entregas
- Fluxos operacionais expostos na UI server-rendered:
  - `/aprovacoes/`
  - `/solicitacoes-aprovacao/`
  - `/notificacoes/`
- Ações de workflow implementadas:
  - aprovar, rejeitar e cancelar solicitações de aprovação
  - marcar notificação como lida
- Regras de domínio fortalecidas:
  - solicitação de aprovação exige solicitante com vínculo ativo no tenant
  - notificação exige destinatário com vínculo ativo no tenant
  - transições válidas apenas a partir do estado pendente, com `decided_at`
- Home e navegação atualizadas para a Sprint 3.
- Cobertura de testes para listagens, transições e validações.

## Verificação real
- `make test` ✅
- `docker compose run --rm web python src/manage.py check` ✅
- Rotas novas responderam com redirecionamento autenticado (`302` para login) ✅

## Observação
A Sprint 3 fechou o núcleo operacional de aprovação/notificação sem alterar o esquema do banco.
