# Subtask 0.5.3 — Mapear integrações externas

**Sprint:** Fundação, escopo e contratos
**Task:** Contratos e invariantes
**Status:** completed
**Timestamp:** 2026-06-29T00:00:00.000000

---

## Output do OpenCode (GLM 5.2)

Contexto herdado das subtasks anteriores: 25 entidades (E-01–E-25, sendo E-24 Log de integração e E-25 Sistema externo reservados para Sprint 5), R27 (Log de integração → Sistema externo N:1), regra transversal T-7 e invariante de fronteira IF-07 (idempotência por `correlation_id` + `sistema_externo_id` UNIQUE), 26 não-objetivos (N-01–N-26) e o handoff explícito da Seção 11 de 0.4.3 apontando PF-FP-01, PF-FS-19, PF-FS-24 e PF-X-08 como dependentes de contratos de SLA/webhook/retry a detalhar aqui. Vou escrever o documento técnico completo.

Subtask **0.5.3 — Mapear integrações externas** concluída e salva em `orchestrator/reports/sprint_0_subtask_0.5.3.md`.

**5 integrações externas do MVP** catalogadas (INT-01 a INT-05): gateway de pagamento, provedor de e-mail transacional, armazenamento de objetos, importação de arquivos (ingresso) e exportação de arquivos (egresso). Cada uma traz sistema externo (E-25), endpoints, autenticação, fluxo de dados entrada/saída, criticidade, riscos, PFs relacionados e contrato de SLA/webhook/retry. Inclui matriz de criticidade, matriz de riscos, fluxo de dados consolidado e handoff para a task 5.1 (Sprint 5). Fronteiras respeitadas: 9 não-objetivos confirmados fora do escopo (N-09/N-11 push/SMS, N-18 a N-20 ERP/financeiro, N-24 streaming, N-25 BI, N-26 API pública). Toda integração é registrada em E-24 (R27) e guardada por T-7/IF-07. `needs_review: true` mantido.

---

# Mapeamento de integrações externas — SaaS de futebol (MVP)

## 1. Sumário executivo

O MVP do SaaS de futebol é uma plataforma B2B **fechada**: não expõe API pública (N-26), não faz BI self-service (N-25), não integra ERP/financeiro (N-18 a N-20), não emite push/SMS (N-09/N-11) e não consome federações esportivas (N-24). Mesmo assim, **cinco integrações externas são indispensáveis** à operação e devem ser contratadas/configuradas antes da Sprint 5:

| ID | Integração | Função no MVP | Criticidade |
|----|------------|---------------|-------------|
| INT-01 | Gateway de pagamento | Cobrança recorrente de assinaturas (E-02); governa suspensão/reativação do tenant (PF-FP-01, PF-FS-24, PF-X-08) | Crítica |
| INT-02 | Provedor de e-mail transacional | Canal de notificação externo (E-22) complementar ao in-app (FS-07); únicos canais do MVP | Alta |
| INT-03 | Armazenamento de objetos (S3-compatible) | Persistência de Anexos (E-18) e arquivos de importação/exportação (FS-05/FS-06) | Alta |
| INT-04 | Importação de arquivos (ingresso) | Carga de dados em lote via CSV/XLSX pelo `admin_tenant` (FS-05) | Média |
| INT-05 | Exportação de arquivos (egresso) | Saída de listagens/relatórios em CSV/XLSX/PDF (FS-06) | Média |

**Princípios transversais (já formalizados):**

1. Toda chamada a sistema externo grava em **E-24 (Log de integração)** com `sistema_externo_id`, `http_status`, `latencia_ms`, `correlation_id`, payload redigido (R27, 0.3.3).
2. Toda integração é **idempotente** por `correlation_id` + `sistema_externo_id` UNIQUE (T-7, IF-07, 0.5.1).
3. Toda integração tem **retry com backoff exponencial** (3 tentativas) e, após falha persistente, escalada para a fila de exceções (R27 PE, 0.3.3).
4. Segredos de autenticação **nunca** transitam em query string ou log; redação de payload em E-24 (IF-08 soft-delete, 0.5.1).
5. Nenhuma integração do MVP é síncrona no caminho crítico de UI além de INT-01 (checkout) e INT-03 (upload/download); demais são assíncronas via job.

O detalhamento destes contratos alimenta a task **5.1 (Integrações externas, Sprint 5)** e os testes de contrato da task **6.3.3**.

---

## 2. Escopo e fronteiras

### 2.1 Estão no MVP (escopo deste documento)

- INT-01 a INT-05 acima.
- Catálogo **E-25 (Sistema externo)** com `status ∈ {'ativo', 'descontinuado'}`, credencial referenciada por ID (segredo em cofre, não no catálogo).
- **E-24 (Log de integração)** como túmulo append-only de toda chamada.

