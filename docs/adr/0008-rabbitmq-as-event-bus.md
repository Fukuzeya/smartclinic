# ADR-0008 — RabbitMQ as the event bus

- Status: Accepted
- Date: 2026-04-13
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: messaging, integration, infrastructure

## Context and Problem Statement

Bounded contexts (ADR-0002) communicate only via domain events. We
need a broker that supports:

- **Topic-based routing** — so a context subscribes to
  `clinical.encounter.prescription_issued.v1` without knowing who
  published it.
- **Durability** — events outlive consumer downtime.
- **Dead-letter handling** — poison messages go somewhere we can
  inspect.
- **Per-consumer queues** — so slow consumers don't block fast ones.
- **Good Python support** with native asyncio.
- **Runs on a student laptop**.

## Decision Drivers

- Operational realism within the demo budget.
- Pattern fit: the published-language model maps cleanly to topic
  exchanges.
- Team familiarity.
- Observability: we need Prometheus metrics and the ability to see
  queue depth.

## Considered Options

1. **RabbitMQ** (AMQP 0-9-1) with a topic exchange.
2. **Apache Kafka** with one topic per event type.
3. **Redis Streams**.
4. **NATS JetStream**.
5. **In-memory pub-sub** — ship nothing.

## Decision Outcome

Chosen option: **Option 1 — RabbitMQ 3.13 (management + Prometheus plugin)**.

Topology (see `ops/rabbitmq/definitions.json`):
- One topic exchange: `smartclinic.events`.
- One DLX (fanout): `smartclinic.events.dlx` → queue `smartclinic.events.dlq`.
- One durable queue per bounded context, bound by routing-key
  patterns drawn from the Published Language of its upstreams.

Client library: `aio-pika` (asyncio-native, publisher confirms).

### Positive Consequences
- Routing-key semantics (`patient.#`, `clinical.#`) match exactly how
  Published Language is namespaced.
- Persistent messages + publisher confirms give the reliability we
  need (layered on the Outbox — ADR-0009).
- The management UI is invaluable as a demo artefact — "here is the
  queue depth on Billing as invoices fly through".
- Prometheus metrics exporter plugs straight into the stack.

### Negative Consequences
- RabbitMQ does not retain messages after consumer ACK. For an
  event-*log* need (Clinical ES), the log lives in Postgres — the bus
  only ever carries projection-feeding publications. This separation
  is explicit.
- No native replay across consumers. Our Outbox (ADR-0009) mitigates
  by being the durable source.

## Pros and Cons of the Options

### RabbitMQ
- Good, because mature, easy ops, fit for purpose.
- Bad, because not a log (no replay); addressed via Outbox.

### Kafka
- Good, because it *is* a log; replay is trivial; partitioning is
  first-class.
- Bad, because operational cost of ZK/KRaft + topic-per-event-type
  blows up in the demo container budget.
- Bad, because overkill for our throughput.

### Redis Streams
- Good, because light.
- Bad, because durability story is weaker; no routing-key expressions.

### NATS JetStream
- Good, because modern and fast.
- Bad, because the team has no operational experience with it, and
  for a marked project that matters.

### In-memory
- Good, because zero ops.
- Bad, because cannot demonstrate the pattern honestly.

## Links
- ADR-0002, ADR-0009.
- RabbitMQ topic exchange docs.
- <https://github.com/mosquito/aio-pika>.
