# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

SaaS for managing football (soccer) operations — registrations, approval flows, dashboards, and reports. Multi-tenant Django 4.2 application (Python 3.11, PostgreSQL 16). Codebase and domain language are **Portuguese (pt-br)**; the timezone is `America/Sao_Paulo`. Match the surrounding language when writing user-facing strings, model verbose names, and comments.

The application is developed largely by an automated sprint orchestrator (`orchestrator/`) that drives an OpenCode CLI (GLM 5.2). See "Orchestrator" below.

## Commands

Everything runs through Docker Compose, wrapped by the `Makefile`. Django lives under `src/`, so `manage.py` is always invoked as `python src/manage.py ...`.

- `make up` / `make down` — start / stop services (`web` on :8000, `db` Postgres on :5432)
- `make build` / `make restart` — build images / rebuild + restart
- `make migrate` / `make makemigrations` — run / create migrations
- `make test` — run the full Django test suite
- `make shell` / `make bash` — Django shell / bash inside the `web` container
- `make createsuperuser` — create an admin user
- `make logs` — tail `web` logs

Run a single test (no Make target — invoke directly):
```
docker compose run --rm web python src/manage.py test futebol.tests.HomeFlowTests.test_home_renders_after_login
```

The `web` entrypoint (`entrypoint.sh`) runs `migrate` and `collectstatic` automatically on container start. The repo root is bind-mounted into `/app`, so code changes hot-reload via `runserver`.

## Architecture

Two Django projects live in `src/`: `config/` (settings, root URLconf, WSGI/ASGI) and the single app `futebol/`. All domain logic is in `futebol/`.

### Multi-tenancy is the core invariant

Every domain model except `Tenant` and `TenantMembership` inherits from **`TenantScopedModel`** (`futebol/models.py`). This base class enforces tenant isolation at the data layer — do not bypass it:

- It adds a `tenant` FK and `created_at`/`updated_at` to every subclass.
- `save()` calls `full_clean()` on every write, so model-level validation always runs (this is not Django's default).
- `tenant_bound_fields` is a per-model tuple of related FKs that **must belong to the same tenant** as the row itself. `clean()` validates this. When you add a model with FKs to other tenant-scoped models, list those FKs in `tenant_bound_fields` — otherwise cross-tenant references can leak.

`TenantMembership.Role` defines the seven authorization roles (admin_tenant, gestor_clube, gestor_competicao, aprovador, delegado_partida, auditor, admin_plataforma). Views scope querysets by the user's active memberships; superusers see all tenants (see `TablePage.queryset` and `_accessible_tenants` in `futebol/views.py`).

### Domain model shape

The `futebol` app models the full lifecycle: `Club`, `Person`, `TeamCategory`, then the competition tree `Competition → CompetitionEdition → CompetitionPhase → Match → MatchEvent`/`MatchLineup`, plus `Contract`/`Negotiation`/`Proposal`, an approval subsystem (`ApprovalFlow`/`ApprovalRequest`), `Notification`, `ExternalSystem`/`IntegrationRecord`, and `AuditLog`. Business rules per competition live in `CompetitionRuleSet` (registration notice, suspension length, immutability window, import limits, conflict policy).

Notable model-level rules to preserve:
- **`Match.immutable_after`** is derived on `clean()` from the competition's `CompetitionRuleSet.immutability_window_hours`; `is_mutable()` gates edits after a match. Home and away clubs must differ (enforced by both `clean()` and a CheckConstraint).
- **`AuditLog` is append-only** — its `save()` rejects updates (any row with a pk) and `delete()` always raises. It uses a `GenericForeignKey` to reference any audited object.
- Uniqueness constraints are almost always **scoped per tenant** (e.g. `uniq_club_slug_per_tenant`). Follow this pattern for new unique fields.

### Views layer

`futebol/views.py` uses a hand-rolled **`TablePage`** helper class (not Django CBVs) to render searchable, paginated, sortable list pages from a declarative config (`model`, `search_fields`, `ordering_map`, `columns`). Columns accept either a dotted-attribute string or a callable. New list pages should follow this pattern. Templates are server-rendered (`futebol/templates/`), extending `futebol/base.html`; there is no REST/JS frontend.

### Import/export service

`futebol/services/data_io.py` is the CSV/JSON bulk import/export layer, keyed by `MODEL_REGISTRY` (club, competition, edition, phase, match). Imports are `@transaction.atomic`, upsert per-row with a `conflict_policy` of skip/overwrite/error, and return an `ImportResult` tally. Exposed as management commands:
```
python src/manage.py import_futebol_data --tenant <slug> --model match --input file.csv --conflict-policy skip
python src/manage.py export_futebol_data --tenant <slug> --model match --output file.csv
```

### Request tracing

`RequestIDMiddleware` (`futebol/middleware.py`) assigns an `X-Request-ID` per request (honoring an inbound header), stored in a `ContextVar` and injected into every log line via `RequestIDFilter`. Logging is configured in `config/settings.py` with a `request_id=` field in the verbose formatter. Preserve this correlation ID when adding logging.

## Orchestrator

`orchestrator/` runs the automated build loop — it is **not** part of the deployed application. `runner.py` reads `sprints.json` (a nested sprints → tasks → subtasks tree), executes the next pending subtask via the OpenCode CLI, writes per-subtask output to `reports/`, tracks progress in `state/execution_state.json`, and sends WhatsApp notifications via the Evolution API (`whatsapp_notify.py`).

```
python3 orchestrator/runner.py             # run next pending subtask
python3 orchestrator/runner.py --loop      # run until blocked
python3 orchestrator/runner.py --status    # show progress
python3 orchestrator/runner.py --review    # list subtasks awaiting review
python3 orchestrator/runner.py --approve <id>
python3 orchestrator/runner.py --report    # consolidated technical report
```

Product documentation (PRD, tech spec, sprint notes) lives under `docs/{prd,techspec,sprints}/`.

## Conventions

- **Language**: Portuguese for all domain names, choices labels, validation messages, and UI text.
- **Validation belongs on the model** — rely on `full_clean()` running in `save()` rather than validating in views; add `CheckConstraint`/`UniqueConstraint` for invariants that must hold at the DB level.
- **Secrets** come from env vars (`.env`, see `.env.example`); `config/settings.py` reads them with `os.getenv` and dev defaults. Never rely on the dev `SECRET_KEY` or `DEBUG=1` defaults in production.

## Agent skills

### Issue tracker

Issues and PRDs live in GitHub Issues (`alexfloripavieira/saas-futebol`), managed via the `gh` CLI. External PRs are also a triage surface. See `docs/agents/issue-tracker.md`.

### Triage labels

Default label vocabulary — `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context — one `CONTEXT.md` + `docs/adr/` at the repo root. See `docs/agents/domain.md`.