### 2.2 Não-objetivos confirmados fora do MVP (N-XX de 0.2.2)

| Não-objetivo | Impacto neste mapa |
|--------------|---------------------|
| N-09 / N-11 push e SMS | Apenas in-app + e-mail; INT-02 cobre o canal externo |
| N-18 a N-20 ERP / contabilidade / bilheteria | Nenhuma integração financeira interna; INT-01 só cobrança de assinatura, sem lançamento contábil |
| N-24 streaming e compliance jurídico automatizado (CBF/FIFA) | Nenhum consumo de feed de federação; dados esportivos são entry manual ou import (INT-04) |
| N-25 BI self-service | INT-05 gera relatórios pré-definidos, não consulta livre |
| N-26 API pública versionada | Todas as integrações são **inbound para sistemas externos** ou **outbound para provedores**; nenhuma exposta a integradores de terceiros |

### 2.3 Diretriz de desenho herdada (0.2.3, 0.5.2)

- **Aplicação não bypassa invariantes:** o estado de verdade de `assinatura.status` é o DB interno, não o gateway (PF-X-08). Webhook do gateway é **entrada de evento**, nunca gravação direta — um job idempotente aplica a transição.
- **Tenant boundary:** nenhuma integração recebe dados de outro tenant; INT-02 (e-mail) endereça apenas usuários do tenant em contexto; INT-03 prefixa chaves com `tenant_id`.

---

## 3. Catálogo de integrações

| ID | Sistema externo (E-25) | Direção | Síncrona? | Entidades tocadas | PFs relacionados |
|----|------------------------|---------|-----------|-------------------|------------------|
| INT-01 | Gateway de pagamento (ex.: Stripe Billing / Mercado Pago Assinaturas) | Bidirecional (API + webhook) | Checkout síncrono; webhook assíncrono | E-02 Assinatura, E-01 Organização | PF-FP-01, PF-FS-24, PF-X-08 |
| INT-02 | Provedor de e-mail transacional (ex.: Postmark / SES / SendGrid) | Outbound + webhook de bounce | Outbound assíncrono (job) | E-22 Notificação, E-06 Usuário | PF-FS-19 |
| INT-03 | Armazenamento de objetos S3-compatible (ex.: AWS S3 / Cloudflare R2 / MinIO) | Bidirecional (PUT/GET/DELETE) | Upload/download síncrono; lifecycle assíncrono | E-18 Anexo, E-24 Log | PF-FS-13, PF-FS-06 |
| INT-04 | Ingestão de arquivos do cliente (CSV/XLSX via browser) | Inbound (upload do `admin_tenant`) | Upload síncrono; processamento assíncrono (job) | E-07 a E-15 conforme entidade importada | PF-FS-13, PF-FS-16 |
| INT-05 | Geração e download de relatórios (CSV/XLSX/PDF) | Outbound (download do usuário) | Geração assíncrona (job); download síncrono | E-07 a E-15 conforme entidade exportada | PF-FS-06 |

---

## 4. Detalhamento — INT-01 Gateway de pagamento

### 4.1 Sistema externo

- **E-25:** `gateway_pagamento`, `status = 'ativo'`.
- **Produto de referência:** Stripe Billing ou Mercado Pago Assinaturas (decisão de Sprint 5). O contrato abaixo é agnóstico ao provedor.
- **Função:** criação de cliente, criação de assinatura recorrente, cobrança, eventos de ciclo de vida (pagamento bem-sucedido, falha, expiração, cancelamento).

### 4.2 Endpoints (API) — superfície mínima

| Operação | Direção | Endpoint lógico | Notas |
|----------|---------|-----------------|-------|
| Criar customer | Outbound | `POST /v1/customers` | Mapeia `organizacao.id_externo` |
| Criar assinatura | Outbound | `POST /v1/subscriptions` | Mapeia `assinatura.id_externo` |
| Cancelar assinatura | Outbound | `DELETE /v1/subscriptions/{id}` | Soft-cancel no gateway; reativação cria nova |
| Consultar estado | Outbound | `GET /v1/subscriptions/{id}` | Usado pelo job de reconciliação (PF-X-08) |
| Webhook de eventos | Inbound | `POST /webhooks/pagamento` (rota nossa) | Eventos: `invoice.paid`, `invoice.payment_failed`, `subscription.canceled`, `subscription.expired` |

### 4.3 Autenticação

- **Outbound:** API key (secret) no header `Authorization: Bearer {secret}`; chave armazenada em cofre (variável de ambiente / secrets manager), referenciada por ID em E-25, **nunca em banco nem em log**.
- **Inbound (webhook):** assinatura HMAC do payload (header `Stripe-Signature` ou equivalente) verificada server-side com a chave de webhook (distinta da API key). Rejeição imediata (HTTP 401) se a assinatura não validar — nenhuma ação de negócio é tomada antes da verificação.
- **Rota do webhook:** HTTPS only; IP allowlist do provedor quando disponível.

