# SaaS do Futebol

Ubiquitous language for the football-operations platform. Terms are canonical across code, UI, and docs; the codebase is pt-br, so the canonical form of each term is Portuguese.

## Approvals

**Fluxo de Aprovação** (ApprovalFlow):
A named, per-tenant template describing how a given kind of change gets approved — which ordered Etapas it has and what it targets. It is configuration, not an in-flight case.
_Avoid_: workflow, pipeline, gate (a "gate" is the *use* of a flow at a point in a business process, not the flow itself)

**Etapa** (Step):
One ordered stage within a Fluxo de Aprovação. A flow has one or more Etapas; the MVP seeds every flow with a single Etapa except transfer, which may have two (sporting → legal).
_Avoid_: stage, phase (Fase is reserved for the competition tree — `CompetitionPhase`)

**Solicitação** (ApprovalRequest):
A single in-flight approval case: one target object moving through one Fluxo de Aprovação. It accumulates Decisões and is resolved only when its flow's Etapas are all satisfied.
_Avoid_: request (bare), ticket

**Decisão** (Decision):
A record of one approver's ruling on one Etapa of one Solicitação — who ruled, when, and the outcome (`aprovada` or `rejeitada`). A Solicitação has one Decisão per Etapa acted on. Distinct from the Solicitação itself, which is the case, not the ruling.
_Avoid_: approval (a Decisão may be a rejection, so "approval" is too narrow for the entity); deferimento/deferida (the outcome verb is `aprovar`/`aprovada`, not `deferir`)

**Evidência** (Evidence):
A document or note attached to a target to justify approving it (e.g. transfer paperwork). A Etapa may require ≥1 Evidência before its Decisão can be cast; most MVP flows require none.
_Avoid_: attachment, anexo (use Evidência when the purpose is to justify an approval)

## Commercial access and tenant setup

**Tenant**:
The club workspace sold to the customer. It carries its own data, users, branding, and enabled modules.
_Avoid_: account, organization (use Tenant for the workspace itself)

**Módulo Contratado** (Contracted Module):
A feature area enabled for a Tenant based on what that club purchased. The sidebar should only show contracted modules.
_Avoid_: feature flag (too technical), package (too vague)

**Branding do Tenant** (Tenant Branding):
The visual identity customized per Tenant — logo, colors, symbols, and the name shown in the app and institutional screen.
_Avoid_: theme (too generic if the intent is tenant identity)

**Tela Institucional** (Institutional Landing):
The public-facing screen shown when a visitor or user has no active Tenant access. It presents login and marketing content instead of the operational app.
_Avoid_: splash screen, home page (unless that is the exact public marketing entry)

**Onboarding do Tenant**:
The first configuration flow shown to the initial tenant admin after login. It creates the Tenant and configures the initial access, modules, and branding.
_Avoid_: setup wizard (acceptable only in technical docs)

## Inteligência esportiva

**Comissão Técnica Digital**:
Conjunto coordenado de Agentes Especialistas que analisa o mesmo contexto de uma partida e produz recomendações complementares para a comissão humana.
_Avoid_: chatbot, IA genérica, vários bots independentes

**Agente Especialista**:
Integrante da Comissão Técnica Digital com responsabilidade delimitada, como análise tática, preparação física, defesa, ataque, observação ou bola parada.
_Avoid_: persona (persona descreve tom; o Agente Especialista possui responsabilidade e limites)

**Dossiê da Partida**:
Retrato versionado dos dados disponíveis sobre nosso time, adversário, ambiente e disponibilidade no momento de uma análise.
_Avoid_: prompt, contexto solto, relatório do adversário

**Recomendação Tática**:
Proposta explicável de escalação, estrutura ou comportamento, acompanhada de evidências, confiança e restrições.
_Avoid_: palpite, resposta da IA

**Plano de Jogo**:
Conjunto escolhido de Recomendações Táticas para uma partida, incluindo formação, escalação, comportamentos por fase e cenários alternativos.
_Avoid_: estratégia (genérico), escalação (é apenas uma parte do plano)

**Fonte de Dados Esportivos**:
Origem estruturada de partidas, eventos, métricas ou tracking, com proveniência, licença, qualidade e validade conhecidas.
_Avoid_: Fonte de Conhecimento (reservada a documentos e conteúdo textual)
