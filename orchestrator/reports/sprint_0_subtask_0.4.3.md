# Subtask 0.4.3 — Marcar pontos de falha

**Sprint:** Fundação, escopo e contratos
**Task:** Mapear fluxos
**Status:** completed
**Timestamp:** 2026-06-28T23:14:23.878192

---

## Output do OpenCode (GLM 5.2)

I'll start by exploring the existing reports to maintain consistency with what's already been produced in this sprint.
Let me read the most relevant prior reports to maintain consistency, especially the immediate predecessors 0.4.1 and 0.4.2, plus a smaller one for style reference.
Let me read the rest of the 0.4.2 report to capture the handoff section for 0.4.3.
I have full context now. The prior reports (0.4.1, 0.4.2) established conventions: 25 entities (E-01–E-25), 27 relationships (R01–R27), 10 invariants (I-01–I-10), 8 transversal rules, 26 non-objectives (N-01–N-26), main flow FP-01–FP-11 with gates G-1–G-4 and notifications N-1–N-7, and 12 secondary flows FS-01–FS-12 with gate G-5 and notifications NS-1–NS-7. The 0.4.2 handoff (Section 12) explicitly lists the failure points I must detail in 0.4.3.

I'll write the report in parts via heredocs (the approach that worked for the large 0.4.1/0.4.2 files).
Document complete at 920 lines. Let me validate structure and integrity, as the prior reports did.
Validation shows 79 unique failure points (32+31+8+8), all 10 invariants and all 8 transversal rules referenced. But G-4 and a few entities (E-08, E-10, E-13, E-24) don't appear as literal tags. Let me verify whether they're mentioned by name or genuinely missing.
G-4 (encerramento de Edição, defined in 0.4.1) is genuinely missing — I covered G-1–G-3 and G-5 but not G-4 specifically. The entities are referenced by name (Partida, Competição, Equipe), which is readable, but G-4 needs a failure point. Let me add PF-G-09 for G-4 and update the counts.
Now update the counts throughout to reflect 80 points (9 gates).
Now let me re-validate to confirm G-4 and E-13 are present and counts are consistent.
Still 2 occurrences of "79 pontos" remain. Let me find and fix them.
Let me add the remaining entity tags (E-08, E-10, E-24) for traceability consistency with prior reports.
Final validation pass:
Subtask **0.4.3 — Marcar pontos de falha** concluída e salva em `orchestrator/reports/sprint_0_subtask_0.4.3.md` (928 linhas).

**80 pontos de falha** catalogados em 4 namespaces: **PF-FP-01 a 32** (fluxo principal), **PF-FS-01 a 31** (12 fluxos secundários), **PF-G-01 a 09** (gates G-1 a G-5) e **PF-X-01 a 08** (transversais) — com taxonomia de severidade (C/A/M/B), 6 estratégias de tratamento, matrizes de detecção e severidade×probabilidade, e **10 pendências resolvidas** com decisão consolidada (Seção 10), incluindo as 8 sinalizadas nos handoffs de 0.4.1/0.4.2 (contrato rejeitado em G-1, escalação incompleta, gol com atleta não escalado, reabertura pós-imutabilidade, rollback de G-5, importação parcial, arquivamento de base, WO retroativo, desistência com partida em andamento). Cobertura completa: 25/25 entidades, 10/10 invariantes, 8/8 regras transversais, 5/5 gates. `needs_review: true` mantido como ponto de parada para revisão humana antes de encerrar a task 0.4.


## Stderr

