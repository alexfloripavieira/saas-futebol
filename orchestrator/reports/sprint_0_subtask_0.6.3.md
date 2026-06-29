# Subtask 0.6.3 — Preparar handoff para Sprint 1 (Sprint 0)

**Sprint:** Fundação, escopo e contratos
**Task:** Consolidar Sprint 0
**Status:** completed
**Época:** 2026-06-29
**Modelo:** opencode-go/glm-5.2
**needs_review:** true

---

# Handoff final — Sprint 0 → Sprint 1

Documento de transição da **Sprint 0 (Fundação, escopo e contratos)** para a **Sprint 1 (Fundação da plataforma)**. Consolida as premissas implementadas, as regras imutáveis que não podem ser violadas, os arquivos de referência e o próximo passo. Fontes primárias: relatórios 0.6.1 (resumo executivo) e 0.6.2 (pendências abertas), complementados por 0.5.1 (invariantes), 0.5.2 (fronteiras técnicas) e 0.5.3 (integrações externas).

> Esta subtask mantém `needs_review: true` — exige validação humana antes do avanço definitivo para a Sprint 1 (regra 2 do `system_orchestrator.txt`).

---

## 1. Premissas implementadas (decisões consolidadas na Sprint 0)

A Sprint 0 produziu apenas **especificação e contratos** — nenhum código foi gerado em `src/` (vazio) nem documentação em `docs/` (vazio). Toda a riqueza técnica está em `orchestrator/reports/`. As premissas abaixo são **decisões tomadas e registradas** que a Sprint 1 deve assumir como dadas.

### 1.1 Visão do produto (0.1.x)

- **Produto:** SaaS **B2B de gestão de operações esportivas** voltado a **clubes profissionais e federações regionais** no Brasil (MVP). Não é voltado ao torcedor.
- **Problema central:** operação esportiva (cadastro, contratos, competições, partidas) é feita em planilhas e sistemas fragmentados.
- **Proposta de valor:** **fonte única de verdade** para o ciclo competição → partida → consolidação, com auditoria e aprovações embutidas.
- **7 papéis** definidos: `admin_tenant`, `gestor_clube`, `gestor_competicao`, `aprovador`, `delegado_partida`, `auditor_somente_leitura` e `admin_plataforma` (sistema).

### 1.2 Escopo — 26 não-objetivos (0.2.x)

- **14 não-objetivos permanentes** (N-05 a N-14, N-18 a N-20, N-22 a N-23, N-26 conforme 0.2.2/0.2.3): folha, contabilidade, ERP, bilheteria, app de torcida, ingressos, e-commerce, streaming, CRM, redes sociais, on-premise, etc.
- **12 não-objetivos reclassificados para futuro desejado** (F-01 a F-25, em 3 horizontes pós-MVP): análise tática, scouting, biometria, estrutura física, compliance CBF/FIFA automatizado, BI self-service, API pública, entre outros.
- **7 implicações anti-regresso arquiteturais** definidas em 0.2.3: `tenant_id`+RLS, API separada da UI, notificações abstraídas, aprovações como dados, auditoria com diff, IA assistiva, esquema normalizado.

### 1.3 Núcleo de dados — 25 entidades em 7 grupos (0.3.x)

- **A — Organização/acesso:** E-01 Organização (tenant), E-02 Assinatura, E-03 Usuário, E-04 Papel.
- **B — Pessoas:** E-05 Clube, E-06 Pessoa, E-07 Contrato, E-08 (atributos mínimos), E-09 Equipe/Categoria.
- **D — Competições/partidas:** E-10 Competição, E-11 Edição, E-12 Fase/Rodada, E-13 Partida, E-14 Evento, E-15 Escalação.
- **E — Mercado/vínculos:** E-16 Negociação, E-17 Proposta, E-18 Anexo/Evidência.
- **F — Fluxos operacionais:** E-19 Fluxo de aprovação, E-20 Solicitação, E-21 Aprovação, E-22 Notificação.
- **G — Governança/observabilidade:** E-23 Auditoria/Log, E-24 Log de integração, E-25 Sistema externo.
- **27 relacionamentos** (R01–R27) com cardinalidades 1:1, 1:N e N:N (tabelas de junção) + 2 polimórficas; **8 regras transversais** cruzam tabelas.

### 1.4 Fluxos (0.4.x)

