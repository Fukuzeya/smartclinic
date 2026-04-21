# Architecture Decision Records

Every significant design decision on SmartClinic is recorded here as a
short, immutable document. We use the **MADR 4.0** template
(<https://adr.github.io/madr/>) because it is the de-facto format, is
purely Markdown, and renders readably on GitHub.

## Why ADRs?

The marking scheme rewards *justified* decisions, not decisions. An ADR
freezes the **Context** (what was true when we decided), the
**Options** we weighed, the **Decision** we made, and the
**Consequences** we accepted — good and bad. Six months from now, when
someone asks "why did you pick RabbitMQ over Kafka?", the answer is a
single file, not oral history.

ADRs are **immutable once merged**. If the decision changes, we write a
new ADR that supersedes the old one and update the `status` of the old
one — never edit history.

## Status values

- `Proposed` — written but not yet agreed.
- `Accepted` — the current way.
- `Deprecated` — still true but discouraged; a newer approach exists.
- `Superseded by ADR-NNNN` — replaced, with a pointer.

## Index

| #    | Title                                                                                   | Status   |
|------|-----------------------------------------------------------------------------------------|----------|
| 0001 | [Record architecture decisions](0001-record-architecture-decisions.md)                  | Accepted |
| 0002 | [Bounded contexts as microservices](0002-bounded-contexts-as-microservices.md)          | Accepted |
| 0003 | [Event Sourcing for the Clinical context](0003-event-sourcing-for-clinical-context.md)  | Accepted |
| 0004 | [CQRS for Clinical and Billing](0004-cqrs-for-clinical-and-billing.md)                  | Accepted |
| 0005 | [Saga for the Patient Visit lifecycle](0005-saga-for-patient-visit-lifecycle.md)        | Accepted |
| 0006 | [Specification Pattern in Pharmacy](0006-specification-pattern-in-pharmacy.md)          | Accepted |
| 0007 | [Anti-Corruption Layer for the drug DB](0007-anti-corruption-layer-for-drug-db.md)      | Accepted |
| 0008 | [RabbitMQ as the event bus](0008-rabbitmq-as-event-bus.md)                              | Accepted |
| 0009 | [Transactional Outbox and Inbox](0009-transactional-outbox-and-inbox.md)                | Accepted |
| 0010 | [Shared Kernel scope and governance](0010-shared-kernel-scope-and-governance.md)        | Accepted |
| 0011 | [Keycloak OIDC for RBAC](0011-keycloak-oidc-for-rbac.md)                                | Accepted |
| 0012 | [Hash-chained tamper-evident event store](0012-hash-chained-tamper-evident-event-store.md) | Accepted |

## Creating a new ADR

```bash
make adr-new TITLE="Use Temporal for long-running workflows"
```

The `adr-new` target copies the template below, slugifies the title and
picks the next 4-digit number.

## Template (MADR 4.0, trimmed)

```markdown
# ADR-NNNN — <Short noun-phrase title>

- Status: Proposed | Accepted | Deprecated | Superseded by ADR-MMMM
- Date: YYYY-MM-DD
- Deciders: <names>
- Tags: <bounded-context, concern>

## Context and Problem Statement

<What is the force at work? Why is a decision needed now?>

## Decision Drivers

- <driver 1>
- <driver 2>

## Considered Options

1. Option A
2. Option B
3. Option C

## Decision Outcome

Chosen option: **Option X**, because <justification>.

### Positive Consequences
- …

### Negative Consequences
- …

## Pros and Cons of the Options

### Option A — <name>
- Good, because …
- Bad, because …

### Option B — <name>
- Good, because …
- Bad, because …

## Links
- <related ADRs, RFCs, papers, blog posts>
```