### 4.4 Fluxo de dados — entrada e saída

**Saída (nosso sistema → gateway):**

1. `FP-01 (Onboarding)`: `admin_plataforma` cria Organização → aplicação cria customer no gateway → grava `organizacao.id_externo` (E-24 loga requisição/resposta).
2. `FP-02`: aplicação cria assinatura no gateway → grava `assinatura.id_externo` e `assinatura.status = 'ativa'` atomicamente (transação DB + chamada API; ver Seção 4.6 sobre consistência).
3. Job de reconciliação (PF-X-08): a cada 1h consulta `GET /v1/subscriptions/{id}` para todas as assinaturas `ativas`/`suspensas` e compara com E-02.

**Entrada (gateway → nosso sistema):**

1. Webhook `invoice.paid` → job idempotente (T-7) mantém `assinatura.status = 'ativa'` e `organizacao.status = 'ativo'`.
2. Webhook `invoice.payment_failed` → job inicia janela de carência (parâmetro de 6.1.3); após carência, `assinatura.status = 'suspensa'`, `organizacao.status = 'suspenso'` (PE de R01, PF-FS-24).
3. Webhook `subscription.canceled` / `subscription.expired` → `assinatura.status = 'cancelada'`/`expirada`; dados preservados para auditoria (T-6).

### 4.5 Criticidade

- **Crítica.** Sem INT-01 não há cobrança; sem cobrança o tenant não existe operacionalmente (I-02). Webhook perdido causa suspensão indevida (PF-X-08, sev A) ou tenant ativo sem pagamento (perda de receita).

### 4.6 Riscos e mitigações

| Risco | Severidade | Mitigação |
|-------|------------|-----------|
| Webhook perdido ou fora de ordem → estado divergente (PF-X-08) | A | Job de reconciliação periódica (1h); webhook idempotente por `correlation_id` (T-7); NS-1 ao `admin_tenant` em mudança de estado |
| Checkout falha → tenant não criado (PF-FP-01) | M | Aplicação recebe erro síncrono do gateway; retry de cartão pelo cliente; não há criação parcial de tenant (I-02) |
| API key vazada | C | Rotação periódica; cofre; redação em E-24; sem echo em erro |
| Webhook fraudulento (falsa notificação) | A | Verificação HMAC obrigatória; IP allowlist; rejeição 401 antes de qualquer mutação |
| Divergência DB↔gateway na criação (FP-02 atomicidade) | A | Padrão: criar assinatura no gateway, persistir `id_externo` em transação; se DB falhar após API, job de reconciliação detecta assinatura órfã e cancela no gateway |
| Latência do gateway degrada checkout | M | Timeout de 10s; fallback de mensagem clara; não bloqueia outras operações |
| Provedor indisponível (outage) | A | Circuit breaker; job de reconciliação absorve eventos atrasados; NS-1 ao `admin_plataforma` |

---

## 5. Detalhamento — INT-02 Provedor de e-mail transacional

### 5.1 Sistema externo

- **E-25:** `email_transacional`, `status = 'ativo'`.
- **Produto de referência:** Postmark, AWS SES ou SendGrid.
- **Função:** entrega de notificações (E-22) no canal e-mail; único canal externo de notificação no MVP (in-app é o primário).

### 5.2 Endpoints (API)

| Operação | Direção | Endpoint lógico | Notas |
|----------|---------|-----------------|-------|
| Enviar e-mail transacional | Outbound | `POST /v1/email` (ou `SendEmail`) | Body: `from`, `to`, `template_id`, `variables` |
| Webhook de bounce/spam | Inbound | `POST /webhooks/email` (rota nossa) | Eventos: `bounce`, `spam`, `delivered` |
| Consultar reputação do domínio | Outbound | `GET /v1/senders` | Monitoramento de deliverability (opcional, Sprint 1.4) |

### 5.3 Autenticação

- **Outbound:** API token no header (ex.: `X-Postmark-Server-Token`); chave em cofre, referenciada por ID em E-25.
- **Inbound (webhook):** assinatura HMAC ou Basic Auth com credencial de webhook dedicada; IP allowlist do provedor.
- **Domínio:** SPF/DKIM/DMARC configurados no DNS do domínio remetente; verificável no provedor.

### 5.4 Fluxo de dados — entrada e saída

**Saída (nosso sistema → provedor):**