- **Fluxo principal** — 11 etapas (FP-01 a FP-11): onboarding → cadastros → contratos → equipes → competição/edição → inscrição → tabela de partidas → convocação/escalação → condução da partida → encerramento/consolidação → auditoria/dashboards. Mobiliza 22 das 25 entidades.
- **5 gates de aprovação** (G-1 a G-5) modelados **como dados** via E-19/E-20/E-21: G-1 contrato, G-2 inscrição, G-3 reabertura de partida, G-4 encerramento de edição, G-5 transferência.
- **12 fluxos secundários** (FS-01 a FS-12): usuários/papéis, contratos, negociação/transferência, importação em lote, exportação, notificações, reabertura, cotas/assinatura, arquivamento, WO/desistência, auditoria.
- **3 máquinas de estados** encadeadas (Edição, Fase, Partida) + máquina do Contrato.

### 1.5 Pontos de falha — 80 modos (0.4.3)

| Namespace | Intervalo | Quantidade | Escopo |
|-----------|-----------|-----------|--------|
| PF-FP | 01 a 32 | 32 | Fluxo principal |
| PF-FS | 01 a 31 | 31 | Fluxos secundários |
| PF-G | 01 a 09 | 9 | Gates G-1 a G-5 |
| PF-X | 01 a 08 | 8 | Transversais de plataforma |

**Taxonomia de severidade:** C (Crítica), A (Alta), M (Média), B (Baixa). **6 estratégias de tratamento:** bloqueio preventivo, rollback atômico, retry, gate de exceção, compensação manual, notificação + ação humana. Cobertura total: 25/25 entidades, 10/10 invariantes, 8/8 regras transversais, 5/5 gates.

### 1.6 Integrações externas — 5 contratos (0.5.3)

| ID | Integração | Criticidade | Necessária já na Sprint 1? |
|----|------------|------------|---------------------------|
| INT-01 | Gateway de pagamento (Stripe/MP) | Crítica | **Sim** — onboarding/assinatura (FP-01/FP-02, I-02) |
| INT-02 | E-mail transacional (Postmark/SES) | Alta | **Sim** — canal externo de notificação (E-22, FS-07) |
| INT-03 | Object storage S3-compatible | Alta | Não — Sprint 2 (anexos) e Sprint 4 (uploads) |
| INT-04 | Importação de arquivos (CSV/XLSX) | Média | Não — Sprint 2 (task 2.4) |
| INT-05 | Exportação de arquivos (CSV/XLSX/PDF) | Média | Não — Sprint 2 (task 2.4) |

Todas: idempotentes por `correlation_id` + `sistema_externo_id` UNIQUE (T-7, IF-07); logadas em E-24 com payload redigido (R27); retry 3x backoff exponencial + circuit breaker + fila de exceções; webhooks validam HMAC antes de qualquer mutação.

### 1.7 Stack decidida

- **Banco:** PostgreSQL com `tenant_id` + **Row-Level Security** em toda tabela de negócio (multi-tenant).
- **Modelo de execução:** orquestrador Python (`orchestrator/runner.py`) delegando ao OpenCode CLI (GLM 5.2).
- **Notificações:** Evolution API (WhatsApp) no nível do orquestrador; in-app primário + e-mail (INT-02) secundário no nível do produto.

---

## 2. Regras imutáveis (não podem ser violadas pela Sprint 1)

Estas regras são **contratos de arquitetura** firmados na Sprint 0. Qualquer implementação da Sprint 1 que as contrarie constitui regresso arquitetural e deve ser rejeitada em revisão.

### 2.1 Os 26 invariantes (0.5.1)

Toda proteção de invariante é **server-side** (trigger/constraint/RLS/transação) — nunca apenas na camada de aplicação ou UI.

**Estruturais (I-01 a I-10) — guardados em DB:**
- **I-01** Pertencimento único ao tenant (todo `usuario` pertence a exatamente um `organizacao`).
- **I-02** Assinatura única e ativa por tenant.
- **I-03** Unicidade do contrato ativo (Pessoa, Clube) — no máximo um `contrato` ativo por par.
- **I-04** Unicidade do vínculo atleta-equipe por período.
- **I-05** Mandante ≠ Visitante.
- **I-06** 11 titulares por Escalação.
- **I-07** Sequencialidade e unicidade da ordem de Fases.
- **I-08** Unicidade da proposta aceita por negociação.
- **I-09** Auditoria append-only (apenas `INSERT`; `UPDATE`/`DELETE` rejeitados a todo papel).
- **I-10** Propagação não-nula de `tenant_id`.

