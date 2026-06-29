# Subtask 0.5.1 — Escrever invariantes de negócio

**Sprint:** Fundação, escopo e contratos
**Task:** Contratos e invariantes
**Status:** completed
**Timestamp:** 2026-06-28T23:26:22.403477

---

## Output do OpenCode (GLM 5.2)

Tenho contexto completo das subtasks anteriores: 25 entidades (E-01–E-25), 27 relacionamentos (R01–R27), 10 invariantes estruturais (I-01–I-10), 8 regras transversais (T-1–T-8), 80 pontos de falha (PF-FP/FS/G/X) e os 8 princípios de mitigação da Seção 8.3 de 0.4.3 (que o handoff explicitamente manda formalizar como invariantes de fronteira em 0.5.1). Vou escrever o relatório.
Agora valido a estrutura e integridade do relatório, como fizeram as subtasks anteriores.
Falso positivo — "todo" (português) casou com "TODO". Sem placeholders reais. Há uma pequena lacuna de rastreabilidade: E-10 (Competição) e E-18 (Anexo) aparecem por nome mas sem tag. Vou adicioná-las para consistência com 0.4.3.
Subtask **0.5.1 — Escrever invariantes de negócio** concluída e salva em `orchestrator/reports/sprint_0_subtask_0.5.1.md` (600 linhas).

**26 invariantes** formalizados em 3 tiers: **10 estruturais** (I-01 a I-10, de 0.3.3), **8 de domínio** (T-1 a T-8, de 0.3.3) e **8 de fronteira** (IF-01 a IF-08, elevados dos princípios de mitigação de 0.4.3 Seção 8.3 conforme handoff). Cada invariante traz enunciado formal, entidades/relacionamentos, mecanismo de guarda, camada de execução, severidade e recuperação. Inclui matriz invariante × ponto de falha (26/26 cobertos, 59 PFs referenciados), 7 máquinas de estados supervisionadas e matriz severidade × tier. Princípio fundamental: **toda proteção de invariante é server-side** (trigger/constraint/RLS/transação) — ponteiro para 0.5.2 (Fronteiras técnicas). `needs_review: false` mantido.


## Stderr

