# Subtask 0.2.3 — Separar futuro desejado

**Sprint:** Fundação, escopo e contratos
**Task:** Delimitar escopo
**Status:** completed
**Timestamp:** 2026-06-28T22:09:48.982669

---

## Output do OpenCode (GLM 5.2)

Entendi o contexto. Vou gerar o conteúdo técnico da subtask 0.2.3 (Separar futuro desejado), mantendo consistência com os 26 não-objetivos (N-01 a N-26) já declarados em 0.2.2 e com a visão/proposta/público-alvo definidos em 0.1.x.

Deixe-me verificar o estado atual e se há conteúdo da 0.2.1 para alinhar o escopo MVP.
Tenho contexto completo. Agora vou gerar o documento técnico da subtask 0.2.3 — Separar futuro desejado, distinguindo-o dos 26 não-objetivos permanentes (0.2.2) e organizando as capacidades desejadas pós-MVP por horizonte, com dependências no MVP e sprint alvo.
Verifiquei a contagem de reclassificação e há um erro: são 12 diferidos (N-01, N-02, N-03, N-04, N-05, N-15, N-17, N-18, N-19, N-24, N-25, N-26) e 14 permanentes, não 11/15. Vou corrigir.
Conteúdo gerado em `orchestrator/reports/sprint_0_subtask_0.2.3.md`.

**Resumo do que foi produzido:**
- **25 itens de futuro desejado** (F-01 a F-25) em 3 horizontes (curto/médio/longo prazo pós-MVP).
- **Reclassificação dos 26 não-objetivos de 0.2.2**: 12 diferidos → absorvidos no catálogo F-*; 14 mantidos como permanentes.
- Cada item traz descrição, valor esperado, **dependência no MVP** (com referência às sprints/tasks 1–6), origem (N-* diferido ou novo) e **sprint alvo** de reavaliação.
- **Seção 6 — Implicações no MVP** com 7 diretrizes anti-regresso (tenant_id+RLS, API separada da UI, motor de notificações abstraído, aprovações como dados, auditoria com diff, IA assistiva, esquema normalizado) — a serem detalhadas em 0.5.2.
- Governança do backlog e critérios de promoção para roadmap.

Esta subtask está marcada `needs_review: true` em `sprints.json` — é ponto de parada. Após sua aprovação, a próxima subtask será **0.3.1 — Listar entidades principais**.


## Stderr

