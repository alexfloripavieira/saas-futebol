# Sprint 3.3 — Aprovações: implementation plan

Implements the approval engine per [ADR-0001](../adr/0001-approval-engine-as-generic-data.md) and the glossary in [CONTEXT.md](../../CONTEXT.md). Terms below are canonical (Fluxo de Aprovação, Etapa, Solicitação, Decisão, Evidência).

**Precondition / assumption:** no production data exists (dev is orchestrator-driven; `ApprovalFlow`/`ApprovalRequest` ship only in `0001_initial`). We therefore **rewrite** these models and add a single new migration rather than writing a data migration. Confirm before running if any tenant DB has real rows.

**Out of scope (deferred):** Evidência file-upload UI (admin/API attach only this sprint); decision notifications (NS-2/NS-5 — belong to the Notification subsystem, a later task).

---

## Model changes (`src/futebol/models.py`)

All new models inherit `TenantScopedModel`. Follow existing conventions: per-tenant uniqueness constraints, `full_clean()` on save (inherited), pt-br `TextChoices` labels, and `tenant_bound_fields` for every cross-model FK.

### `ApprovalFlow` (Fluxo de Aprovação) — revise
Keep `code`, `name`, `active`. **Remove** the free-text `target_model` string; the target type is fixed by the gate registry entry, not stored free-form. Add:
- `target_kind` — `CharField(choices=...)` drawn from the **allow-list** (see registry): `contrato`, `negociacao`, `partida`, `escalacao`, `inscricao`, `transferencia`.
- Uniqueness: keep `uniq_approval_flow_code_per_tenant`; add `UniqueConstraint(tenant, target_kind)` — one active flow per target kind per tenant (MVP: a target kind maps to exactly one flow).

### `ApprovalFlowStep` (Etapa) — new
- `flow` FK → `ApprovalFlow` (`related_name='steps'`), `tenant_bound_fields = ('flow',)`
- `order` — `PositiveSmallIntegerField`
- `required_role` — `CharField(choices=TenantMembership.Role.choices)` — the role permitted to decide this Etapa
- `requires_evidence` — `BooleanField(default=False)`
- Constraints: `UniqueConstraint(tenant, flow, order)`; `ordering = ['flow', 'order']`

### `ApprovalRequest` (Solicitação) — revise
- **Remove** `target_model` + `target_object_id` (stringly-typed) and the single `status`/`decided_at` decision fields.
- Add GFK exactly like `AuditLog`: `content_type` FK → `ContentType`, `object_id` `CharField`, `content_object = GenericForeignKey(...)`.
- Keep `flow`, `requested_by`, `reason`, `requested_at`.
- `status` (of the *case*, not a step): `OPEN`/`aberta`, `APPROVED`/`aprovada`, `REJECTED`/`rejeitada`, `CANCELLED`/`cancelada`. Resolved by the engine, never set directly.
- `resolved_at` — `DateTimeField(null=True)`.
- `clean()`: validate `content_type.model_class()` is in the allow-list and matches `flow.target_kind`.

### `ApprovalDecision` (Decisão) — new
- `request` FK → `ApprovalRequest` (`related_name='decisions'`)
- `step` FK → `ApprovalFlowStep`
- `decided_by` FK → `AUTH_USER_MODEL`
- `outcome` — `CharField(choices=[('aprovada',...),('rejeitada',...)])`
- `decided_at` — `DateTimeField(auto_now_add=True)`
- `note` — `TextField(blank=True)`
- `tenant_bound_fields = ('request', 'step')`
- Constraint: `UniqueConstraint(request, step)` — one Decisão per Etapa per case.
- `clean()` enforces (see §Invariants): self-approval ban, role match, step ordering, evidence gate.

### `Evidencia` (Evidência) — new
- GFK target (`content_type`/`object_id`/`content_object`)
- `file` (or `url`) + `note` + `uploaded_by` FK
- Referenced by the evidence-gate check when `step.requires_evidence`.

---

## Gate registry (`src/futebol/services/approvals.py` — new)

The single place a gate is defined (ADR-0001). A plain module-level registry keyed by `target_kind`:

```python
@dataclass
class GateSpec:
    target_kind: str
    target_model: type[models.Model]     # for the allow-list
    proponent_role: str                  # who may auto-open (informational + guard)
    on_approved: Callable                # (request) -> None, runs in-transaction
    on_rejected: Callable                # (request) -> None, runs in-transaction

REGISTRY: dict[str, GateSpec] = {}

def register(spec): ...
def get(target_kind) -> GateSpec: ...
def approvable_models() -> set[type]:   # drives the allow-list
    ...
```

