# `shared_kernel` — DDD Building Blocks

The Shared Kernel is the **only** module explicitly permitted to be imported by
more than one bounded context. It contains *concepts that are universally
stable across the business*, nothing else.

> **Governance:** changes to this package require a Pull Request approved by
> **all** context owners — see [ADR 0010](../../docs/adr/0010-shared-kernel-scope-and-governance.md).

## What is in-scope

| Layer | What it provides | What it DOES NOT provide |
|---|---|---|
| `domain/` | `Entity`, `AggregateRoot`, `ValueObject`, `DomainEvent`, `Specification`, `Repository` protocol, `Result`, `DomainError` family | Any concrete aggregate (Encounter, Invoice, Appointment) |
| `types/` | Pan-clinical value objects: `Money`, `PatientId`, `EncounterId`, `PersonName`, `Email`, `PhoneNumber`, `ZimbabweanNationalId`, `Clock` | `ICD10Code`, `Dosage`, `VitalReading` — these live in their owning context |
| `application/` | `Command`, `Query`, `CommandHandler`, `Mediator`, `UnitOfWork` protocol | Concrete handlers, sagas |
| `infrastructure/` | Settings, structured logging, OTel tracing, Prometheus metrics, SQLAlchemy UoW, Transactional Outbox + relay, Inbox dedup, RabbitMQ event bus, Keycloak JWT validator, correlation IDs | Per-service schemas, repositories |
| `fastapi/` | App factory, middleware, RFC 7807 exception handlers, health probes, role-based deps | Service routers |

## Import discipline

```
shared_kernel.domain        →  no dependencies on anything else here
shared_kernel.types         →  may depend on domain (they are value objects)
shared_kernel.application   →  may depend on domain
shared_kernel.infrastructure→  may depend on domain + application
shared_kernel.fastapi       →  may depend on any of the above
```

Violations of this direction are enforced by
[`tests/fitness/test_architecture.py`](tests/fitness/test_architecture.py).
