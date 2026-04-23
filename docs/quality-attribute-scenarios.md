# SmartClinic — Quality Attribute Scenarios

> ATAM-style, six-part scenarios: **Stimulus / Source / Artifact /
> Environment / Response / Measure**. Each scenario names the
> tactics that deliver it, linking to ADRs or to code where the
> tactic is applied. This is the bridge from "quality goals" to
> "architecture choices" — what the marking scheme is actually
> asking about.

## Summary

| #  | Quality attribute | Scenario headline                                                                |
|----|-------------------|----------------------------------------------------------------------------------|
| 1  | Integrity         | Any tamper with a past clinical event is detected in O(events).                  |
| 2  | Availability      | Pharmacy keeps dispensing queueable while Clinical is down.                      |
| 3  | Availability      | Broker outage does not lose published events.                                    |
| 4  | Performance       | Prescription-issued → dispensing-handler end-to-end ≤ 2 s at p95.                |
| 5  | Modifiability     | Adding a new bounded context requires zero changes to existing contexts.         |
| 6  | Modifiability     | Swapping RxNav for a local formulary touches only the ACL implementation.        |
| 7  | Auditability      | Full reconstruction of an encounter's history from the event log alone.          |
| 8  | Security          | Expired / tampered tokens are rejected at every API boundary.                    |
| 9  | Testability       | Architectural rules are enforced in CI (no cross-context imports, etc.).         |
| 10 | Observability     | A failing request's trace, logs and metrics are cross-linkable within 30 s.      |

---

## QAS-1 — Integrity (tamper-evident clinical history)

| Part            | Value                                                                                                                                                      |
|-----------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Malicious or compromised actor with direct DB access.                                                                                                     |
| **Stimulus**    | UPDATE on a historical row in the Clinical `events` table.                                                                                                |
| **Artifact**    | Clinical event store.                                                                                                                                     |
| **Environment** | Any time post-commit.                                                                                                                                     |
| **Response**    | `verify_chain(aggregate_id)` walks the stream; the `hash` of the tampered event no longer matches the `prev_hash` reference in the next event; detection. |
| **Measure**     | O(events in stream). Zero false positives on an untampered stream. Zero false negatives once one hash is edited.                                          |

**Tactics.** Hash-chained append-only log with periodic external
anchor (ADR-0012); crypto-shredding for right-to-be-forgotten
cases; `SELECT … FOR UPDATE` on latest event during writes.

---

## QAS-2 — Availability (Pharmacy survives Clinical downtime)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Clinical service is stopped (crash, deploy, network partition).                                                                 |
| **Stimulus**    | Pharmacist attempts to open / filter / complete dispensing orders already queued.                                               |
| **Artifact**    | Pharmacy service + RabbitMQ.                                                                                                    |
| **Environment** | Weekday business hours.                                                                                                         |
| **Response**    | Pharmacy continues to serve existing dispensing orders (already received into its queue). New prescriptions accumulate in the RabbitMQ queue until Clinical comes back; no messages lost. |
| **Measure**     | 0 messages lost during a 30-minute Clinical outage. Pharmacy error rate unchanged.                                              |

**Tactics.** Loose coupling through async messaging (ADR-0008); durable queues with policy `ha-and-ttl` (see `ops/rabbitmq/definitions.json`); idempotent consumers (Inbox, ADR-0009).

---

## QAS-3 — Availability (broker outage does not drop events)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | RabbitMQ is down or unreachable.                                                                                                |
| **Stimulus**    | Patient is registered in Patient Identity during the outage.                                                                    |
| **Artifact**    | Patient Identity service + its outbox table.                                                                                    |
| **Environment** | Normal write traffic.                                                                                                           |
| **Response**    | Aggregate commit succeeds; event rows land in the outbox. The relay retries publish with exponential backoff. When RabbitMQ recovers, relay drains. |
| **Measure**     | Zero events lost. Outbox-lag metric rises during outage and decays when broker returns; alerts fire if lag > 60 s for > 5 min.  |

**Tactics.** Transactional Outbox with relay (ADR-0009); publisher confirms; metric `smartclinic_outbox_lag_seconds`.

---

## QAS-4 — Performance (prescription → dispensing handler)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Doctor finalising a prescription at an encounter.                                                                               |
| **Stimulus**    | `POST /encounters/{id}/prescriptions`.                                                                                          |
| **Artifact**    | Clinical (write), outbox relay, RabbitMQ, Pharmacy subscriber.                                                                  |
| **Environment** | Normal load (≤ 10 concurrent doctors).                                                                                          |
| **Response**    | Prescription appears as a dispensing order in Pharmacy.                                                                         |
| **Measure**     | p95 ≤ 2 s. Budget: Clinical commit ≤ 200 ms; outbox poll ≤ 250 ms; broker + consumer ≤ 1 500 ms.                                |