Engine functions (all `@transaction.atomic`):
- `open_request(target, requested_by)` — resolve gate by target kind, create `ApprovalRequest(status=OPEN)`. Called from each gated model's create path (§Wiring).
- `cast_decision(request, step, user, outcome, note='')` — validate (via `Decision.clean`), create `ApprovalDecision`. If `rejeitada` → set request `REJECTED`, call `spec.on_rejected`, stop (terminal). If `aprovada` and it was the last required step → set request `APPROVED`, call `spec.on_approved`. Everything in one transaction.
- `cancel_request(request, user)` — requester or `admin_tenant`, only while `OPEN`; set `CANCELLED`, no side-effect.

**MVP gate registrations:**
| Gate | target_kind | steps (seed) | on_approved | on_rejected |
|------|-------------|--------------|-------------|-------------|
| G-1 | `contrato` | 1 (`aprovador`) | contract → `active` | contract → `terminated`/rejeitado |
| G-5 | `transferencia` | 2 (`gestor_competicao` sporting → `aprovador` legal, legal requires evidence) | create dest contract, rescind origin, close vínculo | negotiation → `open` |
| G-3 | `partida` (reabertura) | 1 (`aprovador`) | match → reopened, discard events | no-op (audit only) |

G-2 (inscrição) and G-4 (encerramento de edição) are named in Sprint 0 but their target flows (edition registration / close) aren't built yet — register them when those flows land; the engine needs no change.

---

## Invariants — enforced in `clean()` (server-side, per repo convention)

On `ApprovalDecision`:
1. **Self-approval ban** — `decided_by != request.requested_by`.
2. **Role match** — `decided_by` holds `step.required_role` (active membership in the case's tenant).
3. **Step ordering** — every lower-`order` step already has an `aprovada` Decisão.
4. **Evidence gate** — if `step.requires_evidence`, ≥1 `Evidencia` exists for the target.
5. **Case still open** — `request.status == OPEN`.

On `ApprovalRequest`: allow-list + `target_kind` consistency (above).

---

## Wiring the gated targets

Each gated model auto-opens its Solicitação on creation (ADR-0001, decision 9). Minimal touch: in the create path (service or `Contract`/`Negotiation`/`Match`-reopen flow), after saving the target in its pre-active state (`Contract` → `draft`, etc.), call `approvals.open_request(target, user)`. The target's `on_approved` handler is what flips it to active — creation alone never activates a gated target.

---

## Subtask mapping

- **3.3.1 Quem aprova** → `ApprovalFlowStep.required_role` + invariants 1–2 (role-per-Etapa, self-approval ban).
- **3.3.2 O que aprova** → GFK + allow-list + `target_kind`; registry `approvable_models()`.
- **3.3.3 Evidências necessárias** → `Evidencia` model + `requires_evidence` per Etapa + invariant 4.
- **3.3.4 Rejeição e retorno** → terminal rejection in `cast_decision` + per-gate `on_rejected`.

---

## Tests (`src/futebol/tests.py` or a new `tests/` package)

Django `TestCase`, one class per concern:
- **Happy path single-step (G-1):** open → approve → contract active, request `APPROVED`, one Decisão.
- **Happy path two-step (G-5):** step 1 approve (no side-effect yet) → step 2 approve → transfer executes atomically; assert dest contract created + origin rescinded in one commit.
- **Ordering:** deciding step 2 before step 1 raises `ValidationError`.
- **Self-approval:** `requested_by` deciding raises.
- **Role mismatch:** wrong-role user deciding raises.
- **Evidence gate:** approving an evidence-required step with zero Evidência raises; passes with one.
- **Terminal rejection:** reject step 2 → request `REJECTED`, `on_rejected` ran, step 1's Decisão frozen; a re-attempt is a new Solicitação starting at step 1.
- **Cancellation:** requester cancels OPEN request → `CANCELLED`, target untouched; cancelling a resolved request raises.
- **Tenant isolation:** decision by an approver from another tenant raises (relies on `tenant_bound_fields`).

---

## Sequencing (suggested commits / issues)

1. Models + migration (Flow/Step revise, Solicitação GFK, Decisão, Evidência) + admin registration.
2. `services/approvals.py` registry + engine (`open_request`, `cast_decision`, `cancel_request`).
3. `clean()` invariants + unit tests for each.
4. Register + wire G-1 (contract) end-to-end; integration test.
5. Register + wire G-5 (transfer, two-step, evidence) end-to-end; integration test.
6. Register + wire G-3 (match reopening); integration test.
