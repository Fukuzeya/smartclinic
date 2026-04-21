# ADR-0010 — Shared Kernel scope and governance

- Status: Accepted
- Date: 2026-04-13
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: shared-kernel, dependency-policy, governance

## Context and Problem Statement

With six bounded-context services (ADR-0002), every context will need
building blocks that are truly universal: identity, time, money,
value-object semantics, the outbox, structured logging, tracing,
Keycloak JWT validation. If each context reinvents these, we get
inconsistency and duplication. If we share too much, we corrupt the
bounded contexts (the shared kernel becomes a ball of mud every
context is chained to).

## Decision Drivers

- Provide real leverage without bleeding one context's language into
  another.
- Avoid the classic shared-kernel anti-pattern: a monolithic
  "commons" library that eats the codebase.
- Make the marking scheme's "Shared Kernel vs Published Language"
  distinction visible in code.

## Considered Options

1. **No shared library** — every context copy-pastes primitives.
2. **Unbounded shared library** — anything reusable lives there.
3. **Narrow, governed Shared Kernel** — tightly scoped and jointly
   owned.

## Decision Outcome

Chosen option: **Option 3 — Narrow, governed Shared Kernel**.

### What the Shared Kernel contains

1. **Domain primitives** — `Entity`, `AggregateRoot`, `ValueObject`,
   `DomainEvent`, `Specification`, `Repository`, `Result`, `DomainError`.
2. **Cross-cutting value objects that are not bounded-context-specific**
   — `Money`, `PersonName`, `Email`, `PhoneNumber`, `ZimbabweanNationalId`,
   `Clock`, the typed `Identifier` system.
3. **Application primitives** — `Command`, `Query`, `Mediator`,
   `UnitOfWork`.
4. **Infrastructure** — `OutboxRelay`, `InboxRecord`, `RabbitMQPublisher`,
   `structlog` config, OTel setup, Prometheus helpers, Keycloak JWT
   validator, the FastAPI app factory.

### What the Shared Kernel **does not** contain

- Anything named in the language of a single bounded context
  (`Patient`, `Appointment`, `Encounter`, `Prescription`, `Invoice` —
  each lives **only** in its owning service).
- HTTP / API contracts for any context — these are a Published
  Language, shipped as versioned event payloads, not as shared Python
  types.
- Domain-specific rules — `HasAllergyInteraction` lives in Pharmacy,
  not in the kernel.

### Governance

- **Joint ownership**: every team member must approve a change.
- **Additive only** by default; breaking changes require a MADR ADR
  and a synchronised bump across all consumers.
- **No cross-context imports** — enforced by a CI fitness function
  (`tests/fitness/test_architecture.py`). A service importing another
  service's module fails the build.

### Positive Consequences
- Every context inherits the outbox, tracing, logging and RBAC
  **identically** — consistency is free.
- A new bounded context is productive on day one; the scaffolding
  is already solved.
- The kernel surface is small and inspectable; reviewers see what is
  shared.

### Negative Consequences
- Changes to the kernel ripple. We accept this explicitly: the
  kernel is stable by construction and should not change often.
- Temptation to dump "commonly useful" helpers here. Mitigated by
  the fitness functions and review policy.

## Pros and Cons of the Options

### No shared library
- Good, because maximum context independence.
- Bad, because drift: one context handles correlation IDs, another
  does not; one traces DB calls, another does not. Demo collapses.

### Unbounded shared library
- Good, because maximum reuse.
- Bad, because becomes a monolith by stealth; every context is
  coupled to every other via the kernel.

### Narrow, governed
- Good, because the marking scheme wants exactly this distinction.
- Good, because architecture is visible in the directory structure.
- Bad, because discipline is required — mitigated by CI fitness.

## Links
- ADR-0002, ADR-0009, ADR-0011.
- Evans 2003, *DDD*, ch. 14 — "Shared Kernel".