```
[0m
> build · glm-5.2
[0m
[0m$ [0mls -la /home/alex/saas-futebol/orchestrator/reports/ 2>/dev/null && echo "---" && ls -la /home/alex/saas-futebol/orchestrator/ 2>/dev/null
total 24
drwxrwxr-x 2 alex alex 4096 jun 28 22:00 .
drwxrwxr-x 6 alex alex 4096 jun 28 21:41 ..
-rw-rw-r-- 1 alex alex 1214 jun 28 21:42 sprint_0_subtask_0.1.2.md
-rw-rw-r-- 1 alex alex 2352 jun 28 21:51 sprint_0_subtask_0.1.3.md
-rw-rw-r-- 1 alex alex 6114 jun 28 22:04 sprint_0_subtask_0.2.2.md
---
total 72
drwxrwxr-x 6 alex alex  4096 jun 28 21:41 .
drwxrwxr-x 5 alex alex  4096 jun 28 21:24 ..
drwxrwxr-x 2 alex alex  4096 jun 28 21:22 prompts
drwxrwxr-x 2 alex alex  4096 jun 28 21:41 __pycache__
drwxrwxr-x 2 alex alex  4096 jun 28 22:00 reports
-rw------- 1 alex alex 16525 jun 28 21:48 runner.py
-rw------- 1 alex alex 23885 jun 28 22:04 sprints.json
drwxrwxr-x 2 alex alex  4096 jun 28 21:23 state
-rw------- 1 alex alex  2975 jun 28 21:40 whatsapp_notify.py
[0m
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.1.2.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.1.3.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.2.2.md
[0m→ [0mRead orchestrator/prompts/system_orchestrator.txt
[0m→ [0mRead README.md
[0m→ [0mRead orchestrator/runner.py
[0m→ [0mRead orchestrator/state/execution_state.json
[0m
[0m$ [0mls -la /home/alex/saas-futebol/orchestrator/reports/ /home/alex/saas-futebol/docs/prd/ /home/alex/saas-futebol/docs/sprints/ /home/alex/saas-futebol/docs/techspec/ 2>/dev/null
/home/alex/saas-futebol/docs/prd/:
total 8
drwxrwxr-x 2 alex alex 4096 jun 28 21:18 .
drwxrwxr-x 5 alex alex 4096 jun 28 21:18 ..

/home/alex/saas-futebol/docs/sprints/:
total 8
drwxrwxr-x 2 alex alex 4096 jun 28 21:18 .
drwxrwxr-x 5 alex alex 4096 jun 28 21:18 ..

/home/alex/saas-futebol/docs/techspec/:
total 8
drwxrwxr-x 2 alex alex 4096 jun 28 21:18 .
drwxrwxr-x 5 alex alex 4096 jun 28 21:18 ..

/home/alex/saas-futebol/orchestrator/reports/:
total 24
drwxrwxr-x 2 alex alex 4096 jun 28 22:00 .
drwxrwxr-x 6 alex alex 4096 jun 28 21:41 ..
-rw-rw-r-- 1 alex alex 1214 jun 28 21:42 sprint_0_subtask_0.1.2.md
-rw-rw-r-- 1 alex alex 2352 jun 28 21:51 sprint_0_subtask_0.1.3.md
-rw-rw-r-- 1 alex alex 6114 jun 28 22:04 sprint_0_subtask_0.2.2.md
[0m
[0m← [0mWrite orchestrator/reports/sprint_0_subtask_0.2.3.md
Wrote file successfully.
[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.2.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.3.md
@@ -68,9 +68,9 @@
 | N-24 Compliance jurídico automatizado (CBF/FIFA) | Governança | **Diferido → F-24** |
 | N-25 BI self-service com consulta livre e cubos OLAP | BI/API | **Diferido → F-10** |
 | N-26 API pública versionada para integradores | BI/API | **Diferido → F-03** |
 
-**Resumo da reclassificação:** 11 não-objetivos viram futuro desejado (F-01, F-02, F-03, F-06, F-09, F-10, F-11, F-12, F-13, F-14, F-23, F-24); 15 permanecem como não-objetivos permanentes.
+**Resumo da reclassificação:** 12 não-objetivos viram futuro desejado (F-01, F-02, F-03, F-06, F-09, F-10, F-11, F-12, F-13, F-14, F-23, F-24); 14 permanecem como não-objetivos permanentes.
 
 > Observação: a numeração F-* segue ordem lógica por horizonte, não a ordem de N-*. O mapeamento N→F está expresso na coluna "Desfecho" acima.
 
 ---

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.2.3.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.3.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.3.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.3.md
@@ -311,9 +311,9 @@
 - **25 itens de futuro desejado** (F-01 a F-25) distribuídos em três horizontes:
   - Horizonte 1 (3–6 meses pós-MVP): **F-01 a F-08** (8 itens).
   - Horizonte 2 (6–12 meses pós-MVP): **F-09 a F-16** (8 itens).
   - Horizonte 3 (12+ meses pós-MVP): **F-17 a F-25** (9 itens).
-- **11 não-objetivos de 0.2.2 reclassificados como diferidos** e absorvidos no catálogo F-*.
-- **15 não-objetivos permanecem permanentes** (reafirmados na Seção 5).
+- **12 não-objetivos de 0.2.2 reclassificados como diferidos** e absorvidos no catálogo F-*.
+- **14 não-objetivos permanecem permanentes** (reafirmados na Seção 5).
 - **7 implicações de desenho do MVP** registradas para prevenção de regresso arquitetural (Seção 6), a serem detalhadas em 0.5.2 (Fronteiras técnicas).
 
 **Próxima subtask:** 0.3.1 — Listar entidades principais (Task 0.3 — Mapear entidades). Esta subtask 0.2.3 exige revisão (`needs_review: true`) antes de avançar.

[0m

```