**Tactics.** Short poll interval on outbox (`poll_interval_seconds=0.25`); prefetch ≥ 10 on consumers; async handlers throughout; no N+1s in write path (enforced by SQLAlchemy logging in dev).

---

## QAS-5 — Modifiability (adding a new bounded context)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Architect introducing a new context (e.g., "Radiology").                                                                        |
| **Stimulus**    | Design document for new context approved.                                                                                       |
| **Artifact**    | Monorepo.                                                                                                                        |
| **Environment** | Development.                                                                                                                     |
| **Response**    | New `services/radiology/` scaffolded from template; subscribes to `clinical.encounter.imaging_ordered.v1`; zero lines changed in existing context code. |
| **Measure**     | Hours, not days. CI fitness tests keep passing.                                                                                 |

**Tactics.** Shared Kernel for cross-cutting primitives (ADR-0010); Published Language via topic bus (ADR-0008); import-direction fitness functions (`libs/shared_kernel/tests/fitness/test_architecture.py`).

---

## QAS-6 — Modifiability (swap RxNav for a local formulary)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Product decision to source drug data from Zimbabwe's MOHCC formulary.                                                           |
| **Stimulus**    | PR to replace `RxNavDrugCatalog`.                                                                                               |
| **Artifact**    | Pharmacy service — specifically `infrastructure/drug_catalog/`.                                                                 |
| **Environment** | Development.                                                                                                                    |
| **Response**    | A new class implements `DrugCatalog` against the new source. No domain, application or API code changes.                        |
| **Measure**     | Pharmacy domain tests pass unchanged. Integration tests pointed at the new implementation.                                      |

**Tactics.** Anti-Corruption Layer + port/adapter (ADR-0007).

---

## QAS-7 — Auditability (reconstruct an encounter)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Regulator requests full history of encounter E for patient P.                                                                   |
| **Stimulus**    | `GET /audit/encounters/{id}`.                                                                                                   |
| **Artifact**    | Clinical write-side event store.                                                                                                |
| **Environment** | Any time.                                                                                                                       |
| **Response**    | Response is the ordered event log of the Encounter aggregate, plus `verify_chain` result.                                       |
| **Measure**     | 100% of state at any point in time reproducible from events alone; `verify_chain` returns OK.                                   |

**Tactics.** Event Sourcing (ADR-0003); hash chain (ADR-0012).

---

## QAS-8 — Security (invalid tokens rejected at boundary)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Attacker with stolen / expired JWT or a crafted token.                                                                          |
| **Stimulus**    | Any `Authorization: Bearer <token>` request.                                                                                    |
| **Artifact**    | Any FastAPI service.                                                                                                            |
| **Environment** | Keycloak online.                                                                                                                |
| **Response**    | Signature mismatch, `iss`/`aud`/`exp` violation or missing role ⇒ 401 or 403 with RFC 7807 body; handler not invoked.           |
| **Measure**     | 100% of invalid tokens rejected. `auth_rejected_total` metric attributes by reason.                                             |

**Tactics.** OIDC + JWKS offline validation with TTL cache (ADR-0011); `require_role` dependency; RFC 7807 responses.

---

## QAS-9 — Testability (architecture enforced by fitness functions)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Developer submitting a PR.                                                                                                      |
| **Stimulus**    | A domain module imports `sqlalchemy`, or a service imports another service.                                                     |
| **Artifact**    | `libs/shared_kernel/tests/fitness/test_architecture.py` (runs in CI).                                                           |
| **Environment** | CI.                                                                                                                             |
| **Response**    | Test fails. PR cannot merge.                                                                                                    |
| **Measure**     | Rule violation is caught before merge in 100% of cases (modulo test correctness).                                               |

**Tactics.** AST-based import-graph checks; the same approach can add further rules.

---

## QAS-10 — Observability (trace / logs / metrics correlated)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | On-call engineer looking at a 5xx incident.                                                                                     |
| **Stimulus**    | A failed request's `trace_id` is known from the UI response header.                                                             |
| **Artifact**    | Grafana + Jaeger + Loki.                                                                                                         |
| **Environment** | Stack running.                                                                                                                  |
| **Response**    | Engineer enters the trace_id in Jaeger → full span tree visible; clicks a span → Loki opens filtered logs; clicks a log → metric exemplar jump. |
| **Measure**     | < 30 s to go from symptom to the failing log line.                                                                              |

**Tactics.** OTLP ingestion (`ops/otel-collector/config.yaml`); `derivedFields` on Loki; `tracesToLogsV2` on Jaeger (`ops/grafana/provisioning/datasources/datasources.yml`); exemplar linking on Prometheus histograms.

---

---