1. Fluxo dispara Notificação (E-22) → grava em `notificacao` + `rel_notificacao_usuario` (R24) com `canal = 'in_app'` **sempre** (canal primário).
2. Se usuário tem `preferencia_email = true`, job de despacho (assíncrono) lê não-enviadas e chama `POST /v1/email` com `correlation_id` no header customizado ou metadata.
3. Sucesso (HTTP 2xx) → `notificacao.enviada_em` preenchido; E-24 loga `http_status`, `latencia_ms`.
4. Falha transitória (5xx/timeout) → retry com backoff (3x); após 3 falhas, `notificacao.status = 'falha_envio'` e mantém in-app; NS-1 ao `admin_tenant` sugerindo atualizar e-mail (PF-FS-19).

**Entrada (provedor → nosso sistema):**

1. Webhook `bounce` → marca `usuario.email_valido = false`; próxima notificação pula e-mail, mantém in-app.
2. KPI de bounce por NS/N monitorado em 1.4; bounce rate > 5% aciona alerta de reputação.

### 5.5 Criticidade

- **Alta.** E-mail é o único canal externo; sua indisponibilidade **não bloqueia operação esportiva** (in-app permanece), mas degrada comunicação com usuários offline e podem ocorrer atrasos em alertas de inadimplência (PF-FS-24).

### 5.6 Riscos e mitigações

| Risco | Severidade | Mitigação |
|-------|------------|-----------|
| Bounce de caixa cheia/e-mail inválido (PF-FS-19) | M | Retry 3x; fallback in-app garantido; NS-1 ao `admin_tenant`; marca `email_valido = false` via webhook |
| Reputação de domínio degradada | A | DKIM/SPF/DMARC; KPI de bounce; warm-up de domínio; limite de taxa configurado |
| Webhook de bounce perdido | M | Reconciliação diária consultando relatório de bounce do provedor; idempotência por `correlation_id` |
| E-mail sensível vazado em log | C | Redação de `to`/body em E-24; template server-side, apenas variáveis no payload |
| Template desatualizado | B | Versionamento de template; teste em sandbox; fallback para template mínimo |
| Provedor indisponível | M | Circuit breaker; fila de despacho persiste; retry absorve outage curta |

---

## 6. Detalhamento — INT-03 Armazenamento de objetos (S3-compatible)

### 6.1 Sistema externo

- **E-25:** `object_storage`, `status = 'ativo'`.
- **Produto de referência:** AWS S3, Cloudflare R2 ou MinIO (self-host).
- **Função:** persistência de Anexos (E-18) de Propostas/Negociações e de arquivos temporários de importação (INT-04) e exportação (INT-05).

### 6.2 Endpoints (API)

| Operação | Direção | Endpoint lógico | Notas |
|----------|---------|-----------------|-------|
| PUT de objeto | Outbound | `PUT /{bucket}/{key}` | Key prefixa com `tenant_id/` (tenant boundary) |
| GET de objeto | Outbound | `GET /{bucket}/{key}` | Download via URL pré-assinada |
| URL pré-assinada (upload) | Outbound | `POST /v1/presign` (ou SDK) | Cliente faz upload direto, sem passar pelo app |
| URL pré-assinada (download) | Outbound | idem | TTL de 15 min |
| DELETE de objeto | Outbound | `DELETE /{bucket}/{key}` | Soft-delete no DB; objeto expira via lifecycle |
| Lifecycle / expiração | Config | Regra de bucket | Arquivos temporários de import/export: 7 dias; anexos: permanente (T-6) |

### 6.3 Autenticação

- **Outbound (server):** credenciais IAM / access key + secret em cofre; SDK assina requisições (SigV4 ou equivalente).
- **Cliente (browser):** URL pré-assinada com TTL curto (15 min); sem credencial permanente no cliente.
- **Bucket policy:** negar público; acesso somente via pré-assinada; criptografia em repouso (SSE) e em trânsito (TLS).

### 6.4 Fluxo de dados — entrada e saída

**Entrada (upload de anexo — FS-04 Negociação):**

1. `gestor_clube` seleciona arquivo no browser → app gera URL pré-assinada de upload → browser PUT direto no bucket.
2. App registra `anexo` (E-18) com `bucket`, `key`, `tamanho`, `hash`, `tenant_id`; FS-04 exige ≥ 1 anexo em proposta aceita (R20, PF-FS-12).
3. E-24 loga a emissão da pré-assinada (não o conteúdo).

**Saída (download):**

1. Usuário solicita download → app gera URL pré-assinada de GET (15 min) → browser baixa.
2. Auditoria (E-23) registra o ato de download (PF-FS-30).

**Ciclo de vida:**

- Anexos de negociação cancelada: **preservados** (PF-FS-09, T-6) — nunca excluídos.
- Arquivos de importação (INT-04): expiram em 7 dias via lifecycle; metadados em E-24 persistem.
- Arquivos de exportação (INT-05): expiram em 7 dias; registro em E-24 + auditoria persiste.

### 6.5 Criticidade

