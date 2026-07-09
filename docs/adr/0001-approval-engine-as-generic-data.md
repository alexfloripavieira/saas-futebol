# Approval engine is a generic, multi-step, data-driven module

## Status

accepted

## Context

The platform needs approval gates over heterogeneous targets (contracts, transfers, match reopening, edition registration/close). Sprint 0 framed this as "aprovações como dados" — no workflow logic hardcoded per business process. The pre-existing `ApprovalFlow`/`ApprovalRequest` models were a stub: single-status requests, stringly-typed target references, and no side-effect mechanism.

## Decision

Build the approval engine as a football-agnostic module with three entities — **Fluxo de Aprovação** (template), **Solicitação** (in-flight case), **Decisão** (per-step ruling) — with these commitments:

1. **Multi-step-capable from day one.** A Fluxo has one or more ordered Etapas; a Solicitação accumulates one Decisão per Etapa and resolves only when all required Etapas are `aprovada`. MVP seeds every flow single-step except transfer (sporting → legal). Chosen over single-step-only to avoid a painful future migration that would split a history-bearing status column into per-step records.

2. **Polymorphic target via Django `GenericForeignKey`**, matching the existing `AuditLog` precedent (not the stringly-typed `target_model`/`target_object_id` pair), guarded by an allow-list of approvable models validated in `clean()`.

3. **Side-effects via a dispatch registry.** On final approval the engine, inside the same transaction, records the final Decisão and invokes an `on_approved` handler registered per target type (`contrato → activate_contract`, etc.). A rejecting Decisão is **terminal** — it resolves the whole Solicitação as `rejeitada` and invokes the target's `on_rejected` handler (also in the same transaction) to set the target's return state; a retry is a brand-new Solicitação that re-runs every Etapa from the first. Chosen over Django signals (which undermine the required atomicity and auditability) and over a method-on-target (which would leak approval semantics into every domain model). The registry is the single place a new gate is defined: its target type, the proponent role and creation trigger that auto-opens the Solicitação, the required approver role and evidence per Etapa, the `on_approved` effect, and the `on_rejected` return.

Creating an approval-gated target auto-opens its Solicitação in the same action, so a gated target is always either pending or resolved — never an orphan draft. A still-pending Solicitação may be cancelled by its requester or an `admin_tenant`, with no target side-effect. Approvers act by role per Etapa; a requester may never decide their own Solicitação (separation of duties, enforced in `clean()`).

## Consequences

- The engine stays a deep module knowing nothing about football; each domain owns its own effect handler and is independently testable.
- The atomic "approval mirror" boundary is explicit and lives in one place.
- GenericForeignKey gives no DB-level cascade; referential integrity of the target is enforced only at the application layer (allow-list + handler lookups).
