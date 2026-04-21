# SmartClinic

An integrated clinic management platform for medium-sized private
clinics in Zimbabwe — built to demonstrate advanced Domain-Driven
Design on a realistic, production-shaped stack.

**Team**: TARUVINGA, KATONDO, FUKUZEYA.
**Course**: Masters — Software Architecture (2026).

---

## What it is

Six bounded contexts (Patient Identity, Scheduling, Clinical,
Pharmacy, Laboratory, Billing), plus a Saga Orchestrator, talking
over a RabbitMQ topic bus and running in isolation with their own
PostgreSQL databases. Each context is a FastAPI service; the
front-end is an Angular 20 SPA (Phase 3). Identity is handled by
Keycloak; observability by OpenTelemetry → Jaeger + Prometheus + Loki
rendered in Grafana.

The interesting bits:

- **Event Sourcing + CQRS** in the Clinical (core) context.
- **Hash-chained, tamper-evident** event store for the medical record.
- **Saga / Process Manager** for the end-to-end Patient Visit.
- **Specification Pattern** for pharmacy dispensing rules.
- **Anti-Corruption Layer** around the RxNav drug database.
- **Transactional Outbox + Idempotent Inbox** as the reliability spine.
- **Architectural fitness functions** enforced in CI.

The full design is in [docs/](docs/); twelve decisions are recorded
as MADR ADRs in [docs/adr/](docs/adr/).

---

## Quickstart

### Prerequisites

| Tool            | Version      | Notes                                              |
|-----------------|--------------|----------------------------------------------------|
| Docker Desktop  | 4.32+        | WSL2 back-end on Windows.                          |
| uv              | 0.4+         | Python package and workspace manager.              |
| Python          | 3.12+        | Used by `uv` for local tests.                      |
| make            | GNU Make     | On Windows: `choco install make` or use WSL.       |

### Bring up the stack

```bash
# Infrastructure only (fast: Postgres, RabbitMQ, Keycloak, obs stack).
make up

# Full: also starts scaffolded bounded-context services (slower).
docker compose --profile full up -d

# Stop everything.
make down
```

First boot takes ~60–90 s — Keycloak imports its realm on startup.
Follow progress with `make logs`.

### Useful URLs once the stack is up

| Service               | URL                                                  |
|-----------------------|------------------------------------------------------|
| Grafana               | <http://localhost:3000>   (admin / admin)            |
| Prometheus            | <http://localhost:9090>                              |
| Jaeger UI             | <http://localhost:16686>                             |
| RabbitMQ management   | <http://localhost:15672>  (smartclinic / smartclinic)|
| Keycloak admin        | <http://localhost:8080>   (admin / admin)            |
| MailHog               | <http://localhost:8025>                              |

### Run the shared-kernel tests

```bash
uv sync
make test        # unit + integration tests
make fitness     # architectural fitness functions
make lint        # ruff
make typecheck   # mypy (strict on shared_kernel)
```

---

## Repository layout

```
SmartClinic/
├── libs/
│   └── shared_kernel/        # domain primitives + cross-cutting infra
├── services/                 # one directory per bounded context
│   ├── patient_identity/
│   ├── scheduling/
│   ├── clinical/
│   ├── pharmacy/
│   ├── laboratory/
│   ├── billing/
│   └── saga_orchestrator/
├── ops/                      # prod-like local stack config
│   ├── postgres/             # per-context init SQL
│   ├── rabbitmq/             # topology (exchanges, DLX, queues, bindings)
│   ├── keycloak/             # realm + roles + test users
│   ├── otel-collector/       # OTLP fan-out config
│   ├── prometheus/           # scrape config
│   ├── grafana/              # provisioned datasources + dashboards
│   └── loki/                 # single-binary log aggregator
├── docs/                     # Arc42, context map, QA scenarios, ADRs, …
├── docker-compose.yml        # the prod-like stack
├── docker-compose.override.yml # dev ergonomics (bind-mount + --reload)
├── pyproject.toml            # uv workspace root
└── Makefile
```

---

## Phased delivery

The project is built in phases. The user confirms acceptance between
phases so quality is always demonstrable, never claimed.

| Phase | Deliverable                                                           | Status         |
|-------|-----------------------------------------------------------------------|----------------|
| 1     | Shared Kernel + infrastructure + docs + ADRs (this)                   | **Current**    |
| 2     | Patient Identity bounded context (CRUD + events + outbox)             | Next           |
| 3     | Scheduling bounded context + Angular SPA spine                        | Planned        |
| 4     | Clinical — Event Sourcing + CQRS + hash chain                         | Planned        |
| 5     | Pharmacy — Specification Pattern + ACL to RxNav                       | Planned        |
| 6     | Laboratory                                                             | Planned        |
| 7     | Billing                                                                | Planned        |
| 8     | Saga Orchestrator — end-to-end Patient Visit                          | Planned        |
| 9     | Deployment + CI/CD + CI-run fitness gate                              | Planned        |

---

## Where to go next

- Read [docs/context-map.md](docs/context-map.md) for the system
  shape.
- Read [docs/arc42/architecture.md](docs/arc42/architecture.md) for
  the full architectural spec.
- Read [docs/adr/](docs/adr/) for the *why* behind every pattern.
- Poke around [libs/shared_kernel/](libs/shared_kernel/) — that is
  the concrete Phase 1 deliverable.

---

## Licence

Academic project; not licensed for production use without review.
