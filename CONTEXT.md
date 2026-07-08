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
