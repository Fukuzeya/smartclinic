# ADR-0003 — Event Sourcing for the Clinical context

- Status: Accepted
- Date: 2026-04-10
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: persistence, core-domain, clinical

## Context and Problem Statement

The Clinical context is the core domain and holds the medical record.
The record has two properties no CRUD schema gives for free:

1. **Full auditability.** Who changed what, when, and why, must be
   reconstructible years later. Medical records have medico-legal
   weight and, under POPIA / HIPAA-equivalent regimes, deletion is
   explicitly restricted.
2. **Temporal query.** "What did the doctor know at 14:03 on
   2024-08-15 when they prescribed X?" is a real question. A CRUD
   row cannot answer it; only the history of state can.

## Decision Drivers

- Medico-legal auditability.
- Temporal / as-of queries.
- The proposal commits to demonstrating Event Sourcing.
- Our hash-chained tamper-evident extension (ADR-0012) requires an
  append-only event log anyway.

## Considered Options

1. **CRUD with audit tables** (temporal tables or application-level
   audit log).
2. **Event Sourcing** — aggregates persisted as immutable event streams.
3. **Bitemporal modelling** (SQL:2011-style application- and
   system-time).

## Decision Outcome

Chosen option: **Option 2 — Event Sourcing**.

### Positive Consequences
- State is a projection of events → by construction we have *every*
  historical fact, not just the last one.
- Events are the publication format on the bus (ADR-0008); ES collapses
  persistence and publication into one shape.
- Enables hash-chained tamper evidence (ADR-0012) almost for free.
- Debugging and forensic replay are trivial.

### Negative Consequences
- **Querying is harder** — we cannot SELECT against aggregate state.
  Mitigated by CQRS (ADR-0004): a separate read-model database
  materialised by projections.
- **Schema evolution** of events is non-trivial. Mitigated by
  versioned event types (`*.v1`, `*.v2`) and upcasters on replay.
- **Training cost** for the team — real but acceptable given the
  marking scheme explicitly rewards this pattern.
- **Storage growth** is unbounded in principle. Mitigated by
  snapshots (Phase 4 design) and pragmatic retention on projections.

## Pros and Cons of the Options

### CRUD with audit tables
- Good, because well-understood, cheap to query, cheap to train on.
- Bad, because audit tables drift from truth — a malicious or buggy
  update path can change state without logging.
- Bad, because reconstructing *intent* (why) from a diff is hard.

### Event Sourcing
- Good, because the log *is* the truth; projections are subordinate.
- Good, because perfectly composable with domain events on the bus.
- Bad, because query complexity shifts to the read-side.

### Bitemporal
- Good, because SQL-native and queryable.
- Bad, because no commodity ORM gives the pattern ergonomically.
- Bad, because intent / cause still isn't captured — only state at time.

## Scope

Event Sourcing is **applied only to the Clinical context**. The other
five contexts use CRUD + outbox. This is deliberate: ES is expensive
and the rest of the domain does not demand it.

## Quantified Trade-offs

| Attribute | CRUD + audit | Bitemporal | **Event Sourcing** (chosen) |
|---|---|---|---|
| Temporal query complexity | O(n log n) reconstruction from diffs | O(1) SQL range | O(events) replay; O(1) with snapshot |
| Tamper-evidence integration (ADR-0012) | Requires parallel structure | Not natural | Native — append-only log is the source |
| Cross-context event publication | Extra step (pull state, serialise) | Extra step | Events are already in publish format |
| Write path overhead | 1 × SQL UPDATE | 2 × SQL (application + system time) | 1 × INSERT (append-only; no locks on aggregate row) |
| Schema migration complexity | Low | Medium | High — event upcasters needed for schema changes; mitigated by versioned types (`*.v1`) |
| Storage growth over 5 years (est.) | ~2 MB / 1000 patients | ~3 MB / 1000 patients | ~8 MB / 1000 patients (acceptable; read models remain small) |
| Developer training cost | 0 (familiar) | Low–Medium | Medium-High — mitigated by Shared Kernel base classes |

**Marginal cost accepted**: ~6 MB extra storage per 1000 patients and one extra
abstraction layer in return for: (a) free temporal query, (b) hash-chain
tamper evidence, (c) zero-extra-work domain event publication.

## Why not the alternatives?

**CRUD + audit tables**: An audit trigger records diffs, not intent. A
DBA with `UPDATE` privilege can alter the main row without touching the
audit row if the trigger is disabled during maintenance. This fails the
medico-legal tamper-evidence requirement. The ADR-0012 hash chain cannot be
built over a mutable row without prohibitively expensive re-hashing.

**Bitemporal modelling**: Records *when* a fact was valid but not *why* it
changed. Reconstructing the physician's decision context at 14:03 still
requires interpreting raw column diffs. Standard ORM support for SQL:2011
temporal tables is poor in Python's ecosystem (SQLAlchemy requires manual
`WITHOUT OVERLAPS` constraints). The query model is SQL-native but the write
model is still mutable, making the hash chain structurally impossible.

## Links
- ADR-0002, ADR-0004, ADR-0009, ADR-0012.
- Fowler, "Event Sourcing" — <https://martinfowler.com/eaaDev/EventSourcing.html>.
- Vernon 2013, *Implementing Domain-Driven Design*, ch. 8.