**Domínio (T-1 a T-8) — DB + aplicação:**
- **T-1** Inscrição ativa exige Clube ativo.
- **T-2** Escalação exige vínculo vigente.
- **T-3** Evento de atleta exige atleta em campo.
- **T-4** Approval mirror (atomicidade do gate).
- **T-5** Coincidência de tenant em FKs de negócio.
- **T-6** Soft-delete preserva histórico.
- **T-7** Idempotência de integrações (`correlation_id` + `sistema_externo_id` UNIQUE).
- **T-8** Imutabilidade pós-fato (janela de 24h — valor provisório, parametrizável por tenant).

**Fronteira de plataforma (IF-01 a IF-08) — plataforma server-side:**
- **IF-01** Auditoria obrigatória e atômica.
- **IF-02** `tenant_id` nunca NULL.
- **IF-03** RLS em toda tabela de negócio.
- **IF-04** Imutabilidade calculada server-side (24h parametrizável).
- **IF-05** Aprovações atômicas (transação única).
- **IF-06** Lock pessimista em recursos compartilhados.
- **IF-07** Idempotência por `correlation_id`.
- **IF-08** Soft-delete preserva histórico permanente.

### 2.2 Fronteiras técnicas (0.5.2)

1. **Estado de verdade é interno** — webhooks são **eventos**, nunca gravação direta; um job idempotente aplica a transação (PF-X-08).
2. **Aplicação não bypassa invariantes** — nenhuma rota de negócio pode ignorar trigger/constraint/RLS.
3. **Multi-tenant via `tenant_id` + RLS** — uma Assinatura ativa por tenant (I-02); nenhuma consulta recebe dados de outro tenant.
4. **Aprovações como dados** (E-19/E-20/E-21) — não há lógica de workflow hardcoded; gates são configuráveis por tenant.
5. **Auditoria append-only** (E-23) com diff JSONB; `UPDATE`/`DELETE` proibidos a todo papel (I-09).
6. **Imutabilidade pós-fato** (T-8, IF-04): partida concluída há > 24h só muta via G-3.
7. **Notificações abstraídas** (E-22): in-app primário, e-mail (INT-02) secundário.
8. **Idempotência** (T-7, IF-07) por `correlation_id` em toda integração.
9. **Segredos nunca em banco nem em log** — redação de payload em E-24 (IF-08); credenciais em cofre, referenciadas por ID em E-25.
10. **Tenant boundary em objeto:** INT-03 prefixa keys com `tenant_id/`; import/export filtram por RLS.

### 2.3 Regras do orquestrador (`system_orchestrator.txt`)

Aplicáveis ao fluxo de execução da Sprint 1:

- NUNCA executar uma subtask sem verificar se a anterior foi concluída.
- Subtasks `needs_review: true` exigem parada imediata e interação do usuário.
- Só avançar para a próxima sprint após consolidar a atual (não pular a consolidação final).
- Estado em `orchestrator/state/execution_state.json` sempre atualizado.
- Se uma subtask falhar 3 vezes, parar e pedir intervenção.
- Output de cada subtask salvo em `orchestrator/reports/`.

---

## 3. Arquivos importantes

### 3.1 Orquestrador e estado

| Arquivo | Função |
|---------|--------|
| `orchestrator/sprints.json` | Definição canônica de sprints/tasks/subtasks e flags `needs_review`. Sprint 1 começa na linha 162. |
| `orchestrator/state/execution_state.json` | Estado de execução (sprint/task/subtask atual, histórico, fila de revisão, falhas). |
| `orchestrator/runner.py` | Loop de execução via OpenCode CLI (`--loop`, `--status`, `--review`, `--approve <id>`, `--report`). |
| `orchestrator/prompts/system_orchestrator.txt` | Regras invioláveis e formato de prompt do orquestrador. |
| `orchestrator/whatsapp_notify.py` | Notificações WhatsApp (Evolution API). |
| `README.md` | Visão geral do projeto, estrutura e tech stack. |

### 3.2 Relatórios da Sprint 0 (fontes de conhecimento para a Sprint 1)

Os 15 relatórios em `orchestrator/reports/` são a **especificação viva** do produto. Ordenados por consumo recomendado na Sprint 1:

| Relatório | Conteúdo | Relevância para Sprint 1 |
|-----------|----------|--------------------------|
| `sprint_0_subtask_0.6.1.md` | **Resumo executivo** de todas as decisões (10 seções) | Leitura obrigatória — visão consolidada |
| `sprint_0_subtask_0.6.2.md` | **Pendências abertas** (9 técnicas + 3 governança) | Leitura obrigatória — pré-requisitos |
| `sprint_0_subtask_0.6.3.md` | **Este handoff** | Leitura obrigatória |
| `sprint_0_subtask_0.5.1.md` | 26 invariantes (I/T/IF) + matriz invariante × PF | Base para tasks 1.2 (autenticação) e 1.4 (auditoria) |
| `sprint_0_subtask_0.5.2.md` | Fronteiras técnicas | Base para tasks 1.1 (shell) e 1.2 (sessão) |
| `sprint_0_subtask_0.5.3.md` | 5 integrações externas + SLA/webhook/retry | Base para INT-01/INT-02 já na Sprint 1 |
| `sprint_0_subtask_0.1.3.md` | Público-alvo e 7 papéis | Base para task 1.2 (RBAC/sessão) |
| `sprint_0_subtask_0.3.1.md` | 25 entidades (E-01 a E-25) | Referência para task 1.1 (shell) |
| `sprint_0_subtask_0.3.3.md` | 27 relacionamentos + 8 regras transversais (`needs_review`) | Referência para schema DB (Sprint 2) |
| `sprint_0_subtask_0.4.1.md` | Fluxo principal (FP-01 a FP-11) | Contexto para navegação (task 1.1) |
| `sprint_0_subtask_0.4.2.md` | 12 fluxos secundários (FS-01 a FS-12) | Contexto para navegação (task 1.1) |
| `sprint_0_subtask_0.4.3.md` | 80 pontos de falha (`needs_review`) | Base para task 1.4 (observabilidade/erros) |
| `sprint_0_subtask_0.1.2.md` | Proposta de valor | Contexto de produto |
| `sprint_0_subtask_0.2.2.md` | 26 não-objetivos declarados | Fronteiras do MVP |
| `sprint_0_subtask_0.2.3.md` | Futuro desejado (F-01 a F-25) (`needs_review`) | Anti-regresso arquitetural |

### 3.3 Diretórios vazios (a serem povoados)

- `docs/prd/`, `docs/sprints/`, `docs/techspec/` — vazios; a Sprint 1 pode começar a povoa-los.
- `src/` — vazio; **nenhum código foi gerado** na Sprint 0 (esta foi uma sprint de especificação).

---

## 4. Próximo passo — Sprint 1: Fundação da plataforma

### 4.1 Objetivo da Sprint 1

Construir a fundação técnica da plataforma: shell da aplicação, autenticação/sessão, design system mínimo e observabilidade mínima. É a primeira sprint que **produz código**.

### 4.2 Tasks e subtasks (de `sprints.json`)

| Task | Nome | Subtasks | Observações |
|------|------|----------|-------------|
| 1.1 | Shell da aplicação | 1.1.1 Composição geral · 1.1.2 Áreas persistentes · 1.1.3 Slots dinâmicos (`needs_review`) | Definir layout multi-tenant com áreas persistentes (header/sidebar) e slots dinâmicos por papel. |
| 1.2 | Autenticação e sessão | 1.2.1 Login · 1.2.2 Logout · 1.2.3 Expiração de sessão (`needs_review`) | Implementar sobre os 7 papéis de 0.1.3; RBAC + RLS (I-01, IF-03); integra com INT-01 (assinatura ativa — I-02). |
| 1.3 | Design system mínimo | 1.3.1 Tokens visuais · 1.3.2 Componentes base · 1.3.3 Estados base | Paleta, tipografia, componentes base e estados (loading/empty/error/success) — base para a Sprint 4. |
| 1.4 | Observabilidade mínima | 1.4.1 Logging · 1.4.2 Erros · 1.4.3 Auditoria | Logging/erros/auditoria server-side; KPIs por integração (latência, bounce rate, webhook HMAC rejeitado, divergência DB↔gateway) vindos de 0.5.3 Seção 10; auditoria append-only (I-09, IF-01). |
| 1.5 | Consolidação da Sprint 1 | 1.5.1 Fechar lacunas · 1.5.2 Escrever handoff (`needs_review`) | Consolidação obrigatória antes da Sprint 2. |

### 4.3 Pré-requisitos práticos (pendências P-1.x de 0.6.2)

**Nenhuma pendência bloqueia formalmente o início da Sprint 1**, mas os itens abaixo são pré-requisitos práticos para tasks específicas:

