# Subtask 0.2.2 — Declarar não-objetivos

**Sprint:** Fundação, escopo e contratos
**Task:** Delimitar escopo
**Status:** completed
**Timestamp:** 2026-06-28T22:04:40.579703

---

## Output do OpenCode (GLM 5.2)

Conteúdo salvo em `orchestrator/reports/sprint_0_subtask_0.2.2.md`: 26 não-objetivos (N-01 a N-26) cobrindo esportivo-tático, financeiro, B2C/torcedor, marketing, infra/Mobile nativa, IA aberta, governança jurídica/eleitoral e BI/API públicas — cada item com justificativa, cobertura temporária e impacto nas sprints seguintes. A próxima subtask `0.2.3 — Separar futuro desejado` (needs_review) foi sinalizada como ponto de parada.


## Stderr

```
[0m
> build · glm-5.2
[0m
[0m$ [0mls /home/alex/saas-futebol/orchestrator/reports/ 2>/dev/null
sprint_0_subtask_0.1.2.md
sprint_0_subtask_0.1.3.md
[0m
[0m✱ [0mGlob "orchestrator/reports/*.md"[90m 2 matches[0m
[0m
[0m$ [0mls /home/alex/saas-futebol/orchestrator/reports/ -la; find /home/alex/saas-futebol/orchestrator -name "*0.1.1*" 2>/dev/null; find /home/alex/saas-futebol/orchestrator -name "*0.2.1*" 2>/dev/null
total 16
drwxrwxr-x 2 alex alex 4096 jun 28 21:47 .
drwxrwxr-x 6 alex alex 4096 jun 28 21:41 ..
-rw-rw-r-- 1 alex alex 1214 jun 28 21:42 sprint_0_subtask_0.1.2.md
-rw-rw-r-- 1 alex alex 2352 jun 28 21:51 sprint_0_subtask_0.1.3.md
[0m
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.1.3.md
[0m→ [0mRead orchestrator/reports/sprint_0_subtask_0.1.2.md
[0m→ [0mRead orchestrator/prompts/system_orchestrator.txt
[0m
[0m$ [0mfind /home/alex/saas-futebol -name "*.md" -not -path "*/node_modules/*" 2>/dev/null; ls /home/alex/saas-futebol/docs/prd /home/alex/saas-futebol/docs/sprints /home/alex/saas-futebol/docs/techspec 2>/dev/null
/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.1.2.md
/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.1.3.md
/home/alex/saas-futebol/README.md
/home/alex/saas-futebol/docs/prd:

/home/alex/saas-futebol/docs/sprints:

/home/alex/saas-futebol/docs/techspec:
[0m
[0m→ [0mRead README.md
[0m
[0m$ [0mcat /home/alex/saas-futebol/orchestrator/state/execution_state.json 2>/dev/null; echo "---README check done"
{
  "current_sprint": 0,
  "current_task": "0.2",
  "current_subtask": "0.2.2",
  "status": "running",
  "history": [
    {
      "subtask_id": "0.1.2",
      "subtask_name": "Escrever proposta de valor",
      "sprint": "Fundação, escopo e contratos",
      "timestamp": "2026-06-28T21:42:40.361648",
      "report": "/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.1.2.md"
    },
    {
      "subtask_id": "0.1.3",
      "subtask_name": "Definir público-alvo",
      "sprint": "Fundação, escopo e contratos",
      "timestamp": "2026-06-28T21:51:41.551331",
      "report": "/home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.1.3.md"
    }
  ],
  "review_queue": [],
  "failures": {},
  "started_at": "2026-06-28T21:37:59.744354",
  "last_updated": "2026-06-28T21:57:37.546970"
}---README check done
[0m
[0m← [0mWrite orchestrator/reports/sprint_0_subtask_0.2.2.md
Wrote file successfully.
[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.2.2.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.2.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.2.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.2.md
@@ -52,9 +52,9 @@
 ### 3.3 Ecossistema e produtos voltados ao torcedor
 
 | ID | Item | Justificativa | Cobertura temporária |
 |----|------|----------------|------------------------|
-| N-09 | App/Site voltado ao torcedor, ingressos online, sócio-torcedor | Produto de大喊病因另一种生态; SaaS de operações é B2B对 clubes/federações, não B2C. | Plataforma de ingressos terceirizada. |
+| N-09 | App/Site voltado ao torcedor, ingressos online, sócio-torcedor | Pertence a outro ecossistema (B2C); a SaaS de operações é B2B voltada a clubes/federações, não ao torcedor. | Plataforma de ingressos terceirizada. |
 | N-10 | E-commerce de produtos oficiais (loja virtual) | Pertence a outro vertical de monetização. | Plataforma de e-commerce do clube. |
 | N-11 | Stream de partidas e produção de vídeo | Infraestrutura de mídia pesada, fora do domínio do SaaS. | Concessionária de transmissão. |
 
 ### 3.4 Comunicação e marketing

[0m
[0m← [0mEdit orchestrator/reports/sprint_0_subtask_0.2.2.md
Index: /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.2.md
===================================================================
--- /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.2.md
+++ /home/alex/saas-futebol/orchestrator/reports/sprint_0_subtask_0.2.2.md
@@ -69,9 +69,9 @@
 
 | ID | Item | Justificativa | Cobertura temporária |
 |----|------|----------------|------------------------|
 | N-15 | Multi-tenancy com isolamento físico de banco por cliente | No MVP será multi-tenant via separação lógica (tenant_id); isolamento físico é custo alto sem ganho imediato. | Isolamento lógico + Row-Level Security. |
-| N-16 | Deploy em on-premise / data center próprio do cliente | SaaS é nativo de nuvem; on-preise é outro produto. | Nuvem gerenciada. |
+| N-16 | Deploy em on-premise / data center próprio do cliente | SaaS é nativo de nuvem; on-premise é outro produto. | Nuvem gerenciada. |
 | N-17 | Aplicação mobile nativa (iOS/Android) | No MVP o acesso é via web responsiva; app nativo requer sprint própria (sprint_4 cobre interface web). | Web responsiva PWA-ready. |
 | N-18 | Suporte offline com sincronização posterior | Operação depende de fluxos em tempo real (aprovações, auditoria); offline adiciona complexidade fora do MVP. | Requer conexão para uso. |
 | N-19 | Migração automática de dados de sistemas legados do clube | Cada clube tem formato próprio; no MVP há apenas importação assistida (sprint_2), sem scripts de migração. | Planilha padronizada + importação assistida. |
 

[0m

```