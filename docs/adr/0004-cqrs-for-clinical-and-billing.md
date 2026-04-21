# ADR-0004 — CQRS for Clinical and Billing

- Status: Accepted
- Date: 2026-04-10
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: architecture-style, cqrs, clinical, billing

## Context and Problem Statement

Two contexts have an asymmetric read/write shape:

- **Clinical** — writes are a trickle (a doctor sees ~20 patients a day),
  but reads are heavy and shaped by the UI (patient timeline, vitals
  chart, open prescriptions). Event Sourcing (ADR-0003) makes the write
  side append-only — trivial to write, impossible to query directly.
- **Billing** — writes are invoice state transitions; reads are
  analytics (ageing reports, revenue per doctor, payer reconciliation).
  The report queries have nothing in common with the write schema.

A single model forces reads and writes into the same shape. CQRS
splits them so each side wins independently.

## Decision Drivers

- ES on Clinical (ADR-0003) forces a separate read-model anyway.
- Reporting queries on Billing would require awkward joins on the
  transactional schema.
- Modifiability: UI teams can change read-models without touching
  write-side invariants.
- The marking scheme rewards CQRS as a named pattern.

## Considered Options

1. **Single model** — one ORM, one schema, one set of repositories.
2. **CQRS in every context** — uniform.
3. **CQRS only in Clinical and Billing** — surgical.

## Decision Outcome

Chosen option: **Option 3 — CQRS only in Clinical and Billing**.

- Clinical: write-side is an event log (`clinical_write` DB); read-side
  is a relational projection (`clinical_read` DB) fed by the same
  events published to RabbitMQ.
- Billing: write-side is the transactional `Invoice` / `Payment`
  aggregates; read-side is a denormalised reporting view refreshed
  by event projections.

### Positive Consequences
- Reads and writes can be scaled and optimised independently.
- Read-side can use completely different tech (e.g., a materialised
  view, an OLAP cube, a search index) without touching the write model.
- Clinical's ES write-model stays pure and queryless.
- UI-driven changes never corrupt invariants.

### Negative Consequences
- **Eventual consistency** between sides is exposed to the UI. We
  mitigate by reading our own write immediately post-commit
  ("read-your-writes" via the request context), and by displaying a
  processing indicator for reads that depend on cross-context events.
- Two schemas to maintain per context → more Alembic migrations.
- Projection rebuilds on schema change need to be operational.

## Pros and Cons of the Options

### Single model
- Good, because simplest.
- Bad, because forces the write-side schema to serve UI needs.
- Bad, because incompatible with ES on the write side.

### CQRS everywhere
- Good, because uniform and "pure".
- Bad, because premature — most contexts do not have asymmetric load.
- Bad, because cost is paid per context (migrations, projections,
  consistency UX).

### CQRS in Clinical and Billing only
- Good, because targeted at the shapes that actually benefit.
- Good, because students reading the repo learn "when to apply", not
  just "what".
- Bad, because two contexts have a dual model the others don't — a
  small training tax.

## Links
- ADR-0002, ADR-0003, ADR-0009.
- Young, "CQRS Documents by Greg Young" (2010).
- Fowler, "CQRS" — <https://martinfowler.com/bliki/CQRS.html>.
