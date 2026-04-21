# ADR-0012 — Hash-chained tamper-evident event store (Clinical)

- Status: Accepted (design agreed in Phase 1; implemented in Phase 4)
- Date: 2026-04-14
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: core-domain, security, integrity, innovation

## Context and Problem Statement

The Clinical event store is the medical record. In principle, Event
Sourcing (ADR-0003) gives perfect history — but only if that history
is **provably un-edited**. Row-level audit is not enough: a DBA or a
compromised admin with direct DB access can update an event row and
nothing downstream would notice.

A hospital / clinic has medico-legal obligations: the record
presented as evidence must be the record that was written. We need a
mechanism that makes any retroactive edit to the Clinical event log
**cryptographically detectable**.

This is our declared **innovative extension** for the project.

## Decision Drivers

- Integrity is a first-class quality attribute on the Clinical
  context.
- Auditors and regulators value mathematical, not policy, guarantees.
- The mechanism must add near-zero write-time latency.
- It must not require an external KMS or external storage.

## Considered Options

1. **Row-level audit table** (before/after on every update).
2. **Database-level WAL retention + off-site copy**.
3. **Cryptographic hash chain** over events (each event's hash
   includes the previous event's hash; tamper-evident).
4. **Full blockchain / Merkle forest** persisted externally.

## Decision Outcome

Chosen option: **Option 3 — Hash chain** over the Clinical event
stream.

### Structure

Each event row in the Clinical `events` table carries:

- `prev_hash` — the `hash` of the previous event in the same stream
  (aggregate), or a genesis value for the first event.
- `hash` — `sha256(canonical_json({id, aggregate_id, aggregate_version,
  event_type, occurred_at, payload, prev_hash}))`.

Writes happen in a transaction that holds `SELECT … FOR UPDATE` on
the aggregate's latest event (ensuring nobody can interleave and
change `prev_hash`). Any tamper with an historical row invalidates
every subsequent `hash`; a cheap `verify_chain(aggregate_id)` function
walks the stream and detects it in O(events).

### Disclosure layer

Periodically (default: once a day), the current head hash of every
aggregate is written to an **append-only ledger table** and to the
shared kernel's outbox as a `clinical.integrity.anchor.v1` event. A
real deployment would additionally publish the anchor to an
independent notary (a peer hospital, a trusted timestamping service,
or a public blockchain) — but that is an operational concern and not
strictly required for tamper-evidence within our stack.

### Positive Consequences
- Any edit to past medical history is detectable in constant time.
- Integrates cleanly with ES + outbox (ADR-0003, ADR-0009).
- Explained in a single paragraph; implementable in tens of lines.
- Genuinely novel for this project and directly addresses a real
  domain concern.

### Negative Consequences
- Schema change vs. vanilla ES. Accepted.
- `prev_hash` lookup on write is one extra indexed read per event
  per aggregate; negligible.
- Cannot hard-delete an event (deletion breaks the chain) — we use
  **crypto-shredding** (store encrypted payload, discard the key)
  for right-to-be-forgotten scenarios. Operationally rare.
- No guarantee against a tamper that rewrites the chain *from head
  backwards* without independent anchors — this is why the anchor
  step exists.

## Pros and Cons of the Options

### Row-level audit
- Good, because cheap.
- Bad, because the audit table is also in the DB — same blast radius.

### WAL retention
- Good, because infrastructure-level.
- Bad, because it is an operational guarantee, not a mathematical
  one; a compromised DBA can rotate it.

### Hash chain
- Good, because mathematical, local, cheap.
- Bad, because requires in-domain awareness.

### Blockchain
- Good, because maximal trust.
- Bad, because operational cost is wildly disproportionate for a
  single-tenant clinic system.

## Phase 1 contract

The shared-kernel outbox already carries a `headers: JSONB` column.
The Clinical-specific hash fields are **not** part of the generic
outbox — they live on the Clinical write-side's own `events` table
(created in Phase 4). Phase 1 only reserves the ADR so later phases
inherit a decided direction.

## Links
- ADR-0003, ADR-0009.
- Haber & Stornetta 1991, "How to Time-Stamp a Digital Document".
- Linear history as an integrity property — git's commit graph.
