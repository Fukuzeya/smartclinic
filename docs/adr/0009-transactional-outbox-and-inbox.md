# ADR-0009 — Transactional Outbox and Inbox

- Status: Accepted
- Date: 2026-04-13
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: reliability, messaging, integration

## Context and Problem Statement

Each write in a bounded context has two side-effects:

1. Commit state to Postgres.
2. Publish one or more domain events to RabbitMQ (ADR-0008).

Without care, these can desync: commit succeeds, publish fails (state
exists, downstreams never hear about it); or publish succeeds, commit
fails (downstreams react to a world that never was).

On the consuming side, RabbitMQ guarantees **at-least-once** delivery.
So any handler that performs a side-effect (an insert, a spend) must
be idempotent.

## Decision Drivers

- Commit and publish must be atomic, under broker outage, crash, or
  network partition.
- Consumers must be able to reprocess any message without duplicate
  effect.
- We have Postgres available; we can use it.

## Considered Options

1. **Direct publish inside the transaction**.
2. **Distributed transaction (XA / 2PC)** across Postgres and RabbitMQ.
3. **Transactional Outbox + Inbox pattern** with a relay process.
4. **Change-data-capture (CDC, e.g., Debezium)** off the Postgres WAL.

## Decision Outcome

Chosen option: **Option 3 — Transactional Outbox + Inbox**.

### Write side (Outbox)

Pending domain events are written to an `outbox` table in the *same*
Postgres transaction as the aggregate save. A separate `OutboxRelay`
process polls:

```sql
SELECT … FROM outbox
 WHERE published_at IS NULL
 ORDER BY created_at
 LIMIT :n
 FOR UPDATE SKIP LOCKED
```

… publishes to RabbitMQ with publisher confirms, then marks
`published_at = now()`. `FOR UPDATE SKIP LOCKED` means the relay can
run N replicas without coordination — each picks up a disjoint batch.
Failed publishes increment `attempts` and retry with exponential
backoff. After `max_attempts` an event is flagged to the DLQ via the
relay's own logic.

### Read side (Inbox)

Each consumer, before handling a message, writes `(event_id, consumer_name)`
to its `inbox` table (primary key on that pair). If the insert fails
on unique-key conflict, the message has already been processed — ACK
and drop.

Implementation: both tables live in the shared kernel as SQLAlchemy
ORM models (`OutboxRecord`, `InboxRecord`). The unit-of-work wires
them up transparently.

### Positive Consequences
- Lose nothing: the outbox is part of the aggregate's transaction.
- See nothing twice: the inbox guarantees exactly-once *effect*
  (at-most-once handling of any `event_id`).
- Scale-out relays safely via `SKIP LOCKED`.
- Observable: `smartclinic_outbox_pending`, `smartclinic_outbox_lag_seconds`
  metrics show backpressure in real time.

### Negative Consequences
- **Latency:** published-to-consumer delay equals the relay poll
  interval (default 250 ms). Acceptable for our domain.
- **Extra DB write** per event.
- **Operational:** the relay is its own process. We run it in-process
  with each service for simplicity; it can move out later.

## Pros and Cons of the Options

### Direct publish in transaction
- Bad, because commit-then-publish can lose; publish-then-commit can
  over-publish.

### XA / 2PC
- Good, because "solves" the problem.
- Bad, because RabbitMQ does not participate; forcing the issue via
  XA-capable brokers (e.g., ActiveMQ) is operational torture.

### Outbox + Inbox
- Good, because uses what we already have (Postgres).
- Good, because fits ES naturally — the event log *is* already the
  outbox on the Clinical write side.
- Bad, because latency and extra writes.

### CDC / Debezium
- Good, because zero application coupling.
- Bad, because running Kafka Connect + Debezium is a lot of stack for
  this project. Also: we lose the ability to annotate events with
  application-level metadata (trace_id, causation_id) at emit time.

## Links
- ADR-0003, ADR-0004, ADR-0008.
- Richardson, "Microservices Patterns", ch. 3 (Transactional Outbox).
- Fowler, "What do you mean by 'Event-Driven'?"
  <https://martinfowler.com/articles/201701-event-driven.html>.