```
[0m
> build · glm-5.2
[0m
[0m✱ [0mGlob "orchestrator/reports/sprint_0_*.md"[90m 10 matches[0m
[0m
[0m$ [0mls -la /home/alex/saas-futebol/orchestrator/reports/ 2>/dev/null || echo "directory not found"
total 316
drwxrwxr-x 2 alex alex   4096 jun 28 23:07 .
drwxrwxr-x 6 alex alex   4096 jun 28 22:41 ..
-rw-rw-r-- 1 alex alex   1214 jun 28 21:42 sprint_0_subtask_0.1.2.md
-rw-rw-r-- 1 alex alex   2352 jun 28 21:51 sprint_0_subtask_0.1.3.md
-rw-rw-r-- 1 alex alex   6114 jun 28 22:04 sprint_0_subtask_0.2.2.md
-rw-rw-r-- 1 alex alex   6973 jun 28 22:09 sprint_0_subtask_0.2.3.md
-rw-rw-r-- 1 alex alex   5710 jun 28 22:20 sprint_0_subtask_0.3.1.md
-rw-rw-r-- 1 alex alex   4689 jun 28 22:23 sprint_0_subtask_0.3.2.md
-rw-rw-r-- 1 alex alex  19343 jun 28 22:41 sprint_0_subtask_0.3.3.md
-rw-rw-r-- 1 alex alex  75570 jun 28 22:49 sprint_0_subtask_0.4.1.md
-rw-rw-r-- 1 alex alex  68644 jun 28 23:03 sprint_0_subtask_0.4.2.md
-rw-rw-r-- 1 alex alex 102687 jun 28 23:14 sprint_0_subtask_0.4.3.md
[0m
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.3.3.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.4.3.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.4.3.md[90m [offset=711][0m
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.3.1.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.2.2.md
[0m
[0m← [0mWrite orchestrator/reports/sprint_0_subtask_0.5.1.md
Wrote file successfully.
[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
echo "=== Linhas ===" && wc -l "$F"
echo "" && echo "=== Seções ## ===" && grep -n "^## " "$F"
echo "" && echo "=== Subseções ### ===" && grep -n "^### " "$F"
echo "" && echo "=== Contagem invariantes por tier ==="
echo -n "I- (estruturais, únicos): " && grep -oE "\bI-[01][0-9]\b" "$F" | sort -u | wc -l
echo -n "T- (domínio, únicos): " && grep -oE "\bT-[1-8]\b" "$F" | sort -u | wc -l
echo -n "IF- (fronteira, únicos): " && grep -oE "\bIF-0[1-8]\b" "$F" | sort -u | wc -l
echo "" && echo "=== Listas por tier ==="
echo -n "I-: " && grep -oE "\bI-[01][0-9]\b" "$F" | sort -u | tr '\n' ' '
echo ""
echo -n "T-: " && grep -oE "\bT-[1-8]\b" "$F" | sort -u | tr '\n' ' '
echo ""
echo -n "IF-: " && grep -oE "\bIF-0[1-8]\b" "$F" | sort -u | tr '\n' ' '
echo ""
echo "" && echo "=== PFs referenciados ===" && grep -oE "PF-(FP|FS|G|X)-[0-9]{2}" "$F" | sort -u | wc -l
echo -n "PFs lista: " && grep -oE "PF-(FP|FS|G|X)-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo ""
echo "" && echo "=== Entidades E-XX ===" && grep -oE "E-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== Gates G-1..G-5 ===" && grep -oE "G-[1-5]\b" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== Não-objetivos N-XX ===" && grep -oE "N-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== Fluxos FS-XX referenciados ===" && grep -oE "FS-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== Placeholder check ===" && grep -ciE "placeholder|TODO|FIXME|xxx|lorem" "$F"
echo "=== JSON válido (sprints.json) ===" && python3 -c "import json; json.load(open('/home/alex/saas-futebol/orchestrator/sprints.json')); print('OK')"
=== Linhas ===
598 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md

=== Seções ## ===
12:## Output do OpenCode (GLM 5.2)
20:## 1. Sumário executivo
53:## 2. Definição operacional
66:## 3. Catálogo mestre de invariantes
113:## 4. Detalhamento — Invariantes estruturais (I-01 a I-10)
219:## 5. Detalhamento — Regras transversais de domínio (T-1 a T-8)
303:## 6. Detalhamento — Invariantes de fronteira de plataforma (IF-01 a IF-08)
389:## 7. Matriz invariante × ponto de falha
426:## 8. Máquinas de estados supervisionadas
517:## 9. Matriz severidade × tier
529:## 10. Conformidade com não-objetivos e implicações de desenho
553:## 11. Handoff para as próximas tasks
590:## 12. Resumo para o orquestrador

=== Subseções ### ===
70:### 3.1 Invariantes estruturais de dados (I-01 a I-10)
85:### 3.2 Regras transversais de domínio (T-1 a T-8)
98:### 3.3 Invariantes de fronteira de plataforma (IF-01 a IF-08)
117:### I-01 — Pertencimento único ao tenant
127:### I-02 — Assinatura única e ativa por tenant
137:### I-03 — Unicidade do contrato ativo (Pessoa, Clube)
147:### I-04 — Unicidade do vínculo atleta-equipe por período
157:### I-05 — Mandante ≠ Visitante
167:### I-06 — 11 titulares por Escalação
177:### I-07 — Sequencialidade e unicidade da ordem de Fases
187:### I-08 — Unicidade da proposta aceita por negociação
197:### I-09 — Auditoria append-only
207:### I-10 — Propagação não-nula de `tenant_id`
221:### T-1 — Inscrição ativa exige Clube ativo
231:### T-2 — Escalação exige vínculo vigente
241:### T-3 — Evento de atleta exige atleta em campo
251:### T-4 — Approval mirror (atomicidade do gate)
261:### T-5 — Coincidência de tenant em FKs de negócio
271:### T-6 — Soft-delete preserva histórico
281:### T-7 — Idempotência de integrações
291:### T-8 — Imutabilidade pós-fato (janela de 24h)
307:### IF-01 — Auditoria obrigatória e atômica
317:### IF-02 — `tenant_id` nunca NULL
327:### IF-03 — RLS em toda tabela de negócio
337:### IF-04 — Imutabilidade calculada server-side
347:### IF-05 — Aprovações atômicas (transação única)
357:### IF-06 — Lock pessimista em recursos compartilhados
367:### IF-07 — Idempotência por `correlation_id`
377:### IF-08 — Soft-delete preserva histórico permanente
430:### 8.1 Contrato (E-07) — guarda I-03, T-2
447:### 8.2 Partida (E-13) — guarda I-05, T-8, IF-04
462:### 8.3 Edição (E-11) — guarda I-07, T-1, PF-G-09
475:### 8.4 Escalação (E-15) — guarda I-06, IF-06
484:### 8.5 Negociação (E-16) / Proposta (E-17) — guarda I-08, T-4
495:### 8.6 Solicitação (E-20) — guarda T-4, IF-05
505:### 8.7 Assinatura (E-02) — guarda I-02
531:### 10.1 Não-objetivos respeitados (N-01 a N-26)
541:### 10.2 Implicações de desenho do MVP honradas
555:### 11.1 Subtasks imediatas da task 0.5
560:### 11.2 Tasks downstream
568:### 11.3 Decisões consolidadas
579:### 11.4 Pendências encaminhadas (não resolvidas aqui)

=== Contagem invariantes por tier ===
I- (estruturais, únicos): 10
T- (domínio, únicos): 8
IF- (fronteira, únicos): 8

=== Listas por tier ===
I-: I-01 I-02 I-03 I-04 I-05 I-06 I-07 I-08 I-09 I-10 
T-: T-1 T-2 T-3 T-4 T-5 T-6 T-7 T-8 
IF-: IF-01 IF-02 IF-03 IF-04 IF-05 IF-06 IF-07 IF-08 

=== PFs referenciados ===
59
PFs lista: PF-FP-01 PF-FP-02 PF-FP-03 PF-FP-05 PF-FP-06 PF-FP-07 PF-FP-09 PF-FP-10 PF-FP-12 PF-FP-13 PF-FP-15 PF-FP-16 PF-FP-17 PF-FP-19 PF-FP-20 PF-FP-21 PF-FP-22 PF-FP-25 PF-FP-26 PF-FP-28 PF-FP-29 PF-FP-32 PF-FS-01 PF-FS-03 PF-FS-04 PF-FS-05 PF-FS-06 PF-FS-07 PF-FS-08 PF-FS-09 PF-FS-12 PF-FS-13 PF-FS-18 PF-FS-19 PF-FS-20 PF-FS-21 PF-FS-22 PF-FS-23 PF-FS-24 PF-FS-25 PF-FS-26 PF-FS-27 PF-FS-28 PF-FS-30 PF-FS-31 PF-G-02 PF-G-03 PF-G-05 PF-G-06 PF-G-07 PF-G-08 PF-G-09 PF-X-01 PF-X-02 PF-X-03 PF-X-04 PF-X-05 PF-X-06 PF-X-08 

=== Entidades E-XX ===
E-01 E-02 E-03 E-05 E-06 E-07 E-08 E-11 E-12 E-13 E-14 E-15 E-16 E-17 E-19 E-20 E-21 E-22 E-23 E-24 E-25 
=== Gates G-1..G-5 ===
G-1 G-2 G-3 G-4 G-5 
=== Não-objetivos N-XX ===
N-01 N-12 N-15 N-18 N-20 N-24 N-26 
=== Fluxos FS-XX referenciados ===
FS-01 FS-03 FS-04 FS-05 FS-06 FS-07 FS-08 FS-09 FS-11 FS-12 FS-13 FS-18 FS-19 FS-20 FS-21 FS-22 FS-23 FS-24 FS-25 FS-26 FS-27 FS-28 FS-30 FS-31 
=== Placeholder check ===
9
=== JSON válido (sprints.json) ===
OK
[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
grep -niE "placeholder|TODO|FIXME|xxx|lorem" "$F"
57:1. **Deve ser verdadeira em todo instante observável** do sistema (entre transações e durante transações, do ponto de vista de leitores externos).
119:- **Enunciado:** Para todo `usuario` existe exatamente um `organizacao` (tenant) ao qual pertence; não existe usuário órfão nem usuário pertencente a mais de um tenant.
139:- **Enunciado:** Para todo par `(pessoa_id, clube_id)`, existe no máximo um `contrato` com `status = 'ativo'` em qualquer instante.
149:- **Enunciado:** Para todo par `(atleta_id, equipe_id)`, existe no máximo um `rel_equipe_atleta` com `dt_fim IS NULL` em qualquer instante.
243:- **Enunciado:** Para todo `evento` com `tipo IN ('gol', 'cartao_amarelo', 'cartao_vermelho', 'substituicao_entrada', 'substituicao_saida')`, o `atleta_id` está na `escalacao` confirmada da Partida para a Equipe correspondente; após um `cartao_vermelho` do atleta na Partida, nenhum novo evento esportivo do mesmo atleta é admitido.
355:- **Notas:** a regra vale para **todos** os gates, mas o gate mais complexo é G-5 (cria contrato destino, rescinde origem, encerra `rel_equipe_atleta`) — por isso é o alvo prioritário dos testes de contrato (task 6.3.3).
380:- **Guarda:** RBAC nega `DELETE` em `partida`/`evento`/`auditoria` a todo papel, inclusive `admin_tenant`; trigger `BEFORE DELETE` rejeita; apenas `admin_plataforma` pode executar `DELETE` físico em auditoria mediante procedimento de retenção (task 6.2.3) e com meta-auditoria.
391:Mapa bidirecional: quais pontos de falha (de 0.4.3) protegem cada invariante. Confirma cobertura total — todo invariante tem ao menos um PF que o protege (bloqueio preventivo) ou o exercita no sentido de exceção (gate de exceção/compensação).
572:3. **Atomicidade** (T-4/IF-05) é garantida por transação única em todos os gates; sem efeito parcial.
[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
grep -n "Competição" "$F" | head -10
echo "---"
grep -n "anexo\|Anexo" "$F" | head -10
171:- **Guarda:** trigger `BEFORE INSERT/UPDATE` em `rel_escalacao_atleta` rejeita `count(titular) > 11`; trigger `BEFORE UPDATE` em `escalacao.status → 'confirmada'` valida `count(titular) = 11`; o número de reservas é configurável por Regra de Competição (pendência 2.2.4).
299:- **Notas:** a janela de 24h é parametrizável por Regra de Competição em futuro próximo (pendência 2.2.4), mas o valor default no MVP é 24h; G-3 sobre partida em WO é bloqueado — WO é terminal (PF-G-05).
563:- **2.2.4 — Transições de estado:** as máquinas de estados da Seção 8 definem os estados; a task 2.2.4 detalha as **Regras de Competição** paramétricas (nº de titulares em base, antecedência de janela, placar de WO, janela de transferência) que variam por Edição.
---
195:- **Notas:** a proposta aceita dispara o workflow de G-5 (approval mirror, T-4); o cancelamento da negociação após aceite move a proposta para `recusada` mas **preserva** os anexos (PF-FS-09).
491:- `Proposta.enviada → aceita`: apenas uma por Negociação (I-08, PF-FS-07); exige ≥ 1 anexo (R20, PF-FS-12).
493:- `Negociação → cancelada` após proposta aceita: proposta → `recusada`, anexos preservados (PF-FS-09).
[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.5.1.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
@@ -191,9 +191,9 @@
 - **Guarda:** constraint parcial `UNIQUE (negociacao_id) WHERE status = 'aceita'` em `proposta`; trigger `BEFORE UPDATE` valida que nenhuma outra proposta da mesma negociação está `aceita`.
 - **Camada:** DB (constraint parcial).
 - **Severidade:** C — duas propostas aceitas gerariam dois contratos destino (viola I-03 no destino).
 - **Recuperação:** bloqueio preventivo (PF-FS-07); rollback atômico se o conflito for detectado no deferimento de G-5 (PF-FS-08).
-- **Notas:** a proposta aceita dispara o workflow de G-5 (approval mirror, T-4); o cancelamento da negociação após aceite move a proposta para `recusada` mas **preserva** os anexos (PF-FS-09).
+- **Notas:** a proposta aceita dispara o workflow de G-5 (approval mirror, T-4); o cancelamento da negociação após aceite move a proposta para `recusada` mas **preserva** os anexos (E-18, PF-FS-09).
 
 ### I-09 — Auditoria append-only
 
 - **Enunciado:** A tabela `auditoria` (E-23) admite apenas `INSERT`; `UPDATE` e `DELETE` são permanentemente rejeitados, inclusive para `admin_plataforma`.

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.5.1.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
@@ -487,9 +487,9 @@
 Negociação: aberta → em_aprovacao → concluida | cancelada
 Proposta:   enviada → aceita (UNIQUE por negociação) → efetivada | recusada
 ```
 