- **Alta.** Sem INT-03 não há anexos de proposta (bloqueia FS-04) nem import/export em volume. Indisponibilidade degrada mas não corrompe dados (objetos persistem).

### 6.6 Riscos e mitigações

| Risco | Severidade | Mitigação |
|-------|------------|-----------|
| Cross-tenant access via key malformada | C | Prefixo `tenant_id/` obrigatório; validação server-side antes de pré-assinar; RLS no DB espelha boundary |
| Objeto órfão (anexo sem row no DB) | M | Job de reconciliação compara bucket com E-18; alerta em 1.4 |
| URL pré-assinada vazada | M | TTL 15 min; escopo mínimo (uma key); sem credencial permanente |
| Custo de armazenamento explodir | B | Lifecycle de expiração; monitoramento de tamanho; quota por tenant |
| Provedor indisponível | A | Retry com backoff; circuit breaker; uploads em andamento falham graciosamente (PF-FS-13) |
| Anexo malicioso (vírus) | A | Validação de tipo MIME e hash; limite de tamanho; antivírus opcional em futuro (F-XX) |
| Perda de objeto antes do lifecycle | C | Versionamento de bucket; replicação cross-region para anexos permanentes |

---

## 7. Detalhamento — INT-04 Importação de arquivos (ingresso)

### 7.1 Sistema externo

- **E-25:** `ingestao_arquivos`, `status = 'ativo'` (representa a fronteira de entrada, não um provedor específico; o provedor físico é INT-03 para armazenamento).
- **Função:** carga em lote de entidades (Clube, Pessoa, Contrato, Equipe, Atleta, Inscrição) via CSV/XLSX pelo `admin_tenant` (FS-05).

### 7.2 Endpoints (API)

| Operação | Direção | Endpoint lógico | Notas |
|----------|---------|-----------------|-------|
| Upload de arquivo | Inbound | `POST /api/imports` (nossa rota) | Multipart; valida tipo/tamanho; grava em INT-03 |
| Consultar status do lote | Inbound | `GET /api/imports/{correlation_id}` | Retorna `N_aceitas`/`N_rejeitadas` + relatório |
| Download do relatório de falhas | Inbound | `GET /api/imports/{correlation_id}/report` | CSV com linha/campo/motivo (task 2.4.4) |

### 7.3 Autenticação

- **Inbound:** sessão do `admin_tenant` (RBAC + RLS, I-01); não há credencial externa — a fronteira é o próprio usuário autenticado.
- **Validação de arquivo:** tipo MIME (CSV/XLSX), tamanho máximo (ex.: 10 MB), encoding (UTF-8), delimitador; rejeição síncrona se inválido.

### 7.4 Fluxo de dados — entrada e saída

**Entrada (cliente → nosso sistema):**

1. `admin_tenant` faz upload via `POST /api/imports` → app valida cabeçalho e tipos → grava arquivo em INT-03 → cria registro em E-24 com `tipo_operacao = 'importacao'`, `correlation_id` único.
2. Job assíncrono (worker) lê o arquivo em **batches de 100 linhas** (decisão consolidada de 0.4.3, Seção 10): cada batch é uma transação; linhas inválidas do batch rejeitam só o batch, não o arquivo inteiro.
3. Por linha: valida invariantes (I-02 cotas, I-03 contrato ativo único, I-10 tenant_id); valida regras transversais; aceita ou rejeita com motivo/campo.
4. Ao final: `N_aceitas`/`N_rejeitadas`; relatório de falhas por linha (task 2.4.4); NS-6 ao usuário (E-22).
5. Idempotência: `correlation_id` do lote UNIQUE em E-24 (T-7) — reenvio do mesmo arquivo corrigido gera novo `correlation_id`.

**Saída (nosso sistema → cliente):**

1. Cliente consulta status ou recebe NS-6 in-app.
2. Download do relatório de falhas via INT-03 (URL pré-assinada, TTL 15 min).

### 7.5 Criticidade

- **Média.** Importação é facilidade de onboarding/volume; indisponibilidade não bloqueia operação esportiva (entrada manual via FP-03/FP-04 permanece). Falha de validação não corrompe dados (batches transacionais).

### 7.6 Riscos e mitigações

| Risco | Severidade | Mitigação |
|-------|------------|-----------|
| Arquivo grande trava worker (PF-FS-13) | M | Commit por batch (100 linhas); worker isolado; timeout por batch |
| Linha inválida rejeita arquivo inteiro | A | Decisão consolidada: só o batch rejeita; relatório por linha (0.4.3) |
| Importação duplicada (reenvio) | M | `correlation_id` UNIQUE (T-7); usuário gera novo lote corrigido |
| Encoding/delimitador errado | B | Validação síncrona no upload; mensagem clara |
| Importação viola I-03 (contrato ativo duplicado) | A | Validação por linha na transação do batch; rejeita linha; auditoria |
| Vazamento cross-tenant via arquivo | C | RLS no INSERT; `tenant_id` da sessão propagado por trigger (I-10) |
| Worker cai no meio do lote | M | `correlation_id` permite retomada; batches já comitados não são reprocessados |