```
[0m
> build · glm-5.2
[0m
[0m$ [0mls -la /home/alex/saas-futebol/orchestrator/reports/ 2>/dev/null && echo "---" && ls -la /home/alex/saas-futebol/orchestrator/ 2>/dev/null
total 212
drwxrwxr-x 2 alex alex  4096 jun 28 22:59 .
drwxrwxr-x 6 alex alex  4096 jun 28 22:41 ..
-rw-rw-r-- 1 alex alex  1214 jun 28 21:42 sprint_0_subtask_0.1.2.md
-rw-rw-r-- 1 alex alex  2352 jun 28 21:51 sprint_0_subtask_0.1.3.md
-rw-rw-r-- 1 alex alex  6114 jun 28 22:04 sprint_0_subtask_0.2.2.md
-rw-rw-r-- 1 alex alex  6973 jun 28 22:09 sprint_0_subtask_0.2.3.md
-rw-rw-r-- 1 alex alex  5710 jun 28 22:20 sprint_0_subtask_0.3.1.md
-rw-rw-r-- 1 alex alex  4689 jun 28 22:23 sprint_0_subtask_0.3.2.md
-rw-rw-r-- 1 alex alex 19343 jun 28 22:41 sprint_0_subtask_0.3.3.md
-rw-rw-r-- 1 alex alex 75570 jun 28 22:49 sprint_0_subtask_0.4.1.md
-rw-rw-r-- 1 alex alex 68644 jun 28 23:03 sprint_0_subtask_0.4.2.md
---
total 72
drwxrwxr-x 6 alex alex  4096 jun 28 22:41 .
drwxrwxr-x 5 alex alex  4096 jun 28 21:24 ..
drwxrwxr-x 2 alex alex  4096 jun 28 21:22 prompts
drwxrwxr-x 2 alex alex  4096 jun 28 21:41 __pycache__
drwxrwxr-x 2 alex alex  4096 jun 28 22:59 reports
-rw------- 1 alex alex 16525 jun 28 22:41 runner.py
-rw------- 1 alex alex 23901 jun 28 23:03 sprints.json
drwxrwxr-x 2 alex alex  4096 jun 28 21:23 state
-rw------- 1 alex alex  2975 jun 28 21:40 whatsapp_notify.py
[0m
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.4.1.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.4.2.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.1.3.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.4.2.md[90m [offset=582][0m
[0m
[0m$ [0mcat > /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE1'
# Subtask 0.4.3 — Marcar pontos de falha

**Sprint:** Fundação, escopo e contratos
**Task:** Mapear fluxos
**Status:** completed
**Época:** 2026-06-28
**Modelo:** opencode-go/glm-5.2
**needs_review:** true

---

## Output do OpenCode (GLM 5.2)

Documento técnico que cataloga e detalha os **pontos de falha** do SaaS de futebol — modos de falha do fluxo principal (FP-01 a FP-11, definido em 0.4.1), dos fluxos secundários (FS-01 a FS-12, definido em 0.4.2), dos gates de aprovação (G-1 a G-5) e das falhas transversais de plataforma — em conformidade com as 25 entidades (E-01 a E-25), os 27 relacionamentos (R01 a R27), os 10 invariantes (I-01 a I-10), as 8 regras transversais de 0.3.3, os 26 não-objetivos (N-01 a N-26) e as 7 implicações de desenho do MVP.

Resolve explicitamente as 8 pendências sinalizadas nos handoffs de 0.4.1 (Seção 12.2) e 0.4.2 (Seção 12.2), e estabelece o contrato de tratamento de erros que fundamenta a task 0.5 (Contratos e invariantes) e as tasks de observabilidade (1.4) e segurança (6.x).

---

# Pontos de falha — SaaS de Futebol

## 1. Sumário executivo

Mapear pontos de falha é o fechamento da task 0.4 (Mapear fluxos). O fluxo principal (0.4.1) e os 12 fluxos secundários (0.4.2) descrevem o caminho feliz e os gates de aprovação; resta catalogar **onde, por que e como** cada fluxo pode falhar, qual a severidade, como o sistema detecta, qual o impacto sobre invariantes e entidades, e qual a estratégia de recuperação.

**Conteúdo produzido:**

- **79 pontos de falha** catalogados, em 4 namespaces distintos:
  - **PF-FP-01 a PF-FP-32** — fluxo principal (32 pontos)
  - **PF-FS-01 a PF-FS-31** — fluxos secundários (31 pontos)
  - **PF-G-01 a PF-G-08** — gates de aprovação (8 pontos)
  - **PF-X-01 a PF-X-08** — transversais de plataforma (8 pontos)
- **Taxonomia de severidade** em 4 níveis (Crítica, Alta, Média, Baixa) alinhada aos invariantes I-01 a I-10
- **6 estratégias de tratamento** padronizadas (bloqueio preventivo, rollback atômico, retry, gate de exceção, compensação manual, notificação + ação humana)
- **Matriz de detecção** por mecanismo (trigger DB, validação de aplicação, job, RBAC, observabilidade/KPI)
- **Resolução das 8 pendências** sinalizadas em 0.4.1/0.4.2 (Seção 10)
- **Cobertura:** todos os 10 invariantes e todas as 8 regras transversais têm ao menos um ponto de falha que os protege ou os exerce no sentido de exceção

**Convenção de nomeação:**

- Pontos de falha: **PF-FP-NN** (fluxo principal), **PF-FS-NN** (fluxo secundário), **PF-G-NN** (gate), **PF-X-NN** (transversal)
- Severidade: **C** (Crítica), **A** (Alta), **M** (Média), **B** (Baixa)
- Os namespaces N-* / NS-* (notificações), N-XX (não-objetivos) e F-* (futuro desejado) permanecem distintos e são referenciados quando um ponto de falha dispara ou respeita um deles

---

## 2. Taxonomia de falhas

### 2.1 Níveis de severidade

| Nível | Nome | Critério | SLA de tratamento |
|-------|------|----------|-------------------|
| **C** | Crítica | Viola invariante de negócio (I-01 a I-10), corrompe dado histórico imutável, ou bloqueia todo o fluxo principal do tenant | Bloqueio preventivo (trigger BEFORE) ou rollback atômico imediato; intervenção humana se inevitável |
| **A** | Alta | Impede uma etapa do fluxo, exige correção antes de prosseguir, ou gera inconsistência transitória entre entidades | Detecção síncrona + notificação alta (N-3/N-4/NS-2/NS-5/NS-7); gate de exceção quando cabível |
| **M** | Média | Degrada experiência ou performance; recuperável por retry ou correção pelo próprio usuário | Detecção assíncrona (job/KPI) + notificação média (N-1/N-5/NS-1/NS-3/NS-6) |
| **B** | Baixa | Incômodo operacional sem impacto em integridade de dados | Log + KPI de observabilidade (task 1.4); sem notificação |

### 2.2 Estratégias de tratamento

| Estratégia | Mecanismo | Aplicação |
|------------|-----------|-----------|
| **Bloqueio preventivo** | Trigger `BEFORE INSERT/UPDATE` rejeita; constraint `UNIQUE/CHECK`; RBAC nega | Falhas que violariam invariante — nunca devem ocorrer |
| **Rollback atômico** | Transação DB reverte todos os efeitos colaterais ao detectar violação pós-deferimento | Gates G-1/G-5 com efeitos colaterais múltiplos |
| **Retry** | Job reprocessa com `correlation_id` (idempotência, regra transversal 7) | Falhas transientes de infra/conexão |
| **Gate de exceção** | Abre Solicitação (E-20) para aprovação humana via E-19/E-20/E-21 | Quebra controlada de imutabilidade (G-3) ou WO (FS-11) |
| **Compensação manual** | `admin_plataforma` (papel de sistema) intervém fora do escopo do tenant | Incidentes cross-tenant, órfãos de tenant, reabertura forçada |
| **Notificação + ação humana** | E-22 dispara ao papel responsável; estado permanece consistente | Pendências de aprovação, escalação incompleta, cota próxima |

### 2.3 Mecanismos de detecção

- **Trigger DB:** validação em `BEFORE` (rejeita) ou `AFTER` (recalcula/audita)
- **Validação de aplicação:** camada de serviço valida pré-condições antes de mutar
- **Job agendado:** varredura periódica (expirações, cotas, imutabilidade, poda)
- **RBAC + RLS:** negação de acesso por papel/tenant (I-01, I-10)
- **Observabilidade/KPI:** alerta sobre métrica de saúde (task 1.4, Seções 11 de 0.4.1/0.4.2)
PARTE1
echo "Parte 1 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 1 escrita
75 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mcat >> /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE2'

---

## 3. Catálogo mestre de pontos de falha

Tabela única com os 79 pontos de falha. As colunas **Sev.** (severidade), **Detecção** e **Tratamento** usam os códigos das Seções 2.1–2.3. A coluna **Guarda** indica qual invariante (I-XX) ou regra transversal (T-1 a T-8) o ponto de falha protege ou exercita no sentido de exceção.

### 3.1 Fluxo principal (PF-FP-01 a PF-FP-32)

| ID | Etapa | Modo de falha | Sev. | Detecção | Tratamento | Guarda |
|----|-------|---------------|------|----------|------------|--------|
| PF-FP-01 | FP-01 | Checkout/pagamento falha — tenant não criado | M | Aplicação | Notificação + ação humana | I-02 |
| PF-FP-02 | FP-01 | RLS policy/tenant órfão após falha pós-checkout | C | Job | Compensação manual | I-01 |
| PF-FP-03 | FP-02 | Cota de clubes/pessoas excedida | A | Aplicação | Bloqueio preventivo + NS-1 | I-02 |
| PF-FP-04 | FP-02 | Violação UNIQUE (categoria, genero) da Equipe | A | Trigger DB | Bloqueio preventivo | R08/I-07 |
| PF-FP-05 | FP-02 | Upload de escudo falha (transiente) | B | Aplicação | Retry | — |
| PF-FP-06 | FP-03 | G-1 rejeitado — contrato não ativa | A | Gate | Notificação NS-2 + estado `rejeitado` | T-4 |
| PF-FP-07 | FP-03 | I-03 violado — Pessoa já tem contrato ativo no Clube | C | Trigger DB | Bloqueio preventivo | I-03 |
| PF-FP-08 | FP-03 | `data_inicio > hoje` — contrato no futuro | A | Aplicação | Bloqueio preventivo | — |
| PF-FP-09 | FP-04 | I-04 violado — atleta já vinculado à mesma Equipe no período | C | Trigger DB | Bloqueio preventivo | I-04 |
| PF-FP-10 | FP-04 | Contrato rescindido durante vínculo ativo (órfão) | A | Trigger AFTER | Rollback atômico + NS-3 | T-2 |
| PF-FP-11 | FP-05 | `ano_temporada` duplicado para mesma Competição | A | Trigger DB | Bloqueio preventivo | R10/R11 |
| PF-FP-12 | FP-05 | Ordem de Fase não sequencial (I-07) | A | Trigger DB | Bloqueio preventivo | I-07 |
| PF-FP-13 | FP-06 | G-2 rejeitado — clube não habilitado | A | Gate | Notificação com motivo | T-1 |
| PF-FP-14 | FP-06 | `limite_participantes` excedido | A | Aplicação | Bloqueio preventivo | R12 |
| PF-FP-15 | FP-06 | Clube inativo tenta inscrição | C | Aplicação | Bloqueio preventivo | T-1 |
| PF-FP-16 | FP-06 | Quórum não atingido — edição não publica | M | Aplicação | Notificação + ação humana | — |
| PF-FP-17 | FP-07 | I-05 violado — mandante = visitante | C | Trigger DB | Bloqueio preventivo | I-05 |
| PF-FP-18 | FP-07 | < 2 clubes inscritos para gerar tabela | A | Aplicação | Bloqueio preventivo | — |
| PF-FP-19 | FP-07 | Conflito de datahora (mandante já tem jogo) | M | Aplicação | Notificação + ação humana | — |
| PF-FP-20 | FP-08 | Escalação incompleta no prazo (janela fecha sem 11) | A | Job | Gate de exceção (WO) + NS-7 | I-06 |
| PF-FP-21 | FP-08 | I-06 violado — > 11 titulares | C | Trigger DB | Bloqueio preventivo | I-06 |
| PF-FP-22 | FP-08 | Atleta escalado sem contrato vigente | C | Trigger DB | Bloqueio preventivo | T-2 |
| PF-FP-23 | FP-08 | Numeração de camisa duplicada (R17) | A | Trigger DB | Bloqueio preventivo | R17 |
| PF-FP-24 | FP-08 | Atleta suspenso por cartão vermelho escalado | A | Aplicação | Bloqueio preventivo | R15/R16 |
| PF-FP-25 | FP-09 | Gol com atleta não escalado (T-3) | C | Trigger DB | Bloqueio preventivo | T-3 |
| PF-FP-26 | FP-09 | Evento de atleta após cartão vermelho | C | Trigger DB | Bloqueio preventivo | R15/R16 |
| PF-FP-27 | FP-09 | Queda de conexão do delegado em campo | M | Aplicação | Retry + buffer local | — |
| PF-FP-28 | FP-10 | Mutação direta em partida concluída > 24h | C | Trigger DB | Bloqueio preventivo + meta-auditoria | T-8 |
| PF-FP-29 | FP-10 | G-3 rejeitado — partida permanece concluída | A | Gate | Notificação + auditoria | T-8 |
| PF-FP-30 | FP-10 | Classificação recalculada inconsistente | C | Job | Retry + compensação manual | PE R11 |
| PF-FP-31 | FP-11 | Dashboard lento (> 2s p99) | M | KPI | Otimização (task 1.4) | — |
| PF-FP-32 | FP-11 | RLS leak — dados de outro tenant vazam | C | RBAC + KPI | Bloqueio preventivo + compensação manual | I-01 |

### 3.2 Fluxos secundários (PF-FS-01 a PF-FS-31)

| ID | Fluxo | Modo de falha | Sev. | Detecção | Tratamento | Guarda |
|----|-------|---------------|------|----------|------------|--------|
| PF-FS-01 | FS-01 | Cota de usuários excedida | A | Aplicação | Bloqueio preventivo + NS-1 | I-02 |
| PF-FS-02 | FS-01 | E-mail duplicado no tenant | A | Trigger DB | Bloqueio preventivo | — |
| PF-FS-03 | FS-01 | Atribuição de papel cross-tenant | C | Trigger DB | Bloqueio preventivo | T-5/I-10 |
| PF-FS-04 | FS-03 | Renovação com gap/sobreposição (I-03) | C | Trigger DB | Bloqueio preventivo | I-03 |
| PF-FS-05 | FS-03 | Rescisão invalida escalações em edição ativa | A | Trigger AFTER | Rollback atômico + NS-3 + gate | T-2 |
| PF-FS-06 | FS-03 | Job de expiração automática não roda | A | Job de watchdog | Retry + compensação manual | — |
| PF-FS-07 | FS-04 | I-08 violado — 2ª proposta aceita | C | Trigger DB (constraint parcial) | Bloqueio preventivo | I-08 |
| PF-FS-08 | FS-04 | G-5 deferido mas I-03 falha no destino | C | Trigger DB pós-deferimento | Rollback atômico + NS-5 | I-03/T-4 |
| PF-FS-09 | FS-04 | Negociação cancelada após proposta aceita | M | Aplicação | Rollback de E-18 anexos + NS-5 | — |
| PF-FS-10 | FS-04 | Contrato de origem inativo (R18) | A | Aplicação | Bloqueio preventivo | R18 |
| PF-FS-11 | FS-04 | Clube comprador = vendedor (R07) | C | Trigger DB | Bloqueio preventivo | R07 |
| PF-FS-12 | FS-04 | Proposta aceita sem evidências (R20) | A | Trigger DB | Bloqueio preventivo | R20 |
| PF-FS-13 | FS-05 | Importação parcial — commit por batch vs rollback | A | Aplicação | Commit por batch + relatório de falhas | T-7 |
| PF-FS-14 | FS-05 | Arquivo > 10MB ou > 5000 linhas | M | Aplicação | Bloqueio preventivo + NS-6 | — |
| PF-FS-15 | FS-05 | Encoding inválido / cabeçalho incorreto | M | Aplicação | Bloqueio preventivo + relatório | — |
| PF-FS-16 | FS-05 | Conflito de dados (pular vs sobrescrever) | M | Aplicação | Política `pular` padrão + relatório | T-7 |
| PF-FS-17 | FS-06 | Exportação assíncrona timeout | M | Job | Retry + NS-6 | — |
| PF-FS-18 | FS-06 | Link de download expirado (< 24h) | B | Aplicação | Notificação + reexecução | — |
| PF-FS-19 | FS-07 | E-mail bounce | M | KPI | Retry + fallback in-app | — |
| PF-FS-20 | FS-07 | Acúmulo de notificações não lidas | B | KPI | Job de resumo consolidado | — |
| PF-FS-21 | FS-08 | Reabertura < 24h com classificação já consolidada | A | Aplicação | Recalculo retroativo + NS-7 | T-8 |
| PF-FS-22 | FS-08 | Recalculo de classificação inconsistente após reabertura | C | Job | Retry + compensação manual | PE R11 |
| PF-FS-23 | FS-09 | Downgrade rejeitado (cotas excedentes) | M | Aplicação | Bloqueio preventivo + NS-1 | I-02 |
| PF-FS-24 | FS-09 | Suspensão por inadimplência em produção | A | Job externo | Notificação + carência + FS-10 | I-02 |
| PF-FS-25 | FS-10 | Arquivamento com inscrição ativa em edição | A | Aplicação | Bloqueio preventivo ( exige FS-11) | T-1 |
| PF-FS-26 | FS-10 | Arquivamento com vínculos em equipes de base | M | Aplicação | Soft-delete cascade uniforme + NS-3 | T-6 |
| PF-FS-27 | FS-11 | WO retroativo — resultados já jogados | A | Aplicação | Política: preservar (não anular) + NS-7 | T-6 |
| PF-FS-28 | FS-11 | Desistência com partida `em_andamento` | A | Aplicação | Não interromper; placar de campo prevalece + NS-7 | — |
| PF-FS-29 | FS-11 | WO 3-0 mas adversário já perdeu a partida | M | Aplicação | Preservar placar real se `concluida`; WO só para futuras | — |
| PF-FS-30 | FS-12 | Tentativa de mutação na auditoria | C | Trigger BEFORE | Bloqueio preventivo + meta-auditoria | I-09 |
| PF-FS-31 | FS-12 | Auditoria cresce sem retenção definida | M | KPI | Política de retenção (task 6.2.3) | I-09 |

### 3.3 Gates de aprovação (PF-G-01 a PF-G-08)

| ID | Gate | Modo de falha | Sev. | Detecção | Tratamento | Guarda |
|----|------|---------------|------|----------|------------|--------|
| PF-G-01 | G-1 a G-5 | Aprovador inexistente ou inativo | A | Job | Notificação + reatribuição (FS-01) | R21/R22 |
| PF-G-02 | G-1 a G-5 | Timeout de aprovação (solicitação expira) | M | Job | Arquivar + NS ao proponente + reabrir | — |
| PF-G-03 | G-1 a G-5 | Ordem de etapa violada (R21/R22) | A | Trigger DB | Bloqueio preventivo | R21/R22 |
| PF-G-04 | G-1 a G-5 | Aprovador tenta deferir fora de sua etapa | A | Trigger DB | Bloqueio preventivo | R21/R22 |
| PF-G-05 | G-3 | G-3 deferido mas partida já arquivada (WO) | A | Aplicação | Bloqueio preventivo — partida em WO é terminal | T-8 |
| PF-G-06 | G-5 | Rollback parcial — efeito colateral executa pela metade | C | Trigger DB | Rollback atômico (transação única) + NS-5 | T-4 |
| PF-G-07 | G-1 a G-5 | Duplo deferimento concorrente (race na última etapa) | C | Trigger DB (lock) | Bloqueio preventivo (SELECT FOR UPDATE) | T-4 |
| PF-G-08 | G-1 a G-5 | Reabertura de Solicitação arquivada | A | Trigger DB | Bloqueio preventivo | — |

### 3.4 Transversais de plataforma (PF-X-01 a PF-X-08)

| ID | Escopo | Modo de falha | Sev. | Detecção | Tratamento | Guarda |
|----|--------|---------------|------|----------|------------|--------|
| PF-X-01 | FP-08 | Race condition — 2 gestores editam escalação simultaneamente | C | Trigger DB (lock) | Bloqueio preventivo (row lock) | I-06 |
| PF-X-02 | G-5 | Queda de DB durante transação atômica | C | DB (transação) | Rollback atômico + retry | T-4 |
| PF-X-03 | Toda leitura | RLS bypass / acesso cross-tenant | C | RBAC + KPI | Bloqueio preventivo + compensação manual | I-01 |
| PF-X-04 | Todo INSERT | `tenant_id` NULL em mutação | C | Trigger DB (NOT NULL) | Bloqueio preventivo | I-10 |
| PF-X-05 | Toda mutação | Trigger de auditoria falha (I-09 comprometido) | C | Trigger AFTER | Rollback atômico (auditoria é obrigatória) | I-09 |
| PF-X-06 | FP-10/FS-08 | Relógio desincronizado — janela 24h calculada errada | C | NTP + KPI | Sincronização NTP + compensação manual | T-8 |
| PF-X-07 | PE R11 | Job de recálculo de classificação falha | A | Job de watchdog | Retry + compensação manual | PE R11 |
| PF-X-08 | FS-09 | Gateway de pagamento divergente do estado interno | A | Reconciliação (job) | Retry + compensação manual | I-02 |
PARTE2
echo "Parte 2 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 2 escrita
180 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mcat >> /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE3'

---

## 4. Detalhamento — Pontos de falha do fluxo principal

Cada ponto de falha declara **modo**, **causa**, **detecção**, **impacto** (entidades/invariantes/etapas downstream), **severidade** e **tratamento**. Os pontos sinalizados como pendências em 0.4.1/0.4.2 são marcados com **[PENDÊNCIA]**.

### 4.1 FP-01 — Onboarding do tenant

**PF-FP-01 — Falha no checkout/pagamento impede criação do tenant**
- **Causa:** gateway de pagamento externo recusa cartão ou timeout.
- **Detecção:** aplicação recebe erro síncrono do gateway.
- **Impacto:** nenhuma entidade criada; E-01/E-02 não existem; fluxo principal não inicia.
- **Severidade:** M — não corrompe dados; usuário pode retry.
- **Tratamento:** notificação in-app com motivo; nenhum estado parcial persistido (validação pré-criação).

**PF-FP-02 — RLS policy/tenant órfão após falha pós-checkout**
- **Causa:** checkout confirma, mas falha transiente na criação das policies de RLS ou do `admin_tenant` (E-03) inicial.
- **Detecção:** job de watchdog verifica `organizacao.status = 'ativa'` sem admin vinculado (R03) ou sem RLS policy.
- **Impacto:** tenant pago sem acesso; I-01 comprometido se houver mutação cross-tenant.
- **Severidade:** C — tenant em estado inconsistente.
- **Tratamento:** compensação manual por `admin_plataforma` (recria admin/policies ou reembolsa); NS-1 ao contato comercial.

### 4.2 FP-02 — Cadastro de clubes e pessoas

**PF-FP-03 — Cota de clubes/pessoas excedida**
- **Causa:** tentativa de cadastro além do limite do plano (R02, I-02).
- **Detecção:** aplicação consulta `assinatura` + contagem antes do INSERT.
- **Impacto:** E-05/E-06 não criados; FP-04/FP-08 sem elenco disponível.
- **Severidade:** A — bloqueia cadastro fundacional.
- **Tratamento:** bloqueio preventivo + NS-1 sugerindo upgrade (FS-09) ou arquivamento (FS-10).

**PF-FP-04 — Violação UNIQUE (categoria, genero) da Equipe**
- **Causa:** `gestor_clube` cria Equipe (E-09) com par já existente no Clube (R08).
- **Detecção:** trigger `BEFORE INSERT`/constraint UNIQUE composta.
- **Impacto:** E-09 rejeitado; I-07 análogo preservado.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; mensagem orienta a editar a Equipe existente.

**PF-FP-05 — Upload de escudo falha (transiente)**
- **Causa:** falha de rede/armazenamento no upload do escudo do Clube.
- **Detecção:** aplicação recebe erro de storage.
- **Impacto:** Clube criado sem escudo (campo opcional); sem impacto em integridade.
- **Severidade:** B.
- **Tratamento:** retry automático (3x); Clube persiste sem escudo; usuário pode reenviar depois.

### 4.3 FP-03 — Formalização de contratos (G-1)

**PF-FP-06 — G-1 rejeitado: contrato não ativa** [PENDÊNCIA 0.4.1]
- **Causa:** `aprovador` rejeita a Solicitação (E-20) `tipo_ref = 'contrato'` em G-1.
- **Detecção:** decisão de Aprovação (E-21) com `decisao = 'rejeitado'`.
- **Impacto:** `contrato.status = 'rejeitado'` (estado terminal da máquina do Contrato, Seção 4.3 de 0.4.2); FP-04 (composição de equipes) bloqueada para esse atleta; FP-08 futura sem o atleta elegível. Pessoa permanece elegível para outro vínculo.
- **Severidade:** A — fluxo principal ramifica para exceção.
- **Tratamento:** NS-2 ao `gestor_clube` proponente com motivo; Solicitação arquivada; auditoria grava diff (I-09). Atleta pode ser objeto de nova proposta (novo Contrato em `rascunho`).

**PF-FP-07 — I-03 violado: Pessoa já tem contrato ativo no Clube**
- **Causa:** proponente tenta criar contrato enquanto existe `contrato.status = 'ativo'` para a mesma (Pessoa, Clube) (R04/R05/R06).
- **Detecção:** trigger `BEFORE INSERT` valida constraint parcial UNIQUE `(pessoa_id, clube_id) WHERE status = 'ativo'`.
- **Impacto:** INSERT rejeitado; I-03 preservado.
- **Severidade:** C — invariante de negócio.
- **Tratamento:** bloqueio preventivo; mensagem identifica o contrato ativo conflitante.

**PF-FP-08 — `data_inicio > hoje`: contrato no futuro**
- **Causa:** proponente registra `data_inicio` posterior à data atual; G-1 deferiria um contrato ainda não vigente.
- **Detecção:** validação de aplicação antes de abrir Solicitação.
- **Impacto:** Solicitação não criada; FP-04 não habilita vínculo.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; `data_inicio` deve ser `<= hoje` (pré-condição declarada em 0.4.1 FP-03).

### 4.4 FP-04 — Composição de equipes

**PF-FP-09 — I-04 violado: atleta já vinculado à mesma Equipe no período**
- **Causa:** tentativa de criar `rel_equipe_atleta` ativo quando já existe vínculo ativo para mesma (Equipe, Atleta) no período (R09).
- **Detecção:** trigger `BEFORE INSERT` valida constraint parcial UNIQUE.
- **Impacto:** vínculo rejeitado; I-04 preservado; atleta não duplicado em escalação.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo.

**PF-FP-10 — Contrato rescindido durante vínculo ativo (órfão)**
- **Causa:** `rel_equipe_atleta` ativo existe, mas o Contrato (E-07) subjacente é rescindido (via FS-03) ou expira sem trigger de cascade.
- **Detecção:** trigger `AFTER UPDATE` de Contrato encerra `rel_equipe_atleta.dt_fim` (PE de R09); job de watchdog verifica órfãos.
- **Impacto:** atleta perde elegibilidade para FP-08; se já escalado em partida `agendada`, escalação deve ser revalidada (impacto em PF-FP-22).
- **Severidade:** A.
- **Tratamento:** rollback atômico do vínculo (encerra `dt_fim`); NS-3 ao `gestor_clube`; se partida futura afetada, NS-7 ao `delegado_partida`.

### 4.5 FP-05 — Configuração da competição e edição

**PF-FP-11 — `ano_temporada` duplicado para mesma Competição**
- **Causa:** `gestor_competicao` cria Edição (E-11) com `(competicao_id, ano_temporada)` já existente (R10/R11).
- **Detecção:** trigger `BEFORE INSERT`/constraint UNIQUE composta.
- **Impacto:** Edição rejeitada.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo.

**PF-FP-12 — Ordem de Fase não sequencial (I-07)**
- **Causa:** Fases (E-12) criadas com `ordem` duplicada ou com gap dentro da Edição (R11, I-07).
- **Detecção:** trigger `BEFORE INSERT/UPDATE` valida `ordem` UNIQUE e sequencial.
- **Impacto:** Fase rejeitada; tabela de partidas (FP-07) não pode ser gerada.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo.

### 4.6 FP-06 — Inscrição de clubes (G-2)

**PF-FP-13 — G-2 rejeitado: clube não habilitado**
- **Causa:** `aprovador` rejeita inscrição (E-20 `tipo_ref = 'inscricao_edicao'`).
- **Detecção:** Aprovação (E-21) `rejeitado`.
- **Impacto:** `rel_edicao_clube` não se torna válida; Clube não recebe partidas; FP-07 exclui o Clube da tabela.
- **Severidade:** A.
- **Tratamento:** notificação com motivo ao `gestor_clube`; Clube pode corrigir pendência e reabrir solicitação.

**PF-FP-14 — `limite_participantes` excedido**
- **Causa:** número de inscritos deferidos atingiu `Competicao.limite_participantes` (R12).
- **Detecção:** aplicação valida contagem antes de aceitar nova inscrição.
- **Impacto:** inscrição bloqueada; edição pode não atingir quórum esperado se o limite foi mal configurado.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; NS-1 ao `gestor_competicao` sugerindo revisar limite.

**PF-FP-15 — Clube inativo tenta inscrição**
- **Causa:** Clube em `status <> 'ativo'` (arquivado/suspenso) solicita inscrição.
- **Detecção:** aplicação valida `clube.status = 'ativo'` antes de abrir Solicitação.
- **Impacto:** violaria regra transversal 1; bloqueado.
- **Severidade:** C — invariante de integridade competitiva.
- **Tratamento:** bloqueio preventivo; mensagem orienta reativação via FS-10.

**PF-FP-16 — Quórum não atingido: edição não publica**
- **Causa:** inscrições deferidas < quórum definido (pendência 0.4.1 Seção 12.2; critério a ser detalhado em 2.2.1).
- **Detecção:** aplicação/jo avalia `COUNT(rel_edicao_clube ativa) >= quórum`.
- **Impacto:** Edição permanece em `rascunho`/`publicada` sem avançar para `em_andamento`; FP-07 não gera tabela.
- **Severidade:** M — não corrompe dados; bloqueia avanço.
- **Tratamento:** notificação + ação humana (`gestor_competicao` convoca mais clubes ou reconfigura a Edição).

### 4.7 FP-07 — Tabela de partidas

**PF-FP-17 — I-05 violado: mandante = visitante**
- **Causa:** gerador de tabela ou edição manual produz Partida com `mandante_id = visitante_id` (R13/R14).
- **Detecção:** trigger `BEFORE INSERT`/CHECK constraint.
- **Impacto:** Partida rejeitada; I-05 preservado.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo.

**PF-FP-18 — < 2 clubes inscritos para gerar tabela**
- **Causa:** `gestor_competicao` tenta gerar tabela com menos de 2 clubes válidos.
- **Detecção:** aplicação valida antes de gerar.
- **Impacto:** tabela não gerada; FP-08/FP-09 sem partidas.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo.

**PF-FP-19 — Conflito de datahora (mandante já tem jogo)**
- **Causa:** Partida agendada com `datahora` sobreposta a outra do mesmo Clube como mandante/visitante.
- **Detecção:** aplicação valida sobreposição de janela por Clube.
- **Impacto:** tabela parcialmente gerada; calendário inconsistente.
- **Severidade:** M.
- **Tratamento:** notificação + ação humana (`gestor_competicao` realoca `datahora`).
PARTE3
echo "Parte 3 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 3 escrita
333 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mcat >> /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE4'

### 4.8 FP-08 — Convocação e escalação de atletas

**PF-FP-20 — Escalação incompleta no prazo (janela fecha sem 11 titulares)** [PENDÊNCIA 0.4.1]
- **Causa:** janela de escalação (antecedência mínima — parâmetro por Regra de Competição, pendência 2.2.4) fecha com menos de 11 titulares confirmados; ou `gestor_clube` não finaliza; ou `delegado_partida` não confirma em campo.
- **Detecção:** job no fechamento da janela verifica `escalacao.status` e `COUNT(titulares) = 11` (I-06).
- **Impacto:** Partida não pode mover para `pronta` (máquina da Partida, Seção 4.3 de 0.4.1); FP-09 bloqueada; risco de WO.
- **Severidade:** A — bloqueia condução.
- **Tratamento:** gate de exceção — `gestor_competicao` pode (a) prorrogar a janela por tempo limitado, (b) aceitar escalação incompleta como WO técnico (caminho FS-11), ou (c) reagendar a Partida. NS-7 ao `gestor_clube`, `delegado_partida` e `gestor_competicao`. Decisão consolidada: **WO técnico não é automático**; exige ato do `gestor_competicao` (resolução da pendência 0.4.1).

**PF-FP-21 — I-06 violado: > 11 titulares**
- **Causa:** `gestor_clube` escala mais de 11 titulares em uma Escalação (E-15) (R17, I-06).
- **Detecção:** trigger `BEFORE INSERT` em `rel_escalacao_atleta` valida count + flag `titular`.
- **Impacto:** INSERT rejeitado; I-06 preservado.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo.

**PF-FP-22 — Atleta escalado sem contrato vigente**
- **Causa:** atleta em `rel_equipe_atleta` sem Contrato ativo, ou vínculo encerrado após a escalação (via PF-FP-10).
- **Detecção:** trigger `BEFORE INSERT` valida `rel_equipe_atleta.dt_fim IS NULL` AND `contrato.status = 'ativo'` (regra transversal 2).
- **Impacto:** atleta rejeitado na escalação; I-04/T-2 preservados.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo.

**PF-FP-23 — Numeração de camisa duplicada (R17)**
- **Causa:** dois atletas da mesma Equipe escalados com o mesmo número de camisa na Partida (R17).
- **Detecção:** trigger `BEFORE INSERT` valida UNIQUE `(partida_id, equipe_id, numero_camisa)`.
- **Impacto:** segundo INSERT rejeitado.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo.

**PF-FP-24 — Atleta suspenso por cartão vermelho escalado** [PENDÊNCIA derivada de R15/R16]
- **Causa:** atleta recebeu cartão vermelho em partida anterior dentro do período de suspensão definido por Regra de Competição (pendência 2.2.4) e é escalado.
- **Detecção:** aplicação consulta histórico de Eventos (E-14) `tipo = 'cartao_vermelho'` e janela de suspensão antes de confirmar a Escalação.
- **Impacto:** se não detectado, violaria a sanção esportiva; se detectado, escalação do atleta rejeitada.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo na confirmação; NS-3 ao `gestor_clube` indicando o motivo (suspensão). Decisão consolidada: **a validação é síncrona na confirmação da escalação**, não em tempo de INSERT de evento (não há reabertura retroativa da partida já concluída).

### 4.9 FP-09 — Condução da partida

**PF-FP-25 — Gol com atleta não escalado (T-3)** [PENDÊNCIA 0.4.1]
- **Causa:** `delegado_partida` registra Evento (E-14) `tipo = 'gol'` com `atleta_id` que não está na Escalação (E-15) confirmada de nenhuma das Equipes (regra transversal 3).
- **Detecção:** trigger `BEFORE INSERT` em Evento valida `atleta_id IN (SELECT atleta_id FROM rel_escalacao_atleta WHERE partida_id = NEW.partida_id)`.
- **Impacto:** Evento rejeitado; placar não é corrompido; T-3 preservado.
- **Severidade:** C — risco de placar inválido.
- **Tratamento:** bloqueio preventivo; delegado recebe mensagem em tempo real e deve corrigir o `atleta_id`.

**PF-FP-26 — Evento de atleta após cartão vermelho**
- **Causa:** novo Evento (gol/cartão/substituição) referindo um atleta que já recebeu cartão vermelho na mesma Partida (R15/R16).
- **Detecção:** trigger `BEFORE INSERT` valida ausência de `cartao_vermelho` prévio para o `atleta_id` na Partida.
- **Impacto:** Evento rejeitado; sanção preservada.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo.

**PF-FP-27 — Queda de conexão do delegado em campo**
- **Causa:** `delegado_partida` perde conectividade durante a partida; eventos não são enviados em tempo real.
- **Detecção:** aplicação detecta heartbeat interrompido; KPI `latencia_evento` (0.4.1 Seção 11).
- **Impacto:** eventos podem ser registrados offline e sincronizados depois; risco de ordem incorreta se dois operadores agem.
- **Severidade:** M — não corrompe integridade (trigger valida em INSERT server-side).
- **Tratamento:** buffer local no dispositivo (PWA) com `correlation_id`; retry com idempotência (regra transversal 7); N-4 ao vivo pode ser postergada. Não há streaming (não-objetivo N-24), então latência de painel público interno é tolerável.

### 4.10 FP-10 — Encerramento e consolidação

**PF-FP-28 — Mutação direta em partida concluída > 24h** [PENDÊNCIA 0.4.1]
- **Causa:** qualquer mutação direta (UPDATE em Partida/Evento/Escalação) fora do fluxo FS-08/G-3 em partida `concluida` há mais de 24h (regra transversal 8).
- **Detecção:** trigger `BEFORE UPDATE/DELETE` valida `now() - concluida_em > 24h` AND ausência de Solicitação `tipo_ref = 'partida_reabertura'` deferida.
- **Impacto:** mutação rejeitada; imutabilidade preservada; tentativa registrada como evento de segurança (meta-auditoria).
- **Severidade:** C — protege o dado histórico mais sensível.
- **Tratamento:** bloqueio preventivo + meta-auditoria (I-09); única via legítima é FS-08 via G-3.

**PF-FP-29 — G-3 rejeitado: partida permanece concluída**
- **Causa:** `aprovador` rejeita reabertura (E-20 `tipo_ref = 'partida_reabertura'`).
- **Detecção:** Aprovação `rejeitado`.
- **Impacto:** partida permanece `concluida`; classificação consolidada não muda.
- **Severidade:** A.
- **Tratamento:** auditoria registra tentativa + motivo; NS-7 ao solicitante; sem efeito colateral.

**PF-FP-30 — Classificação recalculada inconsistente**
- **Causa:** trigger de recálculo de classificação (PE de R11) falha após encerramento/reabertura, deixando classificação dessincronizada do placar.
- **Detecção:** job de reconciliação compara `SUM(pontos por partida)` vs. `classificacao.pontos` por Edição.
- **Impacto:** dashboards (FP-11) mostram dado errado; risco de decisão competitiva injusta.
- **Severidade:** C.
- **Tratamento:** retry do job de recálculo; se persistir, compensação manual por `admin_plataforma` com auditoria; KPI `dashboards_disponibilidade`.

### 4.11 FP-11 — Auditoria, relatórios e dashboards

**PF-FP-31 — Dashboard lento (> 2s p99)**
- **Causa:** consulta de classificação/artilharia sem índice apropriado ou volume elevado.
- **Detecção:** KPI `dashboards_disponibilidade` (0.4.1 Seção 11) — alerta se < 95% das consultas < 2s.
- **Impacto:** degradação de experiência; sem impacto em integridade.
- **Severidade:** M.
- **Tratamento:** otimização (índices, materialized view) — task 1.4 (observabilidade) e 6.3 (qualidade).

**PF-FP-32 — RLS leak: dados de outro tenant vazam**
- **Causa:** bug em policy de RLS ou consulta bypass (ex.: função `SECURITY DEFINER` sem `SET LOCAL row_security`).
- **Detecção:** RBAC + KPI de auditoria cruzada (FS-12); testes de contrato (task 6.3.3).
- **Impacto:** violação de I-01 — dado de tenant B visível a tenant A; incidente de segurança.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo (RLS obrigatório em toda tabela de negócio); compensação manual por `admin_plataforma` (rotação de acesso, auditoria do vazamento); meta-auditoria.
PARTE4
echo "Parte 4 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 4 escrita
432 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mcat >> /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE5'

---

## 5. Detalhamento — Pontos de falha dos fluxos secundários

### 5.1 FS-01 — Gestão de usuários e papéis

**PF-FS-01 — Cota de usuários excedida**
- **Causa:** `admin_tenant` cria/convita usuário além do limite do plano (R02, I-02).
- **Detecção:** aplicação consulta contagem antes de INSERT.
- **Impacto:** usuário não criado/convitado.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo + NS-1 sugerindo upgrade (FS-09).

**PF-FS-02 — E-mail duplicado no tenant**
- **Causa:** convite para e-mail já vinculado a Usuário ativo no mesmo tenant.
- **Detecção:** trigger `BEFORE INSERT`/constraint UNIQUE `(tenant_id, email) WHERE status = 'ativo'`.
- **Impacto:** convite rejeitado.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; mensagem sugere reativar o usuário existente.

**PF-FS-03 — Atribuição de papel cross-tenant**
- **Causa:** tentativa de vincular Usuário (E-03) a Papel (E-04) de tenant distinto (regra transversal 5).
- **Detecção:** trigger `BEFORE INSERT` em `rel_usuario_papel` valida `tenant_id` iguais.
- **Impacto:** I-01/I-10 comprometidos se aceito; bloqueado.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo + meta-auditoria.

### 5.2 FS-03 — Gestão de contratos

**PF-FS-04 — Renovação com gap/sobreposição (I-03)**
- **Causa:** renovação com `data_inicio` anterior a `data_fim` do contrato vigente (sobreposição) ou posterior (gap) (R04/R05/R06, I-03).
- **Detecção:** trigger `BEFORE INSERT` valida janelas.
- **Impacto:** novo contrato rejeitado; I-03 preservado.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo.

**PF-FS-05 — Rescisão invalida escalações em edição ativa** [PENDÊNCIA 0.4.2]
- **Causa:** rescisão de contrato (E-07) de atleta escalado em partidas `agendada`/`em_andamento` de uma Edição ativa; PE de R09 encerra `rel_equipe_atleta`.
- **Detecção:** trigger `AFTER UPDATE` de Contrato para `rescindido` verifica partidas futuras com escalação do atleta.
- **Impacto:** escalações futuras tornam-se inválidas (PF-FP-22 passaria a bloquear); FP-08/F-09 afetados; risco de WO técnico (PF-FP-20).
- **Severidade:** A.
- **Tratamento:** rollback atômico do vínculo (encerra `dt_fim`); NS-3 ao `gestor_clube`; notifica `gestor_competicao` para reabrir escalação da partida afetada (FP-08). Decisão consolidada: **partidas já `concluidas` não são afetadas** (imutabilidade, T-8); apenas partidas `agendada` exigem reescalação.

**PF-FS-06 — Job de expiração automática não roda**
- **Causa:** job diário de expiração de contratos (`data_fim < hoje` → `expirado`) falha ou atrasa.
- **Detecção:** job de watchdog verifica último run; divergência entre `data_fim` e `status = 'ativo'`.
- **Impacto:** contratos expirados permanecem `ativo`; atletas podem ser escalados indevidamente (PF-FP-22 não detectaria).
- **Severidade:** A.
- **Tratamento:** retry do job; compensação manual (`admin_plataforma` ajusta estados); auditoria do gap.

### 5.3 FS-04 — Negociação e transferência de atletas

**PF-FS-07 — I-08 violado: 2ª proposta aceita**
- **Causa:** tentativa de mover segunda Proposta (E-17) para `aceita` na mesma Negociação (E-16) (I-08).
- **Detecção:** trigger `BEFORE UPDATE` valida constraint parcial `UNIQUE (negociacao_id) WHERE status = 'aceita'`.
- **Impacto:** I-08 preservado; segunda Proposta rejeitada.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo; NS-4 ao vendedor avisando que já há proposta aceita.

**PF-FS-08 — G-5 deferido mas I-03 falha no destino** [PENDÊNCIA 0.4.2]
- **Causa:** G-5 é deferido, mas a criação do novo Contrato de destino viola I-03 (Pessoa já tem contrato ativo no Clube destino — cenário de race ou dado inconsistente).
- **Detecção:** trigger `BEFORE INSERT` do novo Contrato valida I-03 dentro da mesma transação do deferimento de G-5.
- **Impacto:** se não tratado, dois contratos ativos para mesma Pessoa/Clube destino; violação de I-03.
- **Severidade:** C.
- **Tratamento:** rollback atômico — a transação do deferimento de G-5 reverte **todos** os efeitos colaterais (novo contrato, movimentação do contrato origem, encerramento de `rel_equipe_atleta`); Negociação volta para `aberta`; NS-5 a comprador e vendedor com motivo. Decisão consolidada: **a atomicidade da regra transversal 4 (approval mirror) é garantida por transação única**, sem efeito parcial.

**PF-FS-09 — Negociação cancelada após proposta aceita** [PENDÊNCIA 0.4.2]
- **Causa:** vendedor cancela a Negociação (E-16) após uma Proposta (E-17) estar `aceita` mas antes de G-5.
- **Detecção:** aplicação na transição `aberta → cancelada` com Proposta `aceita` existente.
- **Impacto:** Proposta `aceita` fica órfã; Anexos (E-18) associados precisam de tratamento.
- **Severidade:** M.
- **Tratamento:** rollback lógico — Proposta move para `recusada` (máquina da Proposta, Seção 4.2 de 0.4.2); Anexos (E-18) **preservados** para auditoria (não excluídos — I-09); NS-5 ao comprador informando cancelamento. Decisão consolidada: **Anexos nunca são excluídos fisicamente**; apenas desvinculados logicamente.

**PF-FS-10 — Contrato de origem inativo (R18)**
- **Causa:** tentativa de abrir Negociação com `contrato_origem_id` não `ativo` (R18).
- **Detecção:** aplicação valida antes de criar Negociação.
- **Impacto:** Negociação não criada.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo.

**PF-FS-11 — Clube comprador = vendedor (R07)**
- **Causa:** `clube_destino_id = clube_origem_id` (R07).
- **Detecção:** trigger `BEFORE INSERT` em Negociação (CHECK).
- **Impacto:** Negociação rejeitada; impede auto-transferência.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo.

**PF-FS-12 — Proposta aceita sem evidências (R20)**
- **Causa:** vendedor tenta aceitar Proposta sem ≥ 1 Anexo (E-18) (R20).
- **Detecção:** trigger `BEFORE UPDATE` em Proposta valida `EXISTS(anexo) WHERE proposta_id`.
- **Impacto:** Proposta permanece `enviada`; não avança para G-5.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; NS-4 ao comprador solicitando evidências.

### 5.4 FS-05 — Importação de dados em lote

**PF-FS-13 — Importação parcial: commit por batch vs rollback total** [PENDÊNCIA 0.4.2]
- **Causa:** lote com linhas válidas e inválidas misturadas; decisão de política de commit.
- **Detecção:** aplicação por batch (100 linhas/transação, Seção 3 de 0.4.2).
- **Impacto:** commit total rejeitaria linhas válidas por causa das inválidas; commit parcial deixa base parcialmente populada.
- **Severidade:** A.
- **Tratamento:** decisão consolidada — **commit por batch (100 linhas)**: cada batch é transacional; linhas inválidas do batch rejeitam só o batch, não o arquivo inteiro; relatório de falhas (task 2.4.4) lista linhas rejeitadas com campo/motivo; NS-6 ao usuário com `N_aceitas`/`N_rejeitadas`. Idempotência via `correlation_id` do lote (regra transversal 7) impede duplicação se o usuário reenvia o arquivo corrigido. Resolução da pendência 0.4.2/2.4.3.

**PF-FS-14 — Arquivo > 10MB ou > 5000 linhas**
- **Causa:** upload excede limites do MVP (0.4.2 FS-05).
- **Detecção:** aplicação valida tamanho/contagem antes de processar.
- **Impacto:** upload rejeitado; sem processamento.
- **Severidade:** M.
- **Tratamento:** bloqueio preventivo + NS-6 orientando fragmentar o arquivo.

**PF-FS-15 — Encoding inválido / cabeçalho incorreto**
- **Causa:** arquivo não UTF-8 ou cabeçalho divergente do template (task 2.4.2).
- **Detecção:** validação de formato antes de processar linhas.
- **Impacto:** lote inteiro rejeitado antes de qualquer INSERT.
- **Severidade:** M.
- **Tratamento:** bloqueio preventivo + relatório de falhas de arquivo (não de linha).

**PF-FS-16 — Conflito de dados (pular vs sobrescrever)**
- **Causa:** linha refere-se a entidade existente (match por CPF ou nome+data_nascimento) (task 2.4.3).
- **Detecção:** aplicação valida por linha.
- **Impacto:** sobrescrita poderia destruir histórico; pular deixa dado legado.
- **Severidade:** M.
- **Tratamento:** decisão consolidada — **política padrão `pular`** (não sobrescrever); `sobrescrever` exige confirmação explícita no upload e grava diff na auditoria (I-09) para cada campo mutado. Resolução da pendência 0.4.2/2.4.3.

### 5.5 FS-06 — Exportação de dados e relatórios

**PF-FS-17 — Exportação assíncrona timeout**
- **Causa:** exportação > 1000 linhas (assíncrona) excede tempo do job.
- **Detecção:** job monitora tempo de execução.
- **Impacto:** link não gerado; usuário aguarda.
- **Severidade:** M.
- **Tratamento:** retry com chunking; NS-6 ao concluir; se persistir, compensação manual.

**PF-FS-18 — Link de download expirado (< 24h)**
- **Causa:** usuário tenta baixar após validade do link temporário (24h).
- **Detecção:** aplicação valida `validade_ate`.
- **Impacto:** download indisponível; sem perda de dado.
- **Severidade:** B.
- **Tratamento:** reexecutar exportação via FS-06.
PARTE5
echo "Parte 5 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 5 escrita
572 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mcat >> /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE6'

### 5.6 FS-07 — Gestão de notificações

**PF-FS-19 — E-mail bounce**
- **Causa:** endereço de e-mail do Usuário inválido/caixa cheia; gateway de e-mail retorna bounce.
- **Detecção:** KPI de bounce por NS/N; webhook do provedor de e-mail.
- **Impacto:** notificação não entregue no canal e-mail; in-app permanece.
- **Severidade:** M.
- **Tratamento:** retry (3x); fallback garantido in-app (canal primário do MVP); NS-1 ao `admin_tenant` sugerindo atualizar e-mail.

**PF-FS-20 — Acúmulo de notificações não lidas**
- **Causa:** usuário não consome a central; KPI `notificacoes_nao_lidas` alto (0.4.2 Seção 11).
- **Detecção:** KPI por usuário.
- **Impacto:** risco de notificação alta (N-3/N-4/NS-7) ignorada; sem impacto em integridade.
- **Severidade:** B.
- **Tratamento:** job de resumo consolidado (diário/semanal conforme preferência) agrega não lidas em e-mail único.

### 5.7 FS-08 — Reabertura de partida via G-3

**PF-FS-21 — Reabertura < 24h com classificação já consolidada** [PENDÊNCIA 0.4.2]
- **Causa:** reabertura direta (sem G-3) dentro da janela de 24h, mas a classificação já foi consumida por dashboards/ranking público interno/relatórios exportados.
- **Detecção:** aplicação na reabertura marca `classificacao.stale = true` e dispara recálculo (PE de R11).
- **Impacto:** dashboards momentaneamente dessincronizados; exportações anteriores não são retroativas (já baixadas).
- **Severidade:** A.
- **Tratamento:** recálculo retroativo síncrono; NS-7 aos `gestor_clube` e `gestor_competicao` sinalizando que placar/classificação mudaram; dashboards recompostos. Decisão consolidada: **exportações já baixadas não são invalidadas** (não há como revogar arquivo externo); a auditoria (FS-12) registra a reabertura para rastreabilidade.

**PF-FS-22 — Recálculo de classificação inconsistente após reabertura**
- **Causa:** igual a PF-FP-30, mas disparado por reabertura.
- **Detecção:** job de reconciliação (PE de R11).
- **Impacto:** classificação dessincronizada do placar reaberto.
- **Severidade:** C.
- **Tratamento:** retry do job; compensação manual; KPI `reaberturas_24h`/`reaberturas_gate` (0.4.2 Seção 11).

### 5.8 FS-09 — Gestão de cotas e assinatura

**PF-FS-23 — Downgrade rejeitado (cotas excedentes)**
- **Causa:** `admin_tenant` tenta downgrade para plano com cotas menores que o uso atual (R02).
- **Detecção:** aplicação valida cotas em uso vs. limites do novo plano.
- **Impacto:** downgrade bloqueado; tenant mantém plano atual.
- **Severidade:** M.
- **Tratamento:** bloqueio preventivo + NS-1 listando entidades excedentes (ex.: "15 clubes; plano Basic permite 10"); orienta arquivamento (FS-10) antes.

**PF-FS-24 — Suspensão por inadimplência em produção**
- **Causa:** gateway de pagamento notifica inadimplência; job move `assinatura.status = 'suspensa'` e `organizacao.status = 'suspenso'` (PE de R01).
- **Detecção:** webhook do gateway + job de reconciliação (PF-X-08).
- **Impacto:** novas sessões bloqueadas; todo o fluxo principal paralisado; **dados preservados** para auditoria (não há exclusão).
- **Severidade:** A.
- **Tratamento:** período de carência (preliminar 90 dias, pendência 0.4.2/6.1.3) antes de `expirada`; NS-1 ao `admin_tenant`; após regularização, reativação automática.

### 5.9 FS-10 — Arquivamento e soft-delete

**PF-FS-25 — Arquivamento com inscrição ativa em edição**
- **Causa:** `admin_tenant`/`gestor_clube` tenta arquivar Clube com `rel_edicao_clube` ativa em Edição não `concluida` (pré-condição de FS-10).
- **Detecção:** aplicação valida antes do soft-delete.
- **Impacto:** violaria regra transversal 1; bloqueado.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; mensagem orienta desistência via FS-11 primeiro.

**PF-FS-26 — Arquivamento com vínculos em equipes de base** [PENDÊNCIA 0.4.2]
- **Causa:** Clube possui `rel_equipe_atleta` ativos em Equipes de base (Sub-20 etc.); dúvida sobre tratamento diferenciado.
- **Detecção:** trigger de soft-delete cascade (regra transversal 6).
- **Impacto:** se tratado diferentemente, base poderia continuar ativa enquanto profissional é arquivada — inconsistência.
- **Severidade:** M.
- **Tratamento:** decisão consolidada — **soft-delete cascade uniforme**: todas as Equipes (profissional e base) vão para `arquivada`, todos os `rel_equipe_atleta` encerrados, todos os Contratos para `suspenso_clube`. Não há tratamento diferenciado por categoria no MVP (a diferenciação seria futuro desejado, fora do escopo). Partidas históricas preservadas (T-6). Resolução da pendência 0.4.2.

### 5.10 FS-11 — Desistência/WO de clube em edição em andamento

**PF-FS-27 — WO retroativo: resultados já jogados** [PENDÊNCIA 0.4.1/0.4.2]
- **Causa:** Clube desiste da Edição após já ter disputado partidas `concluidas`; dúvida se resultados são mantidos ou anulados.
- **Detecção:** aplicação no processamento do WO (PE de R12).
- **Impacto:** anular partidas mudaria a classificação retroativamente e violaria a imutabilidade (T-8) dos fatos já consumados.
- **Severidade:** A.
- **Tratamento:** decisão consolidada — **resultados de partidas já `concluidas` são PRESERVADOS** (não anulados); apenas partidas futuras (`agendada`) vão para `wo` com placar 3-0 (configurável por Regra de Competição, pendência 2.2.4). Classificação recalculada mantém pontos das partidas jogadas e soma WO ao adversário das futuras. Resolução da pendência 0.4.1/0.4.2/2.2.4.

**PF-FS-28 — Desistência com partida `em_andamento`** [PENDÊNCIA 0.4.1/0.4.2]
- **Causa:** Clube comunica desistência enquanto uma de suas partidas está `em_andamento`.
- **Detecção:** aplicação ao processar desistência verifica partidas em curso do Clube.
- **Impacto:** interromper a partida em campo seria inviável operacionalmente; duvida sobre qual placar prevalece.
- **Severidade:** A.
- **Tratamento:** decisão consolidada — **a partida em curso NÃO é interrompida**; o placar de campo prevalece e a partida segue para `concluida` normalmente; a desistência só afeta partidas futuras (`agendada`). NS-7 a `gestor_competicao` e `delegado_partida`. Resolução da pendência 0.4.1/0.4.2.

**PF-FS-29 — WO 3-0 mas adversário já perdeu a partida**
- **Causa:** caso teórico em que o placar configurado de WO (3-0) favoreceria o adversário que, na realidade, já havia perdido a partida — mas partidas `concluidas` não viram WO (PF-FS-27), então o cenário só ocorre para partidas `agendada` ainda não disputadas.
- **Detecção:** aplicação: WO só se aplica a `partida.status = 'agendada'`.
- **Impacto:** nenhum — WO nunca sobrescreve partida jogada.
- **Severidade:** M.
- **Tratamento:** bloqueio preventivo da sobreposição; NS-7 com o placar atribuído.

### 5.11 FS-12 — Consulta de auditoria e trilha de logs

**PF-FS-30 — Tentativa de mutação na auditoria**
- **Causa:** qualquer tentativa de `UPDATE`/`DELETE` na tabela de Auditoria (E-23) (I-09 append-only).
- **Detecção:** trigger `BEFORE UPDATE/DELETE` sempre rejeita + RBAC nega escrita ao `auditor_somente_leitura`.
- **Impacto:** I-09 preservado; tentativa registrada como meta-auditoria.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo + meta-auditoria (evento de segurança).

**PF-FS-31 — Auditoria cresce sem retenção definida**
- **Causa:** tabela de Auditoria cresce indefinidamente; sem política de retenção no MVP.
- **Detecção:** KPI de volume; alerta de storage.
- **Impacto:** degradação de consulta (PF-FS-31 relaciona-se a PF-FP-31); sem perda de integridade.
- **Severidade:** M.
- **Tratamento:** política de retenção e particionamento — task 6.2.3 (Retenção de histórico, Sprint 6); no MVP, aceita-se crescimento monitorado.
PARTE6
echo "Parte 6 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 6 escrita
675 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mcat >> /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE7'

---

## 6. Detalhamento — Pontos de falha em gates de aprovação

Os gates G-1 a G-5 compartilham o mecanismo genérico E-19/E-20/E-21 ("aprovações como dados"). As falhas comuns a todos os gates são PF-G-01 a PF-G-04 e PF-G-07/PF-G-08; PF-G-05 é específica de G-3 e PF-G-06 de G-5.

**PF-G-01 — Aprovador inexistente ou inativo**
- **Causa:** Fluxo de aprovação (E-19) referencia Usuário/Papel inexistente ou suspenso; solicitação fica sem decisor.
- **Detecção:** job varre Solicitações (E-20) `status = 'pendente'` com `etapa` atual sem aprovador elegível.
- **Impacto:** gate para; etapas downstream do FP/FS bloqueadas.
- **Severidade:** A.
- **Tratamento:** NS-1 ao `admin_tenant` para reatribuir via FS-01; se recorrente, KPI `tempo_aprovacao` alerta.

**PF-G-02 — Timeout de aprovação (solicitação expira)**
- **Causa:** Solicitação permanece `pendente` além do SLA configurado por `tipo_ref`.
- **Detecção:** job de timeout por `criada_em + SLA`.
- **Impacto:** contrato/inscrição/transferência não concretizados.
- **Severidade:** M.
- **Tratamento:** arquivar Solicitação + NS ao proponente (NS-2/NS-5 conforme o gate); proponente pode reabrir.

**PF-G-03 — Ordem de etapa violada (R21/R22)**
- **Causa:** tentativa de deferir etapa N antes da etapa N-1 ser deferida (R21/R22).
- **Detecção:** trigger `BEFORE INSERT` em Aprovação (E-21) valida `etapa = min(etapa_pendente)`.
- **Impacto:** Aprovação rejeitada; ordem preservada.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo.

**PF-G-04 — Aprovador tenta deferir fora de sua etapa**
- **Causa:** aprovador da etapa 2 tenta decidir etapa 1 (ou vice-versa).
- **Detecção:** trigger valida `aprovador.papel IN papéis_da_etapa`.
- **Impacto:** Aprovação rejeitada.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; auditoria registra tentativa.

**PF-G-05 — G-3 deferido mas partida já arquivada (WO)**
- **Causa:** reabertura solicitada para partida que, entretanto, foi a WO (via FS-11) — estado terminal.
- **Detecção:** aplicação no deferimento de G-3 valida `partida.status = 'concluida'` (não `wo`).
- **Impacto:** reabertura não faz sentido para WO (sem eventos a corrigir).
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; Solicitação arquivada; NS-7 ao solicitante explicando que partida em WO é terminal.

**PF-G-06 — Rollback parcial em G-5**
- **Causa:** o efeito colateral do deferimento de G-5 (criar contrato destino, mover origem, encerrar vínculos) executa parcialmente por falha transiente.
- **Detecção:** transação DB única (regra transversal 4); se qualquer statement falha, toda a transação reverte.
- **Impacto:** sem rollback, teria contrato destino ativo sem origem rescindida (inconsistência).
- **Severidade:** C.
- **Tratamento:** rollback atômico garantido pela transação; Negociação permanece `em_aprovacao` ou volta a `aberta` conforme ponto de falha; NS-5 a comprador e vendedor.

**PF-G-07 — Duplo deferimento concorrente (race na última etapa)**
- **Causa:** dois aprovadores decidem a última etapa simultaneamente; ambos tentam aplicar o efeito colateral.
- **Detecção:** trigger com `SELECT FOR UPDATE` na Solicitação; semáforo de "efeito já aplicado".
- **Impacto:** sem proteção, efeito colateral duplicado (ex.: dois contratos ativos).
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo (lock de linha); apenas o primeiro deferimento aplica o efeito; o segundo é rejeitado como "já deferido".

**PF-G-08 — Reabertura de Solicitação arquivada**
- **Causa:** tentativa de reabrir Solicitação em `arquivada` (estado terminal da máquina de Solicitação).
- **Detecção:** trigger `BEFORE UPDATE` valida transição permitida.
- **Impacto:** impede reuso de instância decidida; força nova Solicitação.
- **Severidade:** A.
- **Tratamento:** bloqueio preventivo; usuário deve criar nova Solicitação se quiser reconsiderar.

---

## 7. Detalhamento — Pontos de falha transversais de plataforma

Falhas que não pertencem a um único fluxo, mas afetam a integridade global da plataforma.

**PF-X-01 — Race condition em escalação**
- **Causa:** dois `gestor_clube` (ou `gestor_clube` + `delegado_partida`) editam a mesma Escalação simultaneamente.
- **Detecção:** trigger com `SELECT FOR UPDATE` na Escalação (E-15) durante a mutação; validação de versão (`lock_version`).
- **Impacto:** sem proteção, numeração duplicada ou > 11 titulares; I-06 comprometido.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo (row lock + otimistic concurrency); o segundo a salvar recebe erro e deve refrescar.

**PF-X-02 — Queda de DB durante transação atômica de G-5**
- **Causa:** falha de infraestrutura no meio da transação do deferimento de G-5.
- **Detecção:** DB reverte a transação automaticamente.
- **Impacto:** sem efeito colateral persistido; Negociação permanece em estado pré-deferimento.
- **Severidade:** C.
- **Tratamento:** rollback atômico garantido pelo DB; retry do deferimento quando o DB volta; idempotência via `correlation_id` da Aprovação (regra transversal 7).

**PF-X-03 — RLS bypass / acesso cross-tenant**
- **Causa:** função `SECURITY DEFINER` sem `SET LOCAL row_security = on`, ou query direta bypassando policies.
- **Detecção:** RBAC + revisão de código (task 6.3) + testes de contrato cross-tenant (task 6.3.3).
- **Impacto:** I-01 violado — dado de outro tenant visível.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo (RLS obrigatório); compensação manual por `admin_plataforma` (auditoria do vazamento, rotação de acesso); meta-auditoria.

**PF-X-04 — `tenant_id` NULL em mutação**
- **Causa:** INSERT/UPDATE sem `tenant_id` (bug de aplicação ou trigger de cascade ausente).
- **Detecção:** trigger `BEFORE INSERT` preenche `tenant_id` da sessão; constraint `NOT NULL` em toda tabela de negócio (I-10).
- **Impacto:** I-10 comprometido; dado órfão.
- **Severidade:** C.
- **Tratamento:** bloqueio preventivo (NOT NULL + trigger); mutação rejeitada se `tenant_id` não resolvível.

**PF-X-05 — Trigger de auditoria falha**
- **Causa:** trigger `AFTER INSERT/UPDATE/DELETE` que grava em E-23 falha (ex.: campo JSONB inválido, overflow).
- **Detecção:** a auditoria é obrigatória — se o trigger falha, a transação pai reverte (trigger AFTER dentro da mesma transação).
- **Impacto:** I-09 comprometido se a mutação persistisse sem auditoria.
- **Severidade:** C.
- **Tratamento:** rollback atômico (auditoria é parte da transação); a mutação não persiste sem auditoria; alerta de observabilidade imediato; compensação manual se o dado era essencial (reaplicar após corrigir o trigger).

**PF-X-06 — Relógio desincronizado (janela 24h)**
- **Causa:** servidor de aplicação com relógio dessincronizado calcula `now() - concluida_em` errado, permitindo reabertura fora da janela ou negando reabertura legítima.
- **Detecção:** sincronização NTP obrigatória; KPI monitora drift; validação server-side usa `clock_timestamp()` do DB (fonte única de verdade).
- **Impacto:** T-8 calculada incorretamente; risco de mutação indevida ou bloqueio indevido.
- **Severidade:** C.
- **Tratamento:** NTP obrigatório; uso de `clock_timestamp()` do DB como referência canônica (nunca relógio do app); compensação manual se drift causou decisão errada.

**PF-X-07 — Job de recálculo de classificação falha**
- **Causa:** job que recalcula classificação (PE de R11) falha por deadlock, timeout ou dado inconsistente.
- **Detecção:** job de watchdog; KPI `dashboards_disponibilidade`.
- **Impacto:** classificação dessincronizada (relaciona-se a PF-FP-30/PF-FS-22).
- **Severidade:** A.
- **Tratamento:** retry com backoff; se persistir, compensação manual por `admin_plataforma` com auditoria.

**PF-X-08 — Gateway de pagamento divergente do estado interno**
- **Causa:** webhook do gateway perdido ou processado fora de ordem; `assinatura.status` diverge da realidade do gateway.
- **Detecção:** job de reconciliação periódica consulta o gateway e compara com E-02.
- **Impacto:** tenant suspenso indevidamente ou ativo indevidamente; I-02 comprometido na margem.
- **Severidade:** A.
- **Tratamento:** retry do webhook (idempotente, regra transversal 7); reconciliação corrige estado; NS-1 ao `admin_tenant` se houve mudança.
PARTE7
echo "Parte 7 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 7 escrita
799 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mcat >> /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md << 'PARTE8'

---

## 8. Estratégias de detecção, recuperação e mitigação

### 8.1 Matriz de detecção por mecanismo

| Mecanismo | Pontos de falha cobertos | Papel no MVP |
|-----------|--------------------------|--------------|
| **Trigger DB (BEFORE)** | PF-FP-04/07/09/12/17/21/22/23/25/26/28; PF-FS-02/03/04/07/11/12; PF-G-03/04/07/08; PF-X-01/04 | Primeira linha de defesa — rejeita mutação inválida antes de persistir |
| **Trigger DB (AFTER)** | PF-FP-10/30; PF-FS-05; PF-FS-22; PF-X-05 | Recalculo/cascade/auditoria na mesma transação |
| **Validação de aplicação** | PF-FP-01/03/08/14/15/16/18/19/24; PF-FS-01/09/10/13/14/15/16/23/25/27/28/29; PF-G-01/02/05 | Pré-condições antes de mutar; UX de erro |
| **Job agendado** | PF-FP-02/20; PF-FS-06/17/21; PF-X-07/08; PF-G-01/02 | Varredura periódica de expirações, órfãos, timeouts, reconciliação |
| **RBAC + RLS** | PF-FP-32; PF-FS-03/30; PF-X-03 | Negação de acesso por papel/tenant |
| **Observabilidade/KPI** | PF-FP-05/27/31; PF-FS-18/19/20/31; PF-X-06 | Alerta sobre métrica (task 1.4) |

### 8.2 Matriz de tratamento por estratégia

| Estratégia | Pontos de falha | Quando aplica |
|------------|-----------------|---------------|
| **Bloqueio preventivo** | 38 de 79 | Toda falha que violaria invariante — nunca deve ocorrer (maioria C/A) |
| **Rollback atômico** | PF-FP-10/30; PF-FS-05/08/09; PF-G-06; PF-X-02/05 | Efeitos colaterais múltiplos em gates/cascades |
| **Retry** | PF-FP-05/27; PF-FS-06/17/19; PF-X-07/08 | Falhas transientes de infra/conexão |
| **Gate de exceção** | PF-FP-20; PF-FS-21/27/28 | Quebra controlada de regra (imutabilidade, WO) |
| **Compensação manual** | PF-FP-02/30; PF-FS-06; PF-FP-32; PF-X-03/06/07 | Incidentes que exigem `admin_plataforma` |
| **Notificação + ação humana** | PF-FP-01/16/19; PF-FS-01/23/24; PF-G-01/02 | Pendências operacionais sem inconsistência |

### 8.3 Princípios de mitigação (contratos para a task 0.5)

Os princípios abaixo formalizam o tratamento de erros e devem ser elevados a **invariantes de fronteira** na subtask 0.5.1 (Invariantes de negócio) e 0.5.2 (Fronteiras técnicas):

1. **Auditoria é obrigatória e atômica:** nenhuma mutação de negócio persiste sem registro em E-23 na mesma transação (PF-X-05). I-09 é guardado por trigger, não por aplicação.
2. **`tenant_id` nunca é NULL:** toda tabela de negócio tem `tenant_id NOT NULL` preenchido por trigger a partir da sessão (PF-X-04). I-10 é guardado por constraint.
3. **RLS em toda tabela de negócio:** não existe tabela de negócio sem policy de RLS por `tenant_id` (PF-FP-32, PF-X-03). I-01 é guardado por policy.
4. **Imutabilidade por trigger, não por aplicação:** a janela de 24h (T-8) é validada server-side com `clock_timestamp()` do DB (PF-FP-28, PF-X-06).
5. **Aprovações são atômicas:** o efeito colateral do deferimento de um gate executa na mesma transação da Aprovação (PF-G-06, PF-X-02, PF-FS-08). T-4 é guardado por transação.
6. **Lock pessimista em recursos compartilhados:** Escalação e última etapa de gate usam `SELECT FOR UPDATE` (PF-X-01, PF-G-07).
7. **Idempotência por `correlation_id`:** jobs de integração/importação/exportação e webhooks do gateway usam `correlation_id` único (PF-FS-13/16, PF-X-08). T-7 é guardado por chave de idempotência.
8. **Soft-delete preserva histórico:** arquivamento nunca exclui Partidas/Eventos/Auditoria (PF-FS-26/27, T-6).

---

## 9. Matriz de severidade × probabilidade

Avaliação qualitativa para priorização de testes (task 6.3) e alertas de observabilidade (task 1.4). **Probabilidade:** A (alta), M (média), B (baixa).

| Sev \ Prob | A (alta) | M (média) | B (baixa) |
|-------------|----------|-----------|-----------|
| **C (Crítica)** | PF-FP-07/17/21/22/25/26/28; PF-FS-07/11; PF-X-01/04/05 | PF-FP-09; PF-FS-03/08; PF-G-06/07; PF-X-02/03/06 | PF-FP-02; PF-FP-32 |
| **A (Alta)** | PF-FP-03/06/20; PF-FS-01/05/13/25; PF-G-01; PF-X-07 | PF-FP-04/10/11/12/13/14/18/24/29; PF-FS-02/04/10/12/21/22/24/26/27/28; PF-G-03/04/05/08; PF-X-08 | PF-FP-08/15; PF-FS-06 |
| **M (Média)** | PF-FP-27; PF-FS-16/19 | PF-FP-01/16/19/31; PF-FS-09/14/15/17/20/23/29/31; PF-G-02 | PF-FS-18 |
| **B (Baixa)** | — | PF-FP-05; PF-FS-20 | PF-FS-18 |

**Prioridade de testes (task 6.3):** o quadrante Crítica×Alta deve ter **testes de contrato e regressão obrigatórios** na Sprint 6; o quadrante Crítica×Média deve ter testes de integração; o restante entra em cobertura padrão.

---

## 10. Resolução das pendências sinalizadas em 0.4.1/0.4.2

As 8 pendências explicitamente sinalizadas nos handoffs das subtasks anteriores são resolvidas nesta seção e referenciadas nos pontos de falha correspondentes.

| # | Pendência (origem) | Resolução (ponto de falha) | Decisão consolidada |
|---|--------------------|----------------------------|---------------------|
| 1 | Contrato rejeitado em G-1 — impacto em FP-04/FP-08 (0.4.1/0.4.2) | PF-FP-06 | `contrato.status = 'rejeitado'` (terminal); FP-04 bloqueada para o atleta; FP-08 sem o atleta; NS-2 ao proponente; atleta elegível para nova proposta. |
| 2 | Escalação incompleta no prazo (0.4.1) | PF-FP-20 | Não há WO automático; `gestor_competicao` decide entre prorrogar janela, WO técnico (FS-11) ou reagendar; NS-7. |
| 3 | Evento de gol com atleta não escalado (0.4.1) | PF-FP-25 | Trigger `BEFORE INSERT` rejeita; T-3 guardado server-side; delegado corrige em tempo real. |
| 4 | Reabertura após imutabilidade (0.4.1) | PF-FP-28/29 | Mutação direta > 24h bloqueada por trigger + meta-auditoria; única via é FS-08 via G-3. |
| 5 | Negociação cancelada após proposta aceita — rollback de E-18 (0.4.2) | PF-FS-09 | Proposta → `recusada`; Anexos **preservados** para auditoria (não excluídos); NS-5 ao comprador. |
| 6 | G-5 deferido mas I-03 falha no destino — rollback (0.4.2) | PF-FS-08 | Rollback atômico na mesma transação; Negociação volta a `aberta`; NS-5; nenhum efeito parcial. |
| 7 | Importação parcial — commit parcial vs rollback (0.4.2) | PF-FS-13 | Commit por batch (100 linhas/transação); relatório de falhas por linha; idempotência por `correlation_id`. |
| 8 | Arquivamento com vínculos em equipes de base (0.4.2) | PF-FS-26 | Soft-delete cascade uniforme (base e profissional); sem diferenciação no MVP. |
| 9 | WO retroativo — resultados mantidos ou anulados (0.4.1/0.4.2) | PF-FS-27 | Resultados de partidas `concluidas` **preservados**; WO só para `agendada`; T-8 respeitada. |
| 10 | Desistência com partida `em_andamento` (0.4.1/0.4.2) | PF-FS-28 | Partida em curso **não é interrompida**; placar de campo prevalece; desistência só afeta futuras. |

> Pendências remanescentes (parâmetros por Regra de Competição: antecedência de janela, placar de WO configurável, janela de transferência, número de etapas de G-5, retenção de auditoria) são encaminhadas para a task 2.2.4 (Transições de estado) e Sprint 6 conforme indicado em 0.4.2 Seção 12.2.

---

## 11. Handoff para as próximas tasks

Este documento fecha a task 0.4 (Mapear fluxos) e estabelece o contrato de tratamento de erros para o restante da Sprint 0 e para as Sprints 1 e 6.

- **0.5.1 — Escrever invariantes de negócio:** os 8 princípios de mitigação (Seção 8.3) devem ser formalizados como invariantes de fronteira, somando-se aos 10 invariantes (I-01 a I-10) e 8 regras transversais de 0.3.3.
- **0.5.2 — Definir fronteiras técnicas:** a separação entre validação por trigger DB (server-side, não-bypassável) e validação de aplicação (UX) deve ser formalizada — toda proteção de invariante é server-side.
- **0.5.3 — Mapear integrações externas:** as falhas PF-FP-01, PF-FS-19, PF-X-08 dependem de integrações (gateway de pagamento, provedor de e-mail) cujo contrato de SLA/webhook/retry deve ser detalhado.
- **1.4 — Observabilidade mínima:** os KPIs desta subtask (matriz de detecção, Seção 8.1) e das Seções 11 de 0.4.1/0.4.2 alimentam os alertas de logging/erros/auditoria da Sprint 1.
- **6.2 — Auditoria:** PF-FS-30/31 e PF-X-05 definem os contratos de imutabilidade e retenção da auditoria.
- **6.3 — Qualidade e testes:** a matriz severidade × probabilidade (Seção 9) define a priorização dos testes de contrato/regressão.

### 11.1 Decisões consolidadas

1. **79 pontos de falha** catalogados em 4 namespaces (PF-FP, PF-FS, PF-G, PF-X).
2. **Bloqueio preventivo server-side** é a estratégia dominante (38/79) — toda proteção de invariante vive em trigger/constraint, nunca apenas em aplicação.
3. **Atomicidade de gates** (T-4) garantida por transação única; sem efeito parcial (PF-G-06, PF-FS-08).
4. **Imutabilidade (T-8)** guardada por trigger com `clock_timestamp()` do DB; única quebra legítima é FS-08 via G-3.
5. **Soft-delete preserva histórico** (T-6) — Partidas/Eventos/Auditoria nunca excluídos por arquivamento ou WO.
6. **Idempotência (T-7)** por `correlation_id` em toda integração/job/webhook.
7. **10 pendências resolvidas** (Seção 10); pendências paramétricas remanescentes encaminhadas a 2.2.4/Sprint 6.

### 11.2 Pendências abertas remanescentes (encaminhadas)

- Antecedência mínima da janela de escalação → 2.2.4 (Regras de Competição).
- Placar de WO configurável (padrão 3-0) → 2.2.4.
- Janela de transferência para G-5 → 2.2.1 + 5.2.
- Número de etapas de G-5 por tenant → 6.1.2.
- Política de retenção de auditoria → 6.2.3.
- Período de carência para `expirada` (Assinatura) → 6.1.3.
- Canal do setor jurídico (NS-3) → 3.4.2.

---

## 12. Resumo para o orquestrador

- **Subtask:** 0.4.3 — Marcar pontos de falha (`needs_review: true`)
- **Resultado:** **79 pontos de falha** catalogados e detalhados, cobrindo o fluxo principal (32), os 12 fluxos secundários (31), os 5 gates de aprovação (8) e as falhas transversais de plataforma (8).
- **Taxonomia:** 4 níveis de severidade (C/A/M/B), 6 estratégias de tratamento, 6 mecanismos de detecção.
- **Cobertura de guardas:** todos os 10 invariantes (I-01 a I-10) e todas as 8 regras transversais (T-1 a T-8) têm ao menos um ponto de falha que os protege (bloqueio preventivo) ou os exercita no sentido de exceção (gate de exceção/compensação).
- **Resolução:** 10 das pendências sinalizadas em 0.4.1/0.4.2 resolvidas com decisão consolidada (Seção 10); pendências paramétricas encaminhadas a 2.2.4 e Sprint 6.
- **Conformidade:** respeita os 26 não-objetivos (N-01 a N-26) — nenhum ponto de falha introduz funcionalidade fora do escopo; e as 7 implicações de desenho do MVP.
- **Princípios de mitigação:** 8 princípios (Seção 8.3) a serem formalizados como invariantes de fronteira em 0.5.1/0.5.2.
- **Ponto de parada:** `needs_review: true` exige revisão humana antes de encerrar a task 0.4 e avançar para 0.5 (Contratos e invariantes).
PARTE8
echo "Parte 8 escrita"
wc -l /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
Parte 8 escrita
920 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
echo "=== SEÇÕES ===" && grep -n "^## " "$F"
echo "" && echo "=== CONTAGEM PF POR NAMESPACE ==="
echo -n "PF-FP: " && grep -c "^### .*PF-FP-[0-9]" "$F"
echo -n "PF-FP (catalogo+detalhe): " && grep -oE "PF-FP-[0-9]{2}" "$F" | sort -u | wc -l
echo -n "PF-FS: " && grep -oE "PF-FS-[0-9]{2}" "$F" | sort -u | wc -l
echo -n "PF-G: " && grep -oE "PF-G-[0-9]{2}" "$F" | sort -u | wc -l
echo -n "PF-X: " && grep -oE "PF-X-[0-9]{2}" "$F" | sort -u | wc -l
echo "" && echo "=== TOTAL ÚNICO ===" && grep -oE "PF-(FP|FS|G|X)-[0-9]{2}" "$F" | sort -u | wc -l
echo "" && echo "=== INVARIANTES REFERENCIADOS ===" && grep -oE "I-[01][0-9]" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== REGRAS TRANSVERSAIS ===" && grep -oE "T-[0-9]" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== ENTIDADES ===" && grep -oE "E-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== GATES ===" && grep -oE "G-[1-5]" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== FLUXOS FS ===" && grep -oE "FS-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== NÃO-OBJETIVOS ===" && grep -oE "N-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
=== SEÇÕES ===
12:## Output do OpenCode (GLM 5.2)
22:## 1. Sumário executivo
47:## 2. Taxonomia de falhas
79:## 3. Catálogo mestre de pontos de falha
184:## 4. Detalhamento — Pontos de falha do fluxo principal
436:## 5. Detalhamento — Pontos de falha dos fluxos secundários
679:## 6. Detalhamento — Pontos de falha em gates de aprovação
741:## 7. Detalhamento — Pontos de falha transversais de plataforma
803:## 8. Estratégias de detecção, recuperação e mitigação
842:## 9. Matriz de severidade × probabilidade
857:## 10. Resolução das pendências sinalizadas em 0.4.1/0.4.2
878:## 11. Handoff para as próximas tasks
911:## 12. Resumo para o orquestrador

=== CONTAGEM PF POR NAMESPACE ===
PF-FP: 1
PF-FP (catalogo+detalhe): 32
PF-FS: 31
PF-G: 8
PF-X: 8

=== TOTAL ÚNICO ===
79

=== INVARIANTES REFERENCIADOS ===
I-01 I-02 I-03 I-04 I-05 I-06 I-07 I-08 I-09 I-10 
=== REGRAS TRANSVERSAIS ===
T-1 T-2 T-3 T-4 T-5 T-6 T-7 T-8 
=== ENTIDADES ===
E-01 E-02 E-03 E-04 E-05 E-06 E-07 E-09 E-11 E-12 E-14 E-15 E-16 E-17 E-18 E-19 E-20 E-21 E-22 E-23 E-25 
=== GATES ===
G-1 G-2 G-3 G-5 
=== FLUXOS FS ===
FS-01 FS-02 FS-03 FS-04 FS-05 FS-06 FS-07 FS-08 FS-09 FS-10 FS-11 FS-12 FS-13 FS-14 FS-15 FS-16 FS-17 FS-18 FS-19 FS-20 FS-21 FS-22 FS-23 FS-24 FS-25 FS-26 FS-27 FS-28 FS-29 FS-30 FS-31 
=== NÃO-OBJETIVOS ===
N-01 N-24 N-26
[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
echo "=== G-4 menções ===" && grep -n "G-4" "$F" | head -20
echo "" && echo "=== E-13 / Partida ===" && grep -cE "E-13" "$F" && grep -c "Partida" "$F"
echo "=== E-08 / E-10 / E-24 ===" && grep -cE "E-08" "$F" && grep -cE "E-10" "$F" && grep -cE "E-24" "$F"
echo "=== Competição/Equipe/Log de integração por nome ===" && grep -c "Competição" "$F" && grep -c "Equipe" "$F" && grep -c "Log de integração" "$F"
echo "" && echo "=== FP-XX steps presentes ===" && grep -oE "FP-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
=== G-4 menções ===

=== E-13 / Partida ===
0
=== E-08 / E-10 / E-24 ===
0
=== Competição/Equipe/Log de integração por nome ===
7
11
0

=== FP-XX steps presentes ===
FP-01 FP-02 FP-03 FP-04 FP-05 FP-06 FP-07 FP-08 FP-09 FP-10 FP-11 FP-12 FP-13 FP-14 FP-15 FP-16 FP-17 FP-18 FP-19 FP-20 FP-21 FP-22 FP-23 FP-24 FP-25 FP-26 FP-27 FP-28 FP-29 FP-30 FP-31 FP-32
[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -152,9 +152,9 @@
 | PF-FS-29 | FS-11 | WO 3-0 mas adversário já perdeu a partida | M | Aplicação | Preservar placar real se `concluida`; WO só para futuras | — |
 | PF-FS-30 | FS-12 | Tentativa de mutação na auditoria | C | Trigger BEFORE | Bloqueio preventivo + meta-auditoria | I-09 |
 | PF-FS-31 | FS-12 | Auditoria cresce sem retenção definida | M | KPI | Política de retenção (task 6.2.3) | I-09 |
 
-### 3.3 Gates de aprovação (PF-G-01 a PF-G-08)
+### 3.3 Gates de aprovação (PF-G-01 a PF-G-09)
 
 | ID | Gate | Modo de falha | Sev. | Detecção | Tratamento | Guarda |
 |----|------|---------------|------|----------|------------|--------|
 | PF-G-01 | G-1 a G-5 | Aprovador inexistente ou inativo | A | Job | Notificação + reatribuição (FS-01) | R21/R22 |

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -164,8 +164,9 @@
 | PF-G-05 | G-3 | G-3 deferido mas partida já arquivada (WO) | A | Aplicação | Bloqueio preventivo — partida em WO é terminal | T-8 |
 | PF-G-06 | G-5 | Rollback parcial — efeito colateral executa pela metade | C | Trigger DB | Rollback atômico (transação única) + NS-5 | T-4 |
 | PF-G-07 | G-1 a G-5 | Duplo deferimento concorrente (race na última etapa) | C | Trigger DB (lock) | Bloqueio preventivo (SELECT FOR UPDATE) | T-4 |
 | PF-G-08 | G-1 a G-5 | Reabertura de Solicitação arquivada | A | Trigger DB | Bloqueio preventivo | — |
+| PF-G-09 | G-4 | Encerramento de Edição com pendências (partidas não concluídas) | A | Aplicação | Bloqueio preventivo + NS-7 com lista de pendências | PE R11 |
 
 ### 3.4 Transversais de plataforma (PF-X-01 a PF-X-08)
 
 | ID | Escopo | Modo de falha | Sev. | Detecção | Tratamento | Guarda |

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -678,9 +678,9 @@
 ---
 
 ## 6. Detalhamento — Pontos de falha em gates de aprovação
 
-Os gates G-1 a G-5 compartilham o mecanismo genérico E-19/E-20/E-21 ("aprovações como dados"). As falhas comuns a todos os gates são PF-G-01 a PF-G-04 e PF-G-07/PF-G-08; PF-G-05 é específica de G-3 e PF-G-06 de G-5.
+Os gates G-1 a G-5 compartilham o mecanismo genérico E-19/E-20/E-21 ("aprovações como dados"). As falhas comuns a todos os gates são PF-G-01 a PF-G-04 e PF-G-07/PF-G-08; PF-G-05 é específica de G-3, PF-G-06 de G-5 e PF-G-09 de G-4.
 
 **PF-G-01 — Aprovador inexistente ou inativo**
 - **Causa:** Fluxo de aprovação (E-19) referencia Usuário/Papel inexistente ou suspenso; solicitação fica sem decisor.
 - **Detecção:** job varre Solicitações (E-20) `status = 'pendente'` com `etapa` atual sem aprovador elegível.

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -736,8 +736,15 @@
 - **Impacto:** impede reuso de instância decidida; força nova Solicitação.
 - **Severidade:** A.
 - **Tratamento:** bloqueio preventivo; usuário deve criar nova Solicitação se quiser reconsiderar.
 
+**PF-G-09 — Encerramento de Edição com pendências (G-4)**
+- **Causa:** `gestor_competicao` solicita G-4 (`tipo_ref = 'edicao_encerramento'`) enquanto existem Partidas (E-13) da Edição (E-11) ainda não `concluidas` (em `agendada`/`em_andamento`/`wo` pendente) ou Fases (E-12) não concluídas.
+- **Detecção:** aplicação no deferimento de G-4 valida `NOT EXISTS(partida WHERE edicao_id = X AND status <> 'concluida' AND status <> 'wo')`.
+- **Impacto:** encerrar com pendências consolidaria classificação incompleta e bloquearia mutações posteriores sobre partidas ainda em curso (conflito com T-8 e com FP-10).
+- **Severidade:** A.
+- **Tratamento:** bloqueio preventivo — G-4 é rejeitado e retorna a lista de pendências (Partidas/Fases em aberto); NS-7 ao `gestor_competicao`; a Edição permanece `em_andamento` até que todas as Partidas estejam `concluidas` ou `wo`. Alinhado à nota de 0.4.1 (Seção 5): G-4 é obrigatório quando há apuração manual de título/rebaixamento.
+
 ---
 
 ## 7. Detalhamento — Pontos de falha transversais de plataforma
 

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -24,12 +24,12 @@
 Mapear pontos de falha é o fechamento da task 0.4 (Mapear fluxos). O fluxo principal (0.4.1) e os 12 fluxos secundários (0.4.2) descrevem o caminho feliz e os gates de aprovação; resta catalogar **onde, por que e como** cada fluxo pode falhar, qual a severidade, como o sistema detecta, qual o impacto sobre invariantes e entidades, e qual a estratégia de recuperação.
 
 **Conteúdo produzido:**
 
-- **79 pontos de falha** catalogados, em 4 namespaces distintos:
+- **80 pontos de falha** catalogados, em 4 namespaces distintos:
   - **PF-FP-01 a PF-FP-32** — fluxo principal (32 pontos)
   - **PF-FS-01 a PF-FS-31** — fluxos secundários (31 pontos)
-  - **PF-G-01 a PF-G-08** — gates de aprovação (8 pontos)
+  - **PF-G-01 a PF-G-09** — gates de aprovação (9 pontos)
   - **PF-X-01 a PF-X-08** — transversais de plataforma (8 pontos)
 - **Taxonomia de severidade** em 4 níveis (Crítica, Alta, Média, Baixa) alinhada aos invariantes I-01 a I-10
 - **6 estratégias de tratamento** padronizadas (bloqueio preventivo, rollback atômico, retry, gate de exceção, compensação manual, notificação + ação humana)
 - **Matriz de detecção** por mecanismo (trigger DB, validação de aplicação, job, RBAC, observabilidade/KPI)

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -815,9 +815,9 @@
 | Mecanismo | Pontos de falha cobertos | Papel no MVP |
 |-----------|--------------------------|--------------|
 | **Trigger DB (BEFORE)** | PF-FP-04/07/09/12/17/21/22/23/25/26/28; PF-FS-02/03/04/07/11/12; PF-G-03/04/07/08; PF-X-01/04 | Primeira linha de defesa — rejeita mutação inválida antes de persistir |
 | **Trigger DB (AFTER)** | PF-FP-10/30; PF-FS-05; PF-FS-22; PF-X-05 | Recalculo/cascade/auditoria na mesma transação |
-| **Validação de aplicação** | PF-FP-01/03/08/14/15/16/18/19/24; PF-FS-01/09/10/13/14/15/16/23/25/27/28/29; PF-G-01/02/05 | Pré-condições antes de mutar; UX de erro |
+| **Validação de aplicação** | PF-FP-01/03/08/14/15/16/18/19/24; PF-FS-01/09/10/13/14/15/16/23/25/27/28/29; PF-G-01/02/05/09 | Pré-condições antes de mutar; UX de erro |
 | **Job agendado** | PF-FP-02/20; PF-FS-06/17/21; PF-X-07/08; PF-G-01/02 | Varredura periódica de expirações, órfãos, timeouts, reconciliação |
 | **RBAC + RLS** | PF-FP-32; PF-FS-03/30; PF-X-03 | Negação de acesso por papel/tenant |
 | **Observabilidade/KPI** | PF-FP-05/27/31; PF-FS-18/19/20/31; PF-X-06 | Alerta sobre métrica (task 1.4) |
 

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -824,9 +824,9 @@
 ### 8.2 Matriz de tratamento por estratégia
 
 | Estratégia | Pontos de falha | Quando aplica |
 |------------|-----------------|---------------|
-| **Bloqueio preventivo** | 38 de 79 | Toda falha que violaria invariante — nunca deve ocorrer (maioria C/A) |
+| **Bloqueio preventivo** | 39 de 80 | Toda falha que violaria invariante — nunca deve ocorrer (maioria C/A) |
 | **Rollback atômico** | PF-FP-10/30; PF-FS-05/08/09; PF-G-06; PF-X-02/05 | Efeitos colaterais múltiplos em gates/cascades |
 | **Retry** | PF-FP-05/27; PF-FS-06/17/19; PF-X-07/08 | Falhas transientes de infra/conexão |
 | **Gate de exceção** | PF-FP-20; PF-FS-21/27/28 | Quebra controlada de regra (imutabilidade, WO) |
 | **Compensação manual** | PF-FP-02/30; PF-FS-06; PF-FP-32; PF-X-03/06/07 | Incidentes que exigem `admin_plataforma` |

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -853,9 +853,9 @@
 
 | Sev \ Prob | A (alta) | M (média) | B (baixa) |
 |-------------|----------|-----------|-----------|
 | **C (Crítica)** | PF-FP-07/17/21/22/25/26/28; PF-FS-07/11; PF-X-01/04/05 | PF-FP-09; PF-FS-03/08; PF-G-06/07; PF-X-02/03/06 | PF-FP-02; PF-FP-32 |
-| **A (Alta)** | PF-FP-03/06/20; PF-FS-01/05/13/25; PF-G-01; PF-X-07 | PF-FP-04/10/11/12/13/14/18/24/29; PF-FS-02/04/10/12/21/22/24/26/27/28; PF-G-03/04/05/08; PF-X-08 | PF-FP-08/15; PF-FS-06 |
+| **A (Alta)** | PF-FP-03/06/20; PF-FS-01/05/13/25; PF-G-01; PF-X-07 | PF-FP-04/10/11/12/13/14/18/24/29; PF-FS-02/04/10/12/21/22/24/26/27/28; PF-G-03/04/05/08/09; PF-X-08 | PF-FP-08/15; PF-FS-06 |
 | **M (Média)** | PF-FP-27; PF-FS-16/19 | PF-FP-01/16/19/31; PF-FS-09/14/15/17/20/23/29/31; PF-G-02 | PF-FS-18 |
 | **B (Baixa)** | — | PF-FP-05; PF-FS-20 | PF-FS-18 |
 
 **Prioridade de testes (task 6.3):** o quadrante Crítica×Alta deve ter **testes de contrato e regressão obrigatórios** na Sprint 6; o quadrante Crítica×Média deve ter testes de integração; o restante entra em cobertura padrão.

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -918,9 +918,9 @@
 
 ## 12. Resumo para o orquestrador
 
 - **Subtask:** 0.4.3 — Marcar pontos de falha (`needs_review: true`)
-- **Resultado:** **79 pontos de falha** catalogados e detalhados, cobrindo o fluxo principal (32), os 12 fluxos secundários (31), os 5 gates de aprovação (8) e as falhas transversais de plataforma (8).
+- **Resultado:** **80 pontos de falha** catalogados e detalhados, cobrindo o fluxo principal (32), os 12 fluxos secundários (31), os 5 gates de aprovação (9) e as falhas transversais de plataforma (8).
 - **Taxonomia:** 4 níveis de severidade (C/A/M/B), 6 estratégias de tratamento, 6 mecanismos de detecção.
 - **Cobertura de guardas:** todos os 10 invariantes (I-01 a I-10) e todas as 8 regras transversais (T-1 a T-8) têm ao menos um ponto de falha que os protege (bloqueio preventivo) ou os exercita no sentido de exceção (gate de exceção/compensação).
 - **Resolução:** 10 das pendências sinalizadas em 0.4.1/0.4.2 resolvidas com decisão consolidada (Seção 10); pendências paramétricas encaminhadas a 2.2.4 e Sprint 6.
 - **Conformidade:** respeita os 26 não-objetivos (N-01 a N-26) — nenhum ponto de falha introduz funcionalidade fora do escopo; e as 7 implicações de desenho do MVP.

[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
echo "=== G-4 ===" && grep -c "G-4" "$F"
echo "=== GATES únicos ===" && grep -oE "G-[1-5]" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== TOTAL PF ÚNICO ===" && grep -oE "PF-(FP|FS|G|X)-[0-9]{2}" "$F" | sort -u | wc -l
echo "=== PF-G únicos ===" && grep -oE "PF-G-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== ENTIDADES E-XX ===" && grep -oE "E-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== Conta 80/79 ===" && grep -c "80 pontos" "$F" && grep -c "79 pontos" "$F"
echo "=== Linhas ===" && wc -l "$F"
=== G-4 ===
6
=== GATES únicos ===
G-1 G-2 G-3 G-4 G-5 
=== TOTAL PF ÚNICO ===
80
=== PF-G únicos ===
PF-G-01 PF-G-02 PF-G-03 PF-G-04 PF-G-05 PF-G-06 PF-G-07 PF-G-08 PF-G-09 
=== ENTIDADES E-XX ===
E-01 E-02 E-03 E-04 E-05 E-06 E-07 E-09 E-11 E-12 E-13 E-14 E-15 E-16 E-17 E-18 E-19 E-20 E-21 E-22 E-23 E-25 
=== Conta 80/79 ===
2
2
=== Linhas ===
928 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
grep -n "79" "$F"
81:Tabela única com os 79 pontos de falha. As colunas **Sev.** (severidade), **Detecção** e **Tratamento** usam os códigos das Seções 2.1–2.3. A coluna **Guarda** indica qual invariante (I-XX) ou regra transversal (T-1 a T-8) o ponto de falha protege ou exercita no sentido de exceção.
899:1. **79 pontos de falha** catalogados em 4 namespaces (PF-FP, PF-FS, PF-G, PF-X).
900:2. **Bloqueio preventivo server-side** é a estratégia dominante (38/79) — toda proteção de invariante vive em trigger/constraint, nunca apenas em aplicação.
[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -77,9 +77,9 @@
 ---
 
 ## 3. Catálogo mestre de pontos de falha
 
-Tabela única com os 79 pontos de falha. As colunas **Sev.** (severidade), **Detecção** e **Tratamento** usam os códigos das Seções 2.1–2.3. A coluna **Guarda** indica qual invariante (I-XX) ou regra transversal (T-1 a T-8) o ponto de falha protege ou exercita no sentido de exceção.
+Tabela única com os 80 pontos de falha. As colunas **Sev.** (severidade), **Detecção** e **Tratamento** usam os códigos das Seções 2.1–2.3. A coluna **Guarda** indica qual invariante (I-XX) ou regra transversal (T-1 a T-8) o ponto de falha protege ou exercita no sentido de exceção.
 
 ### 3.1 Fluxo principal (PF-FP-01 a PF-FP-32)
 
 | ID | Etapa | Modo de falha | Sev. | Detecção | Tratamento | Guarda |

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -895,10 +895,10 @@
 - **6.3 — Qualidade e testes:** a matriz severidade × probabilidade (Seção 9) define a priorização dos testes de contrato/regressão.
 
 ### 11.1 Decisões consolidadas
 
-1. **79 pontos de falha** catalogados em 4 namespaces (PF-FP, PF-FS, PF-G, PF-X).
-2. **Bloqueio preventivo server-side** é a estratégia dominante (38/79) — toda proteção de invariante vive em trigger/constraint, nunca apenas em aplicação.
+1. **80 pontos de falha** catalogados em 4 namespaces (PF-FP, PF-FS, PF-G, PF-X).
+2. **Bloqueio preventivo server-side** é a estratégia dominante (39/80) — toda proteção de invariante vive em trigger/constraint, nunca apenas em aplicação.
 3. **Atomicidade de gates** (T-4) garantida por transação única; sem efeito parcial (PF-G-06, PF-FS-08).
 4. **Imutabilidade (T-8)** guardada por trigger com `clock_timestamp()` do DB; única quebra legítima é FS-08 via G-3.
 5. **Soft-delete preserva histórico** (T-6) — Partidas/Eventos/Auditoria nunca excluídos por arquivamento ou WO.
 6. **Idempotência (T-7)** por `correlation_id` em toda integração/job/webhook.

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -211,9 +211,9 @@
 - **Severidade:** A — bloqueia cadastro fundacional.
 - **Tratamento:** bloqueio preventivo + NS-1 sugerindo upgrade (FS-09) ou arquivamento (FS-10).
 
 **PF-FP-04 — Violação UNIQUE (categoria, genero) da Equipe**
-- **Causa:** `gestor_clube` cria Equipe (E-09) com par já existente no Clube (R08).
+- **Causa:** `gestor_clube` cria Equipe (E-08/E-09) com par já existente no Clube (R08).
 - **Detecção:** trigger `BEFORE INSERT`/constraint UNIQUE composta.
 - **Impacto:** E-09 rejeitado; I-07 análogo preservado.
 - **Severidade:** A.
 - **Tratamento:** bloqueio preventivo; mensagem orienta a editar a Equipe existente.

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -266,9 +266,9 @@
 
 ### 4.5 FP-05 — Configuração da competição e edição
 
 **PF-FP-11 — `ano_temporada` duplicado para mesma Competição**
-- **Causa:** `gestor_competicao` cria Edição (E-11) com `(competicao_id, ano_temporada)` já existente (R10/R11).
+- **Causa:** `gestor_competicao` cria Edição (E-11) com `(competicao_id, ano_temporada)` já existente para a mesma Competição (E-10) (R10/R11).
 - **Detecção:** trigger `BEFORE INSERT`/constraint UNIQUE composta.
 - **Impacto:** Edição rejeitada.
 - **Severidade:** A.
 - **Tratamento:** bloqueio preventivo.

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.4.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
@@ -532,9 +532,9 @@
 - **Causa:** lote com linhas válidas e inválidas misturadas; decisão de política de commit.
 - **Detecção:** aplicação por batch (100 linhas/transação, Seção 3 de 0.4.2).
 - **Impacto:** commit total rejeitaria linhas válidas por causa das inválidas; commit parcial deixa base parcialmente populada.
 - **Severidade:** A.
-- **Tratamento:** decisão consolidada — **commit por batch (100 linhas)**: cada batch é transacional; linhas inválidas do batch rejeitam só o batch, não o arquivo inteiro; relatório de falhas (task 2.4.4) lista linhas rejeitadas com campo/motivo; NS-6 ao usuário com `N_aceitas`/`N_rejeitadas`. Idempotência via `correlation_id` do lote (regra transversal 7) impede duplicação se o usuário reenvia o arquivo corrigido. Resolução da pendência 0.4.2/2.4.3.
+- **Tratamento:** decisão consolidada — **commit por batch (100 linhas)**: cada batch é transacional; linhas inválidas do batch rejeitam só o batch, não o arquivo inteiro; relatório de falhas (task 2.4.4) lista linhas rejeitadas com campo/motivo; Log de integração (E-24) grava o resultado do lote; NS-6 ao usuário com `N_aceitas`/`N_rejeitadas`. Idempotência via `correlation_id` do lote (regra transversal 7) impede duplicação se o usuário reenvia o arquivo corrigido. Resolução da pendência 0.4.2/2.4.3.
 
 **PF-FS-14 — Arquivo > 10MB ou > 5000 linhas**
 - **Causa:** upload excede limites do MVP (0.4.2 FS-05).
 - **Detecção:** aplicação valida tamanho/contagem antes de processar.

[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
echo "=== Linhas ===" && wc -l "$F"
echo "=== 79 residual ===" && grep -c "79" "$F"
echo "=== 80 pontos ===" && grep -c "80 pontos\|80 pontos de falha\|de 80\|39/80" "$F"
echo "=== PF únicos ===" && grep -oE "PF-(FP|FS|G|X)-[0-9]{2}" "$F" | sort -u | wc -l
echo "=== Gates G-1..G-5 ===" && grep -oE "G-[1-5]" "$F" | sort -u | tr '\n' ' '
echo "=== Invariantes I-01..I-10 ===" && grep -oE "I-[01][0-9]" "$F" | sort -u | tr '\n' ' '
echo "=== Transversais T-1..T-8 ===" && grep -oE "T-[1-8]" "$F" | sort -u | tr '\n' ' '
echo "=== Entidades E-XX ===" && grep -oE "E-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "=== PENDÊNCIA marcadas ===" && grep -c "\[PENDÊNCIA" "$F"
echo "=== Seções ===" && grep -c "^## " "$F"
=== Linhas ===
928 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.4.3.md
=== 79 residual ===
0
=== 80 pontos ===
6
=== PF únicos ===
80
=== Gates G-1..G-5 ===
G-1 G-2 G-3 G-4 G-5 === Invariantes I-01..I-10 ===
I-01 I-02 I-03 I-04 I-05 I-06 I-07 I-08 I-09 I-10 === Transversais T-1..T-8 ===
T-1 T-2 T-3 T-4 T-5 T-6 T-7 T-8 === Entidades E-XX ===
E-01 E-02 E-03 E-04 E-05 E-06 E-07 E-08 E-09 E-10 E-11 E-12 E-13 E-14 E-15 E-16 E-17 E-18 E-19 E-20 E-21 E-22 E-23 E-24 E-25 === PENDÊNCIA marcadas ===
14
=== Seções ===
13
[0m

```