# Subtask 0.6.1 — Resumir decisões tomadas (Sprint 0)

**Sprint:** Fundação, escopo e contratos
**Task:** Consolidar Sprint 0
**Status:** completed
**Época:** 2026-06-29
**Modelo:** opencode-go/glm-5.2

---

# Resumo executivo da Sprint 0 — SaaS de Futebol

Documento de 1 página consolidando todas as decisões tomadas nas subtasks 0.1.x a 0.5.x. Fonte primária: relatórios em `orchestrator/reports/sprint_0_subtask_0.*.md`.

## 1. Visão do produto (0.1.x)

SaaS **B2B de gestão de operações esportivas** voltado a **clubes e federações** (não ao torcedor). Problema central: operação esportiva (cadastro, contratos, competições, partidas) é feita hoje em planilhas e sistemas fragmentados. Proposta de valor: **fonte única de verdade** para o ciclo competição → partida → consolidação, com auditoria e aprovações embutidas. Público-alvo: clubes profissionais e federações regionais no Brasil (MVP), com papéis `admin_tenant`, `gestor_clube`, `gestor_competicao`, `aprovador`, `delegado_partida`, `auditor_somente_leitura` e `admin_plataforma` (sistema).

## 2. Escopo — 26 não-objetivos (0.2.2, N-01 a N-26)

| Categoria | Itens | Desfecho |
|-----------|-------|----------|
| Esportivo-tático | N-01 a N-04 (análise tática, scouting, biometria, gestão de categorias de base avançada) | Diferidos em parte |
| Financeiro | N-05 a N-08 (folha, contabilidade, ERP, bilheteria) | Permanentes |
| B2C/Torcedor | N-09 a N-11 (app de torcida, ingressos, e-commerce, streaming) | Permanentes |
| Marketing | N-12 a N-14 (CRM de torcedor, redes sociais) | Permanentes |
| Infra/Mobile | N-15 a N-19 (isolamento físico, on-premise, app nativo, offline, migração automática) | Diferidos em parte |
| IA aberta | N-20 a N-23 (IA generativa aberta) | Permanentes |
| Governança | N-24 (compliance CBF/FIFA automatizado) | Diferido |
| BI/API | N-25 (BI self-service), N-26 (API pública) | Diferidos |

**Reclassificação (0.2.3):** 12 não-objetivos viram **futuro desejado** (F-01 a F-25, em 3 horizontes pós-MVP); **14 permanecem permanentes**. 7 implicações anti-regresso arquitetural definidas: `tenant_id`+RLS, API separada da UI, notificações abstraídas, aprovações como dados, auditoria com diff, IA assistiva, esquema normalizado.

## 3. Núcleo de dados — 25 entidades (0.3.1, E-01 a E-25)

16 de Núcleo + 9 de Suporte, em **7 grupos**:

- **A — Organização/acesso:** E-01 Organização (tenant), E-02 Assinatura, E-03 Usuário, E-04 Papel.
- **B — Pessoas:** E-05 Clube, E-06 Pessoa, E-07 Contrato, E-08 (atributos mínimos), E-09 Equipe/Categoria.
- **C — Estrutura esportiva:** declarada não-objetivo no MVP (N-12 a N-15).
- **D — Competições/partidas:** E-10 Competição, E-11 Edição, E-12 Fase/Rodada, E-13 Partida, E-14 Evento, E-15 Escalação.
- **E — Mercado/vínculos:** E-16 Negociação, E-17 Proposta, E-18 Anexo/Evidência.
- **F — Fluxos operacionais:** E-19 Fluxo de aprovação, E-20 Solicitação, E-21 Aprovação, E-22 Notificação.
- **G — Governança/observabilidade:** E-23 Auditoria/Log, E-24 Log de integração, E-25 Sistema externo.

Modelo **multi-tenant** com `tenant_id` em toda entidade de negócio e isolamento por **Row-Level Security**.

## 4. Relacionamentos — 27 vínculos (0.3.3, R01 a R27)

Cardinalidades: **1:1** (R02 Assinatura↔Organização, R18 Negociação↔Contrato origem), **1:N** (R01, R04–R06, R08, R10, R11, R13–R15, R17, R19–R22, R25–R27) e **N:N** via tabelas de junção `rel_usuario_papel` (R03), `rel_contrato_clube` (R07), `rel_equipe_atleta` (R09), `rel_edicao_clube` (R12), `rel_notificacao_usuario` (R24); polimórficas em R23 (Solicitação↔entidade) e R26 (Auditoria↔entidade). Cada vínculo declara 5 regras: Criação, Obrigatoriedade, Orphan safety (`CASCADE`/`SET NULL`/`RESTRICT`), Integridade Referencial Cruzada e Propagação de Estado. **8 regras transversais** cruzam tabelas (inscrição ativa exige clube ativo, escalação exige vínculo vigente, gol exige atleta em campo, approval mirror, coincidência de tenant, soft-delete preserva histórico, idempotência de integrações, imutabilidade pós-fato 24h).

## 5. Fluxos (0.4.1, 0.4.2)

**Fluxo principal** — ciclo de operação de uma edição de competição — **11 etapas (FP-01 a FP-11)**: onboarding do tenant → cadastro de clubes/pessoas → formalização de contratos → composição de equipes → configuração de competição/edição → inscrição de clubes → tabela de partidas → convocação/escalação → condução da partida → encerramento e consolidação → auditoria/dashboards. Mobiliza 22 das 25 entidades.

**4 gates de aprovação** (G-1 a G-4) modelados como dados via E-19/E-20/E-21: G-1 contrato, G-2 inscrição, G-3 reabertura de partida, G-4 encerramento de edição. **7 notificações** (N-1 a N-7) via E-22.