---

## 8. Detalhamento — INT-05 Exportação de arquivos (egresso)

### 8.1 Sistema externo

- **E-25:** `egresso_arquivos`, `status = 'ativo'` (fronteira de saída; provedor físico é INT-03).
- **Função:** geração de relatórios pré-definidos (listagens, classificações, partidas, auditoria) em CSV/XLSX/PDF pelo usuário (FS-06).

### 8.2 Endpoints (API)

| Operação | Direção | Endpoint lógico | Notas |
|----------|---------|-----------------|-------|
| Solicitar exportação | Inbound | `POST /api/exports` (nossa rota) | Body: `entidade`, `filtros`, `formato`; retorna `correlation_id` |
| Consultar status | Inbound | `GET /api/exports/{correlation_id}` | `pronto`/`gerando`/`falhou` |
| Download do arquivo | Inbound | `GET /api/exports/{correlation_id}/download` | Redireciona para URL pré-assinada de INT-03 |

### 8.3 Autenticação

- **Inbound:** sessão do usuário autenticado; RBAC define quais entidades/filtros cada papel pode exportar (`gestor_clube` exporta seu clube; `gestor_competicao` exporta sua edição; `admin_tenant` exporta todo o tenant; `admin_plataforma` exporta qualquer tenant).
- **RLS:** a consulta que gera o arquivo é filtrada por `tenant_id` da sessão (I-01).

### 8.4 Fluxo de dados — entrada e saída

**Entrada (cliente → nosso sistema):**

1. Usuário solicita exportação via `POST /api/exports` → app valida permissões e filtros → grava solicitação com `correlation_id` único em E-24 (`tipo_operacao = 'exportacao'`).
2. Job assíncrono executa consulta (RLS), monta o arquivo no formato solicitado, faz PUT em INT-03, registra `N_linhas`/`formato`/`key` em E-24.
3. Auditoria (E-23) registra o ato de exportação (PF-FS-30); exportações já baixadas **não são invalidadas** por recálculo retroativo (decisão 0.4.3 Seção 11 — não há como revogar arquivo externo).

**Saída (nosso sistema → cliente):**

1. NS-6 ao usuário notifica `pronto` (E-22, in-app).
2. Usuário baixa via URL pré-assinada (INT-03, TTL 15 min).
3. Arquivo expira em 7 dias (lifecycle de INT-03); metadados em E-24 + auditoria persistem.

### 8.5 Criticidade

- **Média.** Indisponibilidade degrada prestação de contas/auditoria externa, mas não bloqueia operação esportiva. Não é BI self-service (N-25 respeitado) — somente relatórios pré-definidos.

### 8.6 Riscos e mitigações

| Risco | Severidade | Mitigação |
|-------|------------|-----------|
| Exportação volumosa trava DB | M | Job isolado; cursor/paginação; timeout; quota por tenant |
| Exportação cross-tenant (RBAC mal configurado) | C | RLS na consulta; validação de papel; auditoria do ato |
| Vazamento de dado sensível via arquivo externo | A | Escopo mínimo por papel; auditoria registra; não há revogação pós-download (decisão consolidada) |
| Arquivo gerado com dado desatualizado (recálculo retroativo) | B | Auditoria registra reabertura; exportações baixadas mantidas (0.4.3) |
| Format/encoding inconsistente | B | Templates versionados; validação pós-geração |
| Provedor INT-03 indisponível | M | Retry; NS-6 de falha; usuário pode reagendar |

---

## 9. Matriz de criticidade consolidada

| ID | Criticidade | Impacto se indisponível | Tempo máximo tolerável de indisponibilidade |
|----|-------------|--------------------------|---------------------------------------------|
| INT-01 | Crítica | Sem cobrança; tenant não criado; suspensão indevida | < 1h (webhook) / < 5 min (checkout) |
| INT-02 | Alta | Sem e-mail; in-app permanece; atraso em alertas de inadimplência | < 4h |
| INT-03 | Alta | Sem anexos (bloqueia FS-04); sem import/export em volume | < 2h |
| INT-04 | Média | Sem importação em lote; entrada manual permanece | < 8h (janela operacional) |
| INT-05 | Média | Sem exportação; degrada auditoria externa | < 8h (janela operacional) |

---

## 10. Matriz de riscos consolidada

Avaliação qualitativa (Severidade × Probabilidade) para priorização de testes (task 6.3) e alertas (task 1.4). Probabilidade: A (alta), M (média), B (baixa).