-- `Proposta.enviada → aceita`: apenas uma por Negociação (I-08, PF-FS-07); exige ≥ 1 anexo (R20, PF-FS-12).
+- `Proposta.enviada → aceita`: apenas uma por Negociação (I-08, PF-FS-07); exige ≥ 1 anexo (E-18, R20, PF-FS-12).
 - `Negociação.em_aprovacao → concluida`: G-5 deferido atomicamente (T-4, IF-05).
 - `Negociação → cancelada` após proposta aceita: proposta → `recusada`, anexos preservados (PF-FS-09).
 
 ### 8.6 Solicitação (E-20) — guarda T-4, IF-05

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.5.1.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
@@ -460,8 +460,10 @@
 - `concluida → em_andamento`: **apenas** via G-3 deferido dentro de 24h ou com Solicitação `partida_reabertura` (T-8, IF-04).
 
 ### 8.3 Edição (E-11) — guarda I-07, T-1, PF-G-09
 
+Edição (E-11) é filha de Competição (E-10); a máquina abaixo governa o ciclo de vida de uma temporada.
+
 ```
 rascunho → publicada → em_andamento → concluida
               ↓
          cancelada

[0m
[0m$ [0mF=/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
echo "=== Entidades E-XX (final) ===" && grep -oE "E-[0-9]{2}" "$F" | sort -u | tr '\n' ' '
echo "" && echo "=== Total invariantes ===" && echo -n "I: " && grep -oE "\bI-[01][0-9]\b" "$F" | sort -u | wc -l && echo -n "T: " && grep -oE "\bT-[1-8]\b" "$F" | sort -u | wc -l && echo -n "IF: " && grep -oE "\bIF-0[1-8]\b" "$F" | sort -u | wc -l
echo "=== Linhas ===" && wc -l "$F"
echo "=== JSON sprints.json válido ===" && python3 -c "import json; json.load(open('/home/alex/saas-futebol/orchestrator/sprints.json')); print('OK')"
=== Entidades E-XX (final) ===
E-01 E-02 E-03 E-05 E-06 E-07 E-08 E-10 E-11 E-12 E-13 E-14 E-15 E-16 E-17 E-18 E-19 E-20 E-21 E-22 E-23 E-24 E-25 
=== Total invariantes ===
I: 10
T: 8
IF: 8
=== Linhas ===
600 /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.5.1.md
=== JSON sprints.json válido ===
OK
[0m

```