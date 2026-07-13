# Sports provider data is a continuously updated platform asset

## Status

accepted

## Context

Public and platform-licensed sports data is the raw material of the intelligence sold by the SaaS. Storing and synchronizing one copy per Tenant makes customers responsible for ingestion, duplicates provider traffic, and confuses shared product data with private club data.

## Decision

The platform owns one continuously updated **Base Esportiva Global**, outside `TenantScopedModel`. Provider synchronization is infrastructure work and never depends on a Tenant, tenant user, contracted Automations module, or tenant-triggered action. A contracted intelligence service grants read/use entitlement over the shared catalog; it does not control ingestion.

Tenant-provided GPS, health, contracts, availability, reports and decisions remain tenant-scoped. The Treinador Inteligente combines entitled global evidence with that private context, while its Dossiês, Planos de Jogo, lineups and tactical boards remain private to the Tenant.

## Consequences

- Global provider versions are ingested once and refreshed continuously for every entitled Tenant.
- Operational sync controls belong to platform administration; tenants see freshness, provenance and limitations only.
- Tenant-scoped payloads are never promoted automatically: metadata and source URLs cannot prove that a club did not enrich the payload with private fields.
- Legacy public copies are removed only when an artifact-free batch has a native global batch with the same source, dataset and content hash; every unverified batch is preserved.
- Source and capability entitlements gate every canonical read, materialization and global laboratory. A disabled global source acts as a platform kill switch.
- Partial provider failures remain visible and are retried with bounded exponential backoff instead of being reported as a successful cycle.