| Sev \ Prob | A | M | B |
|-------------|---|---|---|
| **C (Crítica)** | INT-01 webhook fraudulento (se mal implementado); INT-03 cross-tenant | INT-01 API key vazada; INT-04 vazamento cross-tenant; INT-05 RBAC mal configurado | — |
| **A (Alta)** | INT-01 webhook perdido (PF-X-08); INT-02 reputação degradada | INT-01 divergência DB↔gateway; INT-01 outage; INT-03 anexo malicioso; INT-05 vazamento de dado | INT-03 perda de objeto |
| **M (Média)** | INT-01 checkout falha (PF-FP-01); INT-02 bounce (PF-FS-19) | INT-03 objeto órfão; INT-04 worker cai; INT-05 DB trava; INT-02 webhook bounce perdido | INT-03 custo; INT-05 dado desatualizado; INT-02 template |
| **B (Baixa)** | — | INT-04 encoding | INT-05 encoding |

**Prioridade de testes (task 6.3.3 — Testes de contrato):** INT-01 (webhook HMAC, idempotência, reconciliação) e INT-03 (prefixo `tenant_id`, pré-assinada) são **obrigatórios** na Sprint 6. INT-02 (bounce → `email_valido`) e INT-04 (batch transacional) são testes de integração. INT-05 entra em cobertura padrão.

---

## 11. Fluxo de dados consolidado (entrada/saída)

### 11.1 Entrada (sistemas externos → nosso sistema)

| Origem | Via | Payload | Destino interno | Idempotência |
|--------|-----|---------|-----------------|--------------|
| Gateway de pagamento | Webhook HTTPS + HMAC | Evento de ciclo de vida (JSON) | Job → E-02 Assinatura, E-01 Organização | `correlation_id` + `evento_id` UNIQUE |
| Provedor de e-mail | Webhook HTTPS + HMAC | Evento de bounce/spam (JSON) | Job → E-06 Usuário (`email_valido`) | `correlation_id` + `evento_id` UNIQUE |
| Cliente (`admin_tenant`) | Upload multipart | CSV/XLSX | INT-03 → worker → E-07 a E-15 | `correlation_id` do lote UNIQUE |
| Cliente (qualquer papel) | Solicitação HTTP | Filtros + formato | Job → INT-03 → E-24 | `correlation_id` da exportação UNIQUE |

### 11.2 Saída (nosso sistema → sistemas externos)

| Destino | Via | Payload | Origem interna | Idempotência |
|---------|-----|---------|-----------------|--------------|
| Gateway de pagamento | API REST + Bearer | Customer/subscription (JSON) | App (onboarding, FP-01/FP-02) | `idempotency_key` do provedor + `correlation_id` |
| Provedor de e-mail | API REST + token | E-mail transacional (JSON) | Job de despacho (FS-07) | `correlation_id` no metadata |
| Armazenamento de objetos | SDK assinado | Bytes do arquivo | App (anexo) / job (import/export) | Hash do objeto; sobrescrita só via lifecycle |
| Cliente (download) | URL pré-assinada | Bytes do arquivo | INT-03 → browser | TTL 15 min; sem credencial permanente |

### 11.3 Registro (E-24)

Toda operação das tabelas acima grava em E-24 (R27) com no mínimo: `sistema_externo_id`, `tipo_operacao`, `http_status`, `latencia_ms`, `correlation_id`, payload redigido (segredos e PII mascarados), `tenant_id` quando aplicável. E-24 é append-only e sobrevive à exclusão da entidade (túmulo do dado, 0.3.3).

---

## 12. Contratos de SLA, webhook e retry (consolidação)

| Integração | SLA alvo | Webhook | Retry | Reconciliação |
|------------|----------|---------|-------|---------------|
| INT-01 | 99.9% provedor; checkout < 10s | HMAC + IP allowlist; eventos `invoice.paid`/`payment_failed`/`canceled`/`expired` | 3x backoff exp. (1s/4s/16s) | Job 1h consulta `GET /subscriptions` (PF-X-08) |
| INT-02 | 99.5% provedor; entrega < 60s | HMAC; eventos `bounce`/`spam`/`delivered` | 3x backoff exp. (1s/4s/16s) | Relatório diário de bounce do provedor |
| INT-03 | 99.9% provedor | — (lifecycle de bucket) | 3x backoff exp. (1s/4s/16s) | Job diário compara bucket com E-18 |
| INT-04 | N/A (fronteira interna) | — | N/A (job próprio) | `correlation_id` permite retomada de batch |
| INT-05 | N/A (fronteira interna) | — | N/A (job próprio) | `correlation_id` permite reprocessamento |

**Política comum:**

- Após 3 retries falhos: evento vai para a **fila de exceções** (R27 PE, 0.3.3) e NS-1 ao `admin_plataforma` (E-22).
- Webhooks rejeitados (HMAC inválido) retornam 401 e **não** geram retry no provedor; são métrica de segurança em 1.4.
- Circuit breaker por integração: 5 falhas consecutivas em 1 min abrem o circuito; half-open após 30s.

