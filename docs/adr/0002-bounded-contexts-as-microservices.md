# ADR-0002 — Bounded contexts as microservices

- Status: Accepted
- Date: 2026-04-10
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: architecture-style, bounded-context, deployment

## Context and Problem Statement

The proposal identifies six bounded contexts with clearly different
**change cadences, languages, consistency needs, and stakeholders**:
Patient Identity, Scheduling, Clinical, Pharmacy, Laboratory, Billing.
The question is: how big should each deployable unit be?

## Decision Drivers

- The marking scheme rewards **explicit boundaries** and
  **Published Language** across bounded contexts.
- Clinical is the **core domain** — it will iterate fastest and must
  evolve schema freely (it uses Event Sourcing).
- Billing has stricter consistency + audit needs than Scheduling.
- The team is small (3) so operational cost matters.
- Polyglot persistence is valuable: Clinical wants an append-only
  store; Billing wants relational.

## Considered Options

1. **Modular monolith** — one deployable, strict module boundaries,
   Published Language as internal events.
2. **Microservices per bounded context** — one deployable per context,
   Published Language across RabbitMQ.
3. **Hybrid** — monolith today, extract as pressure demands.

## Decision Outcome

Chosen option: **Option 2 — Microservices per bounded context**.

### Positive Consequences
- Context autonomy: each service owns its own schema, migrations,
  runtime version, libraries. Polyglot persistence is trivial.
- Failure isolation: a broken Billing migration does not stop
  patient registration.
- Clear Published Language: communication *must* go through the
  broker, which makes coupling visible and reviewable.
- Demonstrates the full breadth of the marking-scheme rubric in
  one system.
- Maps directly to the proposal's architecture diagram.

### Negative Consequences
- Operational overhead — we mitigate with a one-shot
  `docker compose up` stack (ADR-0008).
- Distributed-systems complexity: we must deal with eventual
  consistency, outbox, idempotency, sagas (addressed in ADR-0009
  and ADR-0005).
- Cross-context queries are impossible by construction — which is
  *the point*, but also a UX constraint that will be solved by
  per-context read-models (ADR-0004).

## Pros and Cons of the Options

### Modular monolith
- Good, because single deploy, single DB, trivial transactions.
- Good, because refactoring across modules is cheap early on.
- Bad, because module boundaries erode without compiler-enforced
  walls; in a teaching context we want walls.

### Microservices
- Good, because boundaries are physical (network) and impossible to
  leak accidentally.
- Good, because each context can be written, marked and demoed
  independently.
- Bad, because distributed-systems concerns are real work.

### Hybrid
- Good, because pragmatic for a small team.
- Bad, because the project brief asks us to *demonstrate* the style
  — a hybrid dilutes that demonstration.

## Links
- Evans 2003, *Domain-Driven Design*, ch. 14 "Maintaining Model
  Integrity".
- Newman 2021, *Building Microservices*, 2e.
- ADR-0008, ADR-0009, ADR-0004.