**12 fluxos secundários** (FS-01 a FS-12): gestão de usuários/papéis, gestão de contratos, negociação/transferência (com **gate G-5**), importação em lote, exportação, notificações, reabertura de partida, cotas/assinatura, arquivamento, WO/desistência, auditoria. **7 notificações** (NS-1 a NS-7). **3 máquinas de estados** encadeadas (Edição, Fase, Partida) + máquina do Contrato.

## 6. Pontos de falha — 80 modos (0.4.3)

| Namespace | Intervalo | Quantidade | Escopo |
|-----------|-----------|-----------|--------|
| PF-FP | 01 a 32 | 32 | Fluxo principal |
| PF-FS | 01 a 31 | 31 | Fluxos secundários |
| PF-G | 01 a 09 | 9 | Gates G-1 a G-5 |
| PF-X | 01 a 08 | 8 | Transversais de plataforma |

**Taxonomia de severidade:** C (Crítica — viola invariante), A (Alta — impede etapa), M (Média — degrada), B (Baixa — incômodo). **6 estratégias de tratamento:** bloqueio preventivo, rollback atômico, retry, gate de exceção, compensação manual, notificação + ação humana. Cobertura: 25/25 entidades, 10/10 invariantes, 8/8 regras transversais, 5/5 gates. **10 pendências resolvidas** com decisão consolidada (contrato rejeitado em G-1, escalação incompleta, gol com atleta não escalado, reabertura pós-imutabilidade, rollback de G-5, importação parcial, arquivamento de base, WO retroativo, desistência em andamento, commit por batch de 100 linhas).

## 7. Invariantes — 26 regras (0.5.1)

| Tier | Intervalo | Quantidade | Camada |
|------|-----------|-----------|--------|
| Estruturais | I-01 a I-10 | 10 | DB (constraint/trigger/RLS) |
| Domínio | T-1 a T-8 | 8 | DB + aplicação |
| Fronteira | IF-01 a IF-08 | 8 | Plataforma (server-side) |

Exemplos: I-01 pertencimento único ao tenant, I-03 contrato ativo único (Pessoa, Clube), I-06 11 titulares, I-08 proposta aceita única, I-09 auditoria append-only, T-4 approval mirror atômico, T-8 imutabilidade pós-fato (24h), IF-03 RLS em toda tabela, IF-07 idempotência por `correlation_id`. Princípio fundamental: **toda proteção de invariante é server-side** (trigger/constraint/RLS/transação). Matriz invariante × ponto de falha confirma cobertura total (59 PFs referenciados).

## 8. Fronteiras técnicas (0.5.2)

Estado de verdade é interno (webhooks são eventos, nunca gravação direta). Aplicação não bypassa invariantes. Multi-tenant via `tenant_id` + RLS. Aprovações como dados (E-19/E-20/E-21). Auditoria append-only com diff em JSONB. Notificações abstraídas por canal (in-app primário, e-mail secundário). Imutabilidade pós-fato calculada server-side (24h parametrizável).

## 9. Integrações externas — 5 contratos (0.5.3, INT-01 a INT-05)

| ID | Integração | Criticidade | Função |
|----|------------|------------|--------|
| INT-01 | Gateway de pagamento (Stripe/MP) | Crítica | Cobrança recorrente de assinaturas (E-02); webhook + reconciliação 1h |
| INT-02 | E-mail transacional (Postmark/SES) | Alta | Canal externo de notificação (E-22); webhook de bounce |
| INT-03 | Object storage S3-compatible | Alta | Anexos (E-18) e arquivos import/export; prefixo `tenant_id/` |
| INT-04 | Importação de arquivos (CSV/XLSX) | Média | Carga em lote via `admin_tenant` (FS-05); batch transacional 100 linhas |
| INT-05 | Exportação de arquivos (CSV/XLSX/PDF) | Média | Relatórios pré-definidos (FS-06); não é BI self-service |

Todas: **idempotentes** por `correlation_id` + `sistema_externo_id` UNIQUE (T-7, IF-07); **logadas** em E-24 com payload redigido (R27); **retry 3x backoff exponencial** + circuit breaker + fila de exceções; webhooks validam **HMAC** antes de qualquer mutação. 9 não-objetivos confirmados fora do MVP (N-09/N-11, N-18 a N-20, N-24 a N-26).

## 10. Decisões consolidadas para a Sprint 1

1. **Stack multi-tenant** via `tenant_id` + RLS em PostgreSQL; uma Assinatura ativa por tenant (I-02).
2. **Aprovações como dados** (E-19/E-20/E-21) — não há lógica de workflow hardcoded; gates são configuráveis por tenant.
3. **Auditoria append-only** (E-23) com diff JSONB; `UPDATE`/`DELETE` proibidos a todo papel (I-09).
4. **Imutabilidade pós-fato** (T-8, IF-04): partida concluída há > 24h só muta via G-3.
5. **Notificações abstraídas** (E-22): in-app primário, e-mail (INT-02) secundário.
6. **Idempotência** (T-7, IF-07) por `correlation_id` em toda integração.
7. **INT-01 e INT-02** são necessárias já na Sprint 1 (autenticação/assinatura e notificações); INT-03 na Sprint 2/4.
8. **Pendências encaminhadas:** escolha dos provedores de pagamento/e-mail/storage (Sprint 5); período de carência de inadimplência (6.1.3); retenção de E-24 (6.2.3); Regras de Competição paramétricas (2.2.4).

---

**Próxima subtask:** 0.6.2 — Registrar pendências abertas. **Handoff:** 0.6.3 (needs_review) prepara transição para a Sprint 1 (Fundação da plataforma).