---

## 13. Handoff para as próximas tasks

### 13.1 Subtask imediata (0.6 — Consolidar Sprint 0)

- **0.6.1 — Resumir decisões tomadas:** as 5 integrações (INT-01 a INT-05) e os contratos de SLA/webhook/retry da Seção 12 entram no resumo executivo da Sprint 0.
- **0.6.2 — Registrar pendências abertas:** itens 13.3 abaixo.
- **0.6.3 — Preparar handoff para Sprint 1:** INT-01 (checkout) e INT-02 (e-mail) são necessárias já na Sprint 1 (autenticação/assinatura e notificações); INT-03 na Sprint 2 (anexos) e Sprint 4 (formulários com upload).

### 13.2 Tasks downstream

- **1.4 — Observabilidade mínima:** os KPIs por integração (latência, bounce rate, webhook HMAC rejeitado, divergência DB↔gateway) alimentam logging/erros/auditoria da Sprint 1.
- **2.4 — Importação e exportação:** INT-04 e INT-05 formalizam formatos, validação, conflitos e relatório de falhas previstos nas subtasks 2.4.1 a 2.4.4.
- **5.1 — Integrações externas (Sprint 5):** esta subtask é o **contrato de entrada** para 5.1.1 (sistemas externos), 5.1.2 (autenticação) e 5.1.3 (entrada e saída de dados, `needs_review`). A task 5.1 Implementa os contratos; 0.5.3 os especifica.
- **6.2 — Auditoria:** E-24 (Log de integração) é auditável e append-only (PF-FS-30/31, PF-X-05); retenção definida em 6.2.3.
- **6.3.3 — Testes de contrato:** INT-01 e INT-03 são obrigatórios (Seção 10).

### 13.3 Decisões consolidadas

1. **5 integrações externas** no MVP (INT-01 a INT-05); demais fronteiras são não-objetivos (N-09/N-11, N-18 a N-20, N-24 a N-26).
2. **Toda integração é idempotente** por `correlation_id` + `sistema_externo_id` UNIQUE (T-7, IF-07).
3. **Toda chamada é logada** em E-24 com payload redigido (R27); E-24 é append-only (I-09).
4. **Estado de verdade é interno** — webhook é evento, nunca gravação direta; job idempotente aplica a transação (PF-X-08).
5. **Webhooks validam HMAC** antes de qualquer mutação; rejeição 401 não gera retry.
6. **Tenant boundary em objeto:** INT-03 prefixa keys com `tenant_id/`; INT-04/INT-05 filtram por RLS.
7. **Retry 3x com backoff exponencial** + circuit breaker + fila de exceções (R27 PE).

### 13.4 Pendências encaminhadas (não resolvidas aqui)

- **Escolha do provedor de pagamento** (Stripe vs Mercado Pago) → decisão de Sprint 5 (5.1.1); o contrato aqui é agnóstico.
- **Escolha do provedor de e-mail** (Postmark vs SES vs SendGrid) → Sprint 5 (5.1.1).
- **Escolha do object storage** (S3 vs R2 vs MinIO) → Sprint 5 (5.1.1) com viés a R2/MinIO para custo.
- **Período de carência** entre `payment_failed` e `suspensa` → 6.1.3 (Regras de Competição / Assinatura).
- **Política de retenção de E-24** (Log de integração) → 6.2.3.
- **Antivírus de anexos** → futuro (F-XX), fora do MVP.
- **IP allowlist dos provedores** → configurar em Sprint 5 com dados do provedor escolhido.
- **Rate limit por tenant em import/export** → definir em 2.4 (Importação e exportação) com base em cotas de assinatura (I-02).

---

## 14. Resumo para o orquestrador

- **5 integrações externas** mapeadas (INT-01 a INT-05) com sistema externo (E-25), endpoints, autenticação, fluxo de dados entrada/saída, criticidade e riscos.
- **Matriz de criticidade** (Seção 9): 1 crítica, 2 altas, 2 médias.
- **Matriz de riscos** (Seção 10) alimenta testes de contrato (6.3.3) e observabilidade (1.4).
- **Contratos de SLA/webhook/retry** consolidados na Seção 12; todos idempotentes por `correlation_id` (T-7, IF-07); todos logados em E-24 (R27).
- **Fronteiras respeitadas:** 9 não-objetivos confirmados fora do MVP (N-09/N-11, N-18 a N-20, N-24 a N-26).
- **Handoff para Sprint 5 (task 5.1)** completo; pendências de escolha de provedor encaminhadas.
- `needs_review: true` mantido — escolha de provedores e parâmetros de SLA exigem validação humana antes da implementação.