| ID | Pendência | Bloqueia | Ação necessária |
|----|-----------|----------|-----------------|
| P-1.1 | Configurar **INT-01** (gateway de pagamento) em sandbox | Task 1.2 (autenticação/assinatura, FP-01/FP-02, I-02) | Provisionar conta sandbox (Stripe ou Mercado Pago); decisão formal fica em 5.1.1 |
| P-1.2 | Configurar **INT-02** (e-mail transacional) | Task 1.4 (observabilidade de notificações, FS-07) | Provisionar provedor; configurar SPF/DKIM/DMARC no domínio remetente |
| P-1.3 | Validar **público-alvo** (0.1.3, `needs_review`) | Task 1.3 (design system) | Confirmar segmentação e papéis antes do design system |
| P-1.4 | **Tokens visuais e componentes base** (1.3.x) | Própria task 1.3 | Definir paleta, tipografia, componentes e estados base |

### 4.4 Subtasks com `needs_review: true` herdados da Sprint 0

Estas 5 subtasks foram completadas mas mantêm flag de revisão pendente e devem ser validadas (ou explicitamente aceitas) antes ou durante a Sprint 1:

- **0.1.3** — Definir público-alvo (validar segmentação/papéis — impacta 1.2 e 1.3).
- **0.2.3** — Separar futuro desejado (12 não-objetivos reclassificados — anti-regresso arquitetural).
- **0.3.3** — Descrever relacionamentos R01–R27 + 8 regras transversais (revisar antes de gerar schema DB na Sprint 2).
- **0.4.3** — Marcar pontos de falha (80 PFs; 10 pendências resolvidas).
- **0.5.3** — Mapear integrações externas (INT-01 a INT-05; escolha de provedores pendente).

### 4.5 Mapeamento Sprint 0 → Sprint 1 (o que alimenta o quê)

| Decisão Sprint 0 | Alimenta task Sprint 1 |
|-------------------|------------------------|
| 7 papéis (0.1.3) | 1.2 (autenticação/RBAC) |
| Multi-tenant + RLS (0.5.1, 0.5.2) | 1.1 (shell), 1.2 (sessão), 1.4 (auditoria) |
| Auditoria append-only I-09/IF-01 (0.5.1) | 1.4.3 (auditoria) |
| Imutabilidade pós-fato T-8/IF-04 (0.5.1) | 1.4 (logging/erros) |
| INT-01/INT-02 necessárias (0.5.3) | 1.2 (assinatura), 1.4 (notificações) |
| Estados base loading/empty/error/success (0.4.3) | 1.3.3 (estados base), 1.4.2 (erros) |
| KPIs por integração (0.5.3 Seção 10) | 1.4 (observabilidade) |
| Pontos de falha PF-X-01 a 08 (0.4.3) | 1.4 (transversais de plataforma) |

### 4.6 Como iniciar a Sprint 1

1. **Aprovar este handoff** (subtask 0.6.3, `needs_review: true`):
   ```bash
   python3 orchestrator/runner.py --approve 0.6.3
   ```
2. Provisionar INT-01 e INT-02 em **sandbox** (pendências P-1.1, P-1.2).
3. Validar público-alvo (P-1.3) e os demais itens `needs_review` herdados.
4. Executar a Sprint 1 em loop:
   ```bash
   python3 orchestrator/runner.py --loop
   ```
   O orquestrador iniciará pela subtask **1.1.1 — Definir composição geral**.

---

## 5. Resumo executivo do handoff

- A **Sprint 0 entregou especificação e contratos**, não código: 25 entidades, 27 relacionamentos, 11+12 fluxos, 5 gates, 80 pontos de falha, 26 invariantes, 5 integrações e 26 não-objetivos — tudo documentado em 15 relatórios.
- A **Sprint 1 é a primeira sprint de código**: shell, autenticação, design system e observabilidade, sobre PostgreSQL multi-tenant com RLS.
- **Regras imutáveis** (26 invariantes + 10 fronteiras) são server-side e não podem ser bypassadas pela aplicação.
- **INT-01 e INT-02 em sandbox** são pré-requisitos práticos para tasks 1.2 e 1.4.
- **5 subtasks com `needs_review`** da Sprint 0 devem ser validadas; esta (0.6.3) é uma delas e **bloqueia o avanço até aprovação humana**.
- Próxima subtask após aprovação: **1.1.1 — Definir composição geral** (Sprint 1, Task 1.1 — Shell da aplicação).

---

**Fim do handoff da Sprint 0.** Aguardando revisão humana (`needs_review: true`). Para aprovar: `python3 orchestrator/runner.py --approve 0.6.3`.