## QAS-11 — AI Copilot non-repudiation (ADR-0013)

| Part            | Value                                                                                                                           |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| **Source**      | Compliance auditor querying whether AI was used in clinical decision-making.                                                     |
| **Stimulus**    | Request for all AI interactions involving encounter E.                                                                          |
| **Artifact**    | `ai_suggestions` table in the Clinical database.                                                                                |
| **Environment** | Any time post-encounter.                                                                                                        |
| **Response**    | Query returns all suggestions: model used, timestamp, text, and clinician decision (accepted/discarded with `decided_by` and `decided_at`). |
| **Measure**     | 100% of AI suggestions auditable; zero AI suggestions appear in `clinical_events`.                                              |

**Tactics.** Provider Port (ADR-0013); separate `ai_suggestions` table; `RecordAIDecisionCommand` gate; disclaimer banner in UI.

---

## Quantified SLO targets

These are the targets against which the architecture is designed. They are not
SLAs — no external commitment is made — but they guide capacity and trade-off
decisions.

| Scenario | Metric | Target | Budget allocation |
|---|---|---|---|
| QAS-4: prescription → dispensing | p95 end-to-end latency | ≤ 2 000 ms | Clinical write ≤ 200ms; outbox poll ≤ 250ms; RabbitMQ + Pharmacy consumer ≤ 1 500ms |
| QAS-1: chain verification | p95 verify_chain latency (≤ 50 events) | ≤ 80 ms | SHA-256 over 50 × 512-byte payloads ≈ 2ms; DB read ≤ 70ms |
| QAS-8: token validation | p99 auth middleware overhead | ≤ 2 ms | JWKS cached; no network call on hot path |
| QAS-2: pharmacy during Clinical outage | Pharmacy availability | ≥ 99.5% | Async only; RabbitMQ HA queue |
| QAS-3: outbox during broker outage | Event loss | 0 events | Transactional outbox + idempotent consumers |
| QAS-11: AI suggestion response | p95 AI endpoint latency | ≤ 3 000 ms | Anthropic Haiku p95 ≈ 1 500ms; DB write ≤ 100ms; overhead ≤ 400ms |

## RTO / RPO targets

| Failure scenario | RTO (Recovery Time) | RPO (Recovery Point) | Mechanism |
|---|---|---|---|
| Single service crash | < 30 s | 0 (no state in-process) | Docker healthcheck restart; outbox re-drains |
| Postgres crash | < 2 min | 0 (WAL; committed transactions preserved) | Docker volume; pg_wal retained 5 min |
| RabbitMQ crash | < 1 min | 0 (durable queues + outbox) | Docker restart; outbox relay re-publishes unacknowledged rows |
| Keycloak crash | < 30 s | 0 (realm in Postgres) | Docker healthcheck; active JWTs still valid for remaining TTL |
| Full stack restart | < 3 min | 0 | `make up`; DB volumes persisted |

**Note**: RPO = 0 for committed transactions is achievable only because every
domain state change is a database write (either to the event store or to CRUD
tables) before any event is published. In-flight in-memory state has never been
the source of truth.

## Where tactics meet code

| Tactic                                   | Code                                                                                                                  |
|------------------------------------------|-----------------------------------------------------------------------------------------------------------------------|
| Async messaging                          | [libs/shared_kernel/src/shared_kernel/infrastructure/event_bus.py](../libs/shared_kernel/src/shared_kernel/infrastructure/event_bus.py) |
| Outbox + relay                           | [libs/shared_kernel/src/shared_kernel/infrastructure/outbox.py](../libs/shared_kernel/src/shared_kernel/infrastructure/outbox.py) |
| Inbox / idempotency                      | [libs/shared_kernel/src/shared_kernel/infrastructure/inbox.py](../libs/shared_kernel/src/shared_kernel/infrastructure/inbox.py) |
| JWT validation                           | [libs/shared_kernel/src/shared_kernel/infrastructure/security.py](../libs/shared_kernel/src/shared_kernel/infrastructure/security.py) |
| Fitness functions                        | [libs/shared_kernel/tests/fitness/test_architecture.py](../libs/shared_kernel/tests/fitness/test_architecture.py)      |
| RFC 7807 mapping                         | [libs/shared_kernel/src/shared_kernel/fastapi/exception_handlers.py](../libs/shared_kernel/src/shared_kernel/fastapi/exception_handlers.py) |
| OTel setup                               | [libs/shared_kernel/src/shared_kernel/infrastructure/tracing.py](../libs/shared_kernel/src/shared_kernel/infrastructure/tracing.py) |
| Metrics                                  | [libs/shared_kernel/src/shared_kernel/infrastructure/metrics.py](../libs/shared_kernel/src/shared_kernel/infrastructure/metrics.py) |
