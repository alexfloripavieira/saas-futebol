# Subtask 0.6.2 — Registrar pendências abertas (Sprint 0)

**Sprint:** Fundação, escopo e contratos
**Task:** Consolidar Sprint 0
**Status:** completed
**Época:** 2026-06-29
**Modelo:** opencode-go/glm-5.2

---

# Pendências e dúvidas abertas da Sprint 0

Consolidação das pendências que **não foram resolvidas** na Sprint 0 e precisam ser tratadas em sprints posteriores. Fontes: handoffs de 0.4.3 (Seção 10), 0.5.3 (Seção 13.4) e 0.6.1 (Seção 10). Itens marcados com `needs_review` exigem validação humana antes do encerramento definitivo.

## 1. Pendências para a Sprint 1 — Fundação da plataforma

| ID | Pendência | Contexto | Decisão necessária |
|----|-----------|----------|--------------------|
| P-1.1 | **Configurar INT-01 (gateway de pagamento)** | Necessário já na Sprint 1 para onboarding/assinatura (FP-01/FP-02, I-02) | Provisionar conta; definir se Stripe ou Mercado Pago (decisão formal fica em 5.1.1, mas sandbox é preciso agora) |
| P-1.2 | **Configurar INT-02 (e-mail transacional)** | Único canal externo de notificação (E-22); FS-07 depende | Provisionar provedor; configurar SPF/DKIM/DMARC no domínio remetente |
| P-1.3 | **Validar público-alvo** (0.1.3, `needs_review`) | Recorte entre clubes profissionais e federações regionais | Confirmar segmentação e papéis antes do design system |
| P-1.4 | **Tokens visuais e componentes base** (1.3.x) | Sem design system definido | Definir paleta, tipografia, componentes base e estados base |

## 2. Pendências para a Sprint 2 — Núcleo de dados do futebol

| ID | Pendência | Contexto | Decisão necessária |
|----|-----------|----------|--------------------|
| P-2.1 | **Regras de Competição paramétricas** (task 2.2.4, `needs_review`) | Referenciadas por PF-FP-20, PF-FP-24, PF-FP-16, T-8 | Definir: antecedência mínima de escalação; período de suspensão por cartão vermelho; quórum mínimo para publicar edição |
| P-2.2 | **Janela de imutabilidade pós-fato** (T-8, IF-04) | 24h é valor provisório; parametrizável por tenant | Confirmar valor padrão e possibilidade de override por tenant |
| P-2.3 | **Rate limit por tenant em import/export** (task 2.4) | Limite de 10 MB / 5000 linhas é provisório | Definir cotas por plano (I-02) e políticas de conflito `pular` vs `sobrescrever` |
| P-2.4 | **Validar relacionamentos entre entidades** (0.3.3, `needs_review`) | 27 vínculos (R01–R27) e 8 regras transversais | Revisão humana antes de gerar schema DB |

## 3. Pendências para a Sprint 5 — Integrações, automações e IA

| ID | Pendência | Contexto | Decisão necessária |
|----|-----------|----------|--------------------|
| P-5.1 | **Escolha do provedor de pagamento** (5.1.1) | INT-01 — Stripe vs Mercado Pago | Decisão comercial/técnica; contrato 0.5.3 é agnóstico |
| P-5.2 | **Escolha do provedor de e-mail** (5.1.1) | INT-02 — Postmark vs SES vs SendGrid | Decisão comercial/técnica |
| P-5.3 | **Escolha do object storage** (5.1.1) | INT-03 — S3 vs Cloudflare R2 vs MinIO | Viés a R2/MinIO para custo (0.5.3) |
| P-5.4 | **IP allowlist dos provedores** (5.1.x) | Validação HMAC já especificada | Configurar com dados do provedor escolhido |
| P-5.5 | **Validar integrações externas** (0.5.3, `needs_review`) | 5 integrações (INT-01 a INT-05), SLAs e webhooks | Revisão humana dos contratos antes da implementação |

## 4. Pendências para a Sprint 6 — Segurança, qualidade e governança

| ID | Pendência | Contexto | Decisão necessária |
|----|-----------|----------|--------------------|
| P-6.1 | **Período de carência de inadimplência** (task 6.1.3) | Entre `invoice.payment_failed` e `assinatura.status = 'suspenda'` (PF-FS-24, PF-X-08) | Definir janela (ex.: 3, 7 ou 14 dias) e notificações durante a carência |
| P-6.2 | **Política de retenção de E-24** (task 6.2.3) | Log de integração é append-only (I-09) mas cresce indefinidamente (PF-FS-31) | Definir tempo de retenção e mecanismo de poda com preservação de auditoria |
| P-6.3 | **Retenção de auditoria (E-23)** (task 6.2.3) | Auditoria append-only; soft-delete preserva histórico (T-6) | Definir retenção mínima e política de arquivamento frio |

## 5. Itens diferidos para pós-MVP (futuro desejado)

| ID | Item | Origem |
|----|------|--------|
| F-XX | **Antivírus de anexos** (INT-03) | 0.5.3 Seção 13.4 — fora do MVP |
| F-08 a F-11 | Estrutura física (estádio/CT/instalações) | 0.3.3 — não-objetivos N-12 a N-15 reclassificados |
| F-20 | Compliance jurídico automatizado (CBF/FIFA) | 0.3.3 — não-objetivo N-24 reclassificado |
| F-01 a F-25 | **25 itens de futuro desejado** em 3 horizontes | 0.2.3 (`needs_review`) — reavaliar no handoff 0.6.3 |

## 6. Dúvidas abertas para validação humana (`needs_review: true`)

Estas subtasks foram completadas mas mantêm flag de revisão pendente:

- **0.1.3** — Definir público-alvo
- **0.2.3** — Separar futuro desejado (12 não-objetivos reclassificados para F-*)
- **0.3.3** — Descrever relacionamento entre entidades (R01–R27 + 8 regras transversais)
- **0.4.3** — Marcar pontos de falha (80 PFs; 10 pendências resolvidas com decisão consolidada)
- **0.5.3** — Mapear integrações externas (INT-01 a INT-05; escolha de provedores pendente)

## 7. Resumo executivo

- **9 pendências técnicas** distribuídas entre Sprint 1 (4), Sprint 2 (4) e Sprint 5 (5, com sobreposição de provedores).
- **3 pendências de governança** para Sprint 6 (carência de inadimplência, retenção de E-24, retenção de E-23).
- **25 itens de futuro desejado** (F-01 a F-25) reavaliáveis pós-MVP.
- **5 subtasks** com `needs_review: true` aguardando validação humana antes do handoff final (0.6.3).
- **Nenhuma pendência bloqueia o início da Sprint 1**, mas INT-01/INT-02 em sandbox são pré-requisitos práticos para 1.2 (autenticação/assinatura) e 1.4 (observabilidade de notificações).

**Próxima subtask:** 0.6.3 — Preparar handoff para Sprint 1 (`needs_review: true`).
