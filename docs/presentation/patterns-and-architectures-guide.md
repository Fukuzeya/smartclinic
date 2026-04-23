# SmartClinic — Patterns & Architectures Used, Feature-by-Feature

> Companion to [`ilograph-architecture.md`](ilograph-architecture.md).
> Structured to match the **marking scheme**:
> Problem Context → Pattern Selection → Architecture Views → Quality Attributes
> → Trade-offs / Risks → Prototype / Tests → DevOps / Observability →
> Security / Compliance → Documentation / ADRs. Everything here is traceable
> to working code and to an ADR in `docs/adr/`.

---

## 0. Marking scheme → section map (read this first)

| Marking area | Covered in § |
|---|---|
| Problem Context & Requirements | §1, §2 |
| Architectural Pattern Selection & Justification | §3 (strategic), §4 (tactical), §5 (integration), §6 (per feature) |
| Architecture Design & Views | `ilograph-architecture.md` + §7 |
| Quality Attribute Scenarios & Tactics | §8 (mapped to ATAM QAS) |
| Trade-offs, Alternatives & Risks (ATAM) | §9 |
| Prototype, Testing & Evaluation | §10 |
| DevOps, Deployment & Observability | §11 |
| Security, Privacy & Compliance | §12 |
| Documentation, ADRs & Governance | §13 |
| Presentation, Demo, Q&A | §14 |

---

## 1. Problem we are solving (concretely)

Private clinics in Zimbabwe operate with fragmented software:
appointments disconnected from consultations, prescriptions invisible
to the pharmacy until the patient walks over, billing done
retroactively, lab results tracked on paper. The root cause is that
clinic software is usually built as a **single-model monolith**, but
clinic operations are actually a network of autonomous domains that
each speak a different language about the same patient:

| Role | What "a visit" means to them |
|---|---|
| Receptionist | A calendar slot |
| Doctor | A clinical encounter |
| Pharmacist | A dispensing trigger |
| Accounts | A billable event |

This semantic mismatch is exactly the complexity DDD was designed to
tame. **SmartClinic** therefore uses **Advanced DDD** as the
organising principle for the entire platform.

## 2. Scope of the prototype

Six bounded contexts, one saga, one shared kernel, one Angular 20 SPA,
one AI clinical copilot, full three-pillar observability, GitHub
Actions CI/CD, AWS as the production target.

---

# PART A — Architectural patterns in use

## 3. Strategic DDD patterns

### 3.1 Bounded Contexts (ADR-0002)
- **What:** Six microservices — `patient_identity`, `scheduling`,
  `clinical`, `pharmacy`, `laboratory`, `billing` (plus the
  `saga_orchestrator`).
- **Why:** Each domain has its own ubiquitous language, lifecycle, and
  invariants. Sharing a single model would cause the semantic mismatch
  described in §1.
- **Enforcement:** CI fitness function
  `libs/shared_kernel/tests/fitness/test_architecture.py` asserts no
  cross-context imports — the context map is executable.

### 3.2 Subdomain classification (Evans ch. 15)
- **Core:** Clinical. This is where we spend architectural capital
  (Event Sourcing, CQRS, hash-chain, AI copilot).
- **Supporting:** Patient Identity, Scheduling. Necessary but not
  differentiating — lean models.
- **Generic:** Pharmacy, Laboratory, Billing. Could in principle be
  replaced with an off-the-shelf product; they hide behind clean
  contracts so substitution is possible.

### 3.3 Context Map — all six DDD relationship types
Every edge type from Evans part IV appears at least once:
- **Partnership:** Scheduling ↔ Clinical (check-in → encounter).
- **Customer-Supplier (Upstream / Downstream):** Patient Identity →
  Scheduling / Clinical / Billing; Clinical → Pharmacy / Laboratory /
  Billing; Pharmacy / Laboratory → Billing.
- **Conformist:** All contexts → Keycloak (we adopt its claim shape
  without influence).
- **Anti-Corruption Layer:** Pharmacy ↔ RxNav (ADR-0007).
- **Shared Kernel:** `libs/shared_kernel` — jointly owned, narrow,
  governed (ADR-0010).
- **Published Language:** Event schemas `<context>.<entity>.<event>.v<N>`
  on the RabbitMQ topic exchange (ADR-0008).
- **Open Host Service:** Each context's OIDC-protected REST API.

### 3.4 Published Language (ADR-0008)
Versioned event contracts in each service's `published_language/`
package (e.g. `services/clinical/src/clinical/published_language/events_v1.py`).
The `.v1` suffix makes backwards-compatible evolution explicit.

### 3.5 Anti-Corruption Layer (ADR-0007)
Pharmacy treats RxNav's vocabulary (`rxcui`, `tty`) as foreign. The
`DrugInteractionPort` domain interface has a single `RxNavClient`
adapter translating upstream concepts into Pharmacy's ubiquitous
language. Rationale in ADR-0007; code in
`services/pharmacy/src/pharmacy/acl/`.

### 3.6 Shared Kernel (ADR-0010)
The **narrowest possible** jointly-owned module — only AggregateRoot,
ValueObject, Entity, DomainEvent, Specification base class, Outbox,
Inbox, Event Bus adapter, Keycloak JWT validator, logging/tracing/metrics
wiring, and FastAPI factory with RFC 7807 problem+json. Changes require
cross-team review.

## 4. Tactical DDD patterns

### 4.1 Aggregates + invariants
- **Encounter** (Clinical) is the keystone aggregate — event-sourced,
  enforces rules like "cannot issue a prescription without a diagnosis".
- **Appointment** (Scheduling) enforces no-overlap and lead-time rules.
- **Dispensing** (Pharmacy) enforces the full Specification chain.
- **Invoice** (Billing) enforces tariff + medical-aid adjudication.

### 4.2 Value Objects
Immutable, self-validating: `ICD10Code`, `Dosage`, `Money`, `VitalReading`,
`NationalId`, `PersonName`, `EmailAddress`, `PhoneNumber`, `TimeSlot`,
`PatientId`. Most live in `libs/shared_kernel/src/shared_kernel/types/`.

### 4.3 Entities (non-aggregate)
Inside aggregates — e.g. `PrescriptionLine` inside `Encounter`,
`DispensingLine` inside `Dispensing`, `InvoiceLineItem` inside
`Invoice`.

### 4.4 Domain Events (ADR-0003 contract)
Every state change is a domain event. Inside the aggregate they are
emitted via `self._raise(event)`; infrastructure picks them up via the
Unit of Work and writes them atomically to Postgres (aggregate table
or event-store table) **and** the outbox. Published Language version
is part of the class name / routing key.

### 4.5 Domain Services
Stateless operations spanning multiple entities:
- `DrugInteractionService` (Pharmacy) — composes specifications.
- `TariffCalculationService` (Billing) — computes line items from
  different event types.

### 4.6 Specification Pattern (ADR-0006)
Composable boolean rules with an explicit failure reason.
`services/pharmacy/src/pharmacy/domain/specifications.py`:
- `NotAllergic`, `NoSevereInteraction`, `NotDuplicateTherapy`,
  `WithinMaxDailyDose`, `StockAvailable`.
- `.and_(other)`, `.or_(other)`, `.not_()` combinators.
- `evaluate(candidate) -> Result[Success | Violations]`.

Also used in Scheduling (`SlotAvailable`, `NoOverlap`, `WithinOpeningHours`)
and Billing (`EligibleForMedicalAid`).

### 4.7 Repository Pattern + Unit of Work
- `Repository[T]` protocol in `shared_kernel.domain.repository`.
- Postgres implementations per context in `infrastructure/repository.py`.
- `SqlAlchemyUnitOfWork` guarantees that aggregate persistence + outbox
  write happen in the same transaction.

### 4.8 Result / Either type
`shared_kernel.domain.result.Result[T, E]` — explicit success/failure
in the domain without exceptions for control flow. Keeps the happy
path readable.

### 4.9 Factories
Aggregates are created via class-method factories (`Encounter.start(...)`,
`Invoice.issue_from_events(...)`) so that invariants hold from the
first event. No "naked constructor" leaks partially-formed aggregates.

## 5. Integration & resilience patterns

### 5.1 Event-Driven Architecture (choreography + orchestration)
- **Choreography by default:** services react to events.
- **Orchestration for multi-step workflows:** Saga Orchestrator owns
  the Patient Visit shape end-to-end (ADR-0005).

### 5.2 Saga / Process Manager (ADR-0005)
Stateful, durable, deterministic transitions. Listens to every
context's events on a wildcard queue `saga.all.events`. On failure
(stock-out, payment decline, no-show) triggers **compensating
actions** — e.g., `notify-doctor-for-substitution`, `refund-invoice`,
`cancel-encounter`.

### 5.3 Transactional Outbox + Inbox (ADR-0009)
- **Outbox**: events are written to an `outbox` table inside the same
  DB transaction as aggregate state. A relay process polls with
  `SELECT … FOR UPDATE SKIP LOCKED` and publishes to RabbitMQ.
- **Inbox**: consumers persist `(message_id, consumer_group)` before
  handling, achieving exactly-once **effect** on at-least-once
  delivery.
- Together these solve the "dual write" problem.

### 5.4 Dead Letter Exchange + Retry TTL
Declared in `ops/rabbitmq/definitions.json`. Poison messages go to a
parking-lot queue with retry TTL + max-delivery-count so one bad
message cannot block the consumer.

### 5.5 Idempotency
Every consumer is idempotent by construction: the Inbox de-duplicates,
the aggregate's optimistic-concurrency `expected_version` rejects
stale updates, and HTTP command endpoints accept an
`Idempotency-Key` header.

## 6. Per-feature patterns map

### 6.1 Patient registration (Patient Identity)
- **Patterns:** Aggregate (Patient), Value Objects (NationalId,
  PersonName, Phone, Email), Repository, Outbox.
- **Event:** `patient.registered.v1` — downstream builds a local
  read-model; nobody writes back (Customer-Supplier).

### 6.2 Appointment booking & conflict detection (Scheduling)
- **Patterns:** Aggregate (Appointment), Specification chain
  (`SlotAvailable ∧ NoOverlap ∧ WithinOpeningHours ∧ LeadTimeRespected`),
  Repository, Outbox.
- **Event:** `scheduling.appointment.booked.v1` / `.checked_in.v1`.
- **Partnership** with Clinical: `.checked_in.v1` opens an encounter.

### 6.3 Clinical encounter — the core
- **Event Sourcing (ADR-0003):** Every change is an event; the
  aggregate is the fold of its events.
- **CQRS (ADR-0004):** Write side enforces invariants, read side is
  denormalised (EncounterSummaryView, PrescriptionListView) for fast
  UI queries.
- **Hash-chained event store (ADR-0012) — INNOVATION:** Each event
  row carries `prev_hash` + `hash = sha256(canonical_json(...))`.
  Any retroactive edit detected by `verify_chain(aggregate_id)` in
  O(events).
- **Periodic anchor:** Daily head-hash published as
  `clinical.integrity.anchor.v1`.

### 6.4 Prescription issuance & dispensing (Pharmacy)
- **Specification Pattern** for dispensing gate:
  `NotAllergic ∧ NoSevereInteraction ∧ NotDuplicateTherapy ∧
   WithinMaxDailyDose ∧ StockAvailable`.
- **Anti-Corruption Layer** for RxNav (ADR-0007).
- **Reliable event flow** via Outbox/Inbox — even if RabbitMQ is down,
  the dispensing action completes and the downstream event is eventually
  published.

### 6.5 Laboratory (Lab orders & results)
- **Aggregate** LabOrder; state machine `Requested → Sampled → Reported`.
- Emits `laboratory.result.recorded.v1` with abnormal-flag
  (Specification: `WithinReferenceRange`).

### 6.6 Billing (auto-invoice)
- **Event-driven invoice generation** — Billing subscribes to three
  streams and composes invoice lines from
  `clinical.encounter.finalised.v1` + `pharmacy.dispensing.completed.v1` +
  `laboratory.result.recorded.v1`.
- **Domain Service** `TariffCalculationService`.
- **Specification Pattern** for medical-aid adjudication.
- **Money VO** with currency-aware arithmetic (no floating-point).

### 6.7 Patient Visit Saga
- **Process Manager.** State machine with compensations.
- Observability: every saga transition is a span; the full visit trace
  is one Jaeger view.

### 6.8 AI Clinical Copilot (ADR-0013) — INNOVATION
- **Hexagonal Ports & Adapters:** `ClinicalCopilotPort` in
  `shared_kernel.ai.copilot_port`; `AnthropicClinicalCopilot` and
  `MockClinicalCopilot` adapters; `build_copilot()` factory chooses
  based on `ANTHROPIC_API_KEY`.
- **Audit separation:** AI text stored in a separate `ai_suggestions`
  table — **never** in the hash-chained `clinical_events`. Preserves
  medico-legal integrity.
- **Graceful degradation:** no API key → mock returns deterministic
  stubs; CI stays offline.

## 7. Architecture styles / patterns above the DDD layer

| Style | Where applied |
|---|---|
| **Microservices (one context = one service)** | All six bounded contexts |
| **Event-Driven Architecture (topic exchange)** | Cross-context integration |
| **Hexagonal / Ports & Adapters** | Inside every service; explicit in ACL, Copilot |
| **Clean / Onion layering** | api → application → domain; infrastructure → {application, domain} |
| **CQRS** | Clinical & Billing |
| **Event Sourcing** | Clinical (core) |
| **Backend-for-Frontend (light)** | Angular SPA talks to each service directly via path-routed ALB; no god-gateway — Angular's feature modules encapsulate the per-context API shape |
| **Saga / Process Manager** | Patient Visit |
| **Strangler-safe**: the ACL means we could migrate any Generic context to a COTS product without touching the core |

---

# PART B — Engineering quality

## 8. Quality Attribute Scenarios (ATAM style)

Every QAS is a six-part scenario (Source / Stimulus / Artifact /
Environment / Response / Measure). Full set in
`docs/quality-attribute-scenarios.md`. The table below ties each
scenario to the **tactic(s)** delivering it.

| # | Quality attribute | Scenario headline | Tactics |
|---|---|---|---|
| 1 | Integrity | Tamper with a past clinical event → detected in O(events) | Hash-chained append-only log + periodic anchor (ADR-0012); `SELECT … FOR UPDATE` during writes |
| 2 | Availability | Pharmacy keeps serving while Clinical is down | Async messaging; durable queues; idempotent inbox consumers (ADR-0008/0009) |
| 3 | Availability | Broker outage does not lose events | Transactional outbox relay; retries with exponential back-off |
| 4 | Performance | prescription-issued → dispensing ≤ 2 s p95 | Poll interval tuned to 250 ms; JSON payload; durable-publish persistent class |
| 5 | Modifiability | New bounded context = zero changes elsewhere | Published Language; topic exchange; Shared Kernel contracts |
| 6 | Modifiability | Swap RxNav for a local formulary = touch only the ACL | Anti-Corruption Layer (ADR-0007) |
| 7 | Auditability | Full encounter history reconstructed from events alone | Event Sourcing (ADR-0003) |
| 8 | Security | Expired / tampered tokens rejected at every boundary | Offline JWKS validation with short TTL; `require_role` dependency |
| 9 | Testability | Architectural rules enforced in CI | Fitness functions (import-linter + pytest); architecture is code |
| 10 | Observability | Failing request's trace + logs + metrics cross-linked in 30 s | OTel + Jaeger + Prometheus + Loki + Grafana (datasource correlation) |

## 9. Trade-offs, sensitivity points, risks (ATAM)

| Trade-off | Gained | Paid |
|---|---|---|
| Microservices per context (ADR-0002) | Modifiability, team scalability | Distributed-systems complexity (outbox, inbox, saga) |
| Event Sourcing (ADR-0003) | Auditability, integrity | Queryability (fixed with CQRS ADR-0004) |
| Outbox (ADR-0009) | Reliability | Extra write + poll latency (~250 ms) |
| Specification pattern (ADR-0006) | Testability, explanability | Eager evaluation cost — OK for per-decision paths |
| Orchestrated saga (ADR-0005) | Workflow observability | Less decoupled than choreography |
| Keycloak (ADR-0011) | Security posture, SSO | Stack startup time (~30 s) |
| Hash-chain (ADR-0012) | Integrity | Cannot hard-delete; crypto-shredding required for POPIA erasure |
| `SKIP LOCKED` outbox relay | Horizontal scalability | Postgres/MySQL-8 specific |

**Sensitivity points** (design knobs that move multiple qualities at
once): outbox poll interval, event-schema versioning policy, shared
kernel scope, broker choice (Rabbit vs Kafka), saga sync-vs-async UX,
JWKS cache TTL, hash-chain block scope. All documented in
`docs/trade-offs-and-risks.md`.

**Top risks & mitigations:**
- *Saga bottleneck:* stateless, DB-persisted, shardable by `visit_id`.
- *Clock skew on hash-chain:* only event ordering matters; hash anchors
  make absolute time a best-effort signal.
- *Event schema drift:* `.vN` suffix + compatibility tests in CI.
- *RxNav unavailability:* ACL has a circuit breaker + "advisory-only"
  degradation.

## 10. Prototype, testing, evaluation

### Test pyramid
- **Unit tests** — pure domain rules (aggregates, VOs, specifications).
  No Docker, no network.
- **Contract / architecture fitness tests** — enforce ADR rules (no
  cross-context imports, no domain → infrastructure, no API → domain).
- **Integration tests** — testcontainers spin up Postgres + RabbitMQ,
  exercise outbox relay, inbox idempotency, hash-chain verifier, full
  saga happy + compensation path.
- **Stack smoke test** — `docker compose up` infra profile with
  readiness probes.

### Evaluation artefacts
- Working end-to-end demo (§14).
- Quantified trade-off table in ADR-0013 for the AI feature.
- Metrics dashboard in Grafana covering p50/p95/p99 + saturation.
- Load test script `test_api.py` used to warm the read models and
  compare read vs write p95.

## 11. DevOps, deployment, observability

### 11.1 GitHub Actions pipeline (`.github/workflows/ci.yml`)
Jobs, top to bottom:
1. **Lint** — ruff check + ruff format.
2. **Typecheck** — `mypy --strict` on shared kernel; mypy on services.
3. **Unit tests** — pytest across the workspace.
4. **Architecture fitness** — context-map rules enforced.
5. **Integration tests** — testcontainers.
6. **Docker build matrix** — 7 service images + frontend, cached.
7. **Stack smoke test** — `docker compose` infra profile.
8. **Image push** — OIDC-federated to AWS ECR (no long-lived secrets).
9. **Deploy** — CodeDeploy blue/green rolling update on ECS Fargate.

Concurrency group cancels stale runs per ref. Required checks block
merge on `main`.

### 11.2 Container & deployment topology
- **Dev/demo:** `docker compose up` — Postgres, RabbitMQ, Keycloak,
  Jaeger, Prometheus, Loki, OTel Collector, Grafana, MailHog, 7
  services, Angular SPA.
- **Prod (AWS):**
  - Route 53 + ACM → CloudFront (WAF) → SPA
  - ALB → ECS Fargate tasks (one service per task definition)
  - RDS PostgreSQL (multi-AZ, PITR)
  - Amazon MQ (RabbitMQ engine) replaces self-hosted broker
  - Secrets Manager + KMS for secrets and envelope encryption
  - SES for outbound email
  - CloudWatch for container logs + alarms
  - IAM OIDC trust with GitHub — **zero long-lived keys**
- **Parity:** compose → Fargate mapping is one-to-one; identical
  environment-variable shape; adapter differences (MailHog vs SES,
  RabbitMQ vs Amazon MQ) hidden behind Shared Kernel ports.

### 11.3 Observability — three pillars, correlated
- **Traces (Jaeger):** OTLP from every service through the OTel
  Collector. The outbox publish span carries `causation_id` +
  `correlation_id`.
- **Metrics (Prometheus):** `prometheus-client` in every service, plus
  RabbitMQ's Prometheus plugin, Keycloak metrics endpoint, and Postgres
  exporter (production only). Exemplars link metric spikes back to a
  trace.
- **Logs (Loki):** `structlog` JSON with `trace_id`, `span_id`,
  `service`, `correlation_id`, `actor_id`.
- **Grafana:** single pane with `traceToMetrics` + `tracesToLogs`
  wired through the provisioned datasources
  (`ops/grafana/provisioning/datasources/datasources.yml`).
- **Alerting:** AlertManager rules on SLO breach → SES / PagerDuty.

## 12. Security, privacy & compliance

### Authentication & authorisation
- Keycloak OIDC (ADR-0011). PKCE public client in Angular.
- Every service validates JWT offline against cached JWKS (short TTL).
- Role extraction from `realm_access.roles`; FastAPI
  `require_role("doctor")` dependency per handler.

### Data protection
- **PII confinement:** PII lives in `patient_identity`. Other contexts
  hold only `PatientId` references plus minimal denormalised
  demographic fields.
- **Secrets:** dev → `.env.example` sentinels; prod → Secrets Manager
  with rotation; KMS keys for envelope encryption of sensitive
  columns.
- **Transport:** HTTPS + HSTS in prod; WAF with OWASP rules in front
  of CloudFront.
- **Audit:** every state-changing event carries `actor_id` and a
  trace context — who did what, when, why is reconstructable from the
  event log alone (QAS-7).

### Regulatory (POPIA-equivalent, medico-legal)
- **Integrity:** hash-chained event store (ADR-0012).
- **Right-to-be-forgotten:** events cannot be hard-deleted (chain
  would break); we implement **crypto-shredding** — payloads encrypted
  with a per-record KMS key; deleting the key renders them
  unrecoverable while keeping the chain intact.
- **Retention:** controlled at the projection layer; the authoritative
  event log retains indefinitely (medico-legal duty of care).
- **AI governance:** ADR-0013 — every AI suggestion is stored with
  model id, timestamp, disclaimer, and the clinician's Accept/Discard
  decision. Satisfies HIPAA/WHO AI audit-trail expectations.

## 13. Documentation, ADRs & governance

- **arc42** architecture document: `docs/arc42/architecture.md`.
- **Thirteen ADRs** in `docs/adr/` — every major choice traceable:
  `0002` bounded contexts, `0003` event sourcing, `0004` CQRS, `0005`
  saga, `0006` specification, `0007` ACL, `0008` RabbitMQ, `0009`
  outbox/inbox, `0010` shared kernel, `0011` Keycloak, `0012`
  hash-chain, `0013` AI copilot port.
- **Context map:** `docs/context-map.md`.
- **Ubiquitous language glossary:** `docs/ubiquitous-language.md`.
- **Quality attribute scenarios:** `docs/quality-attribute-scenarios.md`.
- **Trade-offs & risks:** `docs/trade-offs-and-risks.md`.
- **Security & compliance:** `docs/security-and-compliance.md`.
- **Governance of the Shared Kernel:** joint code review; dependency
  change is a cross-team PR.

## 14. Presentation & demo plan

### Story arc (10 minutes)
1. **Problem** (1 min) — semantic mismatch in clinic software, §1.
2. **Strategy** (1 min) — DDD bounded contexts + event bus. Show
   Ilograph *Perspective 1 — Context Map*.
3. **Zoom into the core** (2 min) — *Perspective 2 — Hexagonal*, then
   play *Perspective 3 — Event Sourcing + CQRS* animation.
4. **Workflow coordination** (1.5 min) — play *Perspective 4 — Saga*.
   Show compensation.
5. **Live demo** (2 min) — book → check-in → consult → drug-interaction
   block → substitute → dispense → auto-invoice → pay → saga completed.
6. **DevOps/Observability** (1 min) — click through *Perspective 8 —
   DevOps Walkthrough*; show live Grafana with a real trace.
7. **Security/integrity** (0.5 min) — *Perspective 9*; run
   `verify_chain` on a tampered row live.
8. **Innovation** (0.5 min) — *Perspective 10 — AI Copilot Port* +
   one-line provider swap.
9. **Close** (0.5 min) — trade-off table from §9; recap ADR count and
   fitness tests.

### Q&A ammunition
- *"Why not Kafka?"* — operability/throughput trade-off in §9;
  RabbitMQ wins on ops simplicity for our scale; topic exchange gives
  us 95 % of Kafka's routing.
- *"Isn't Event Sourcing overkill?"* — only for the Core; Supporting &
  Generic use plain state. Medico-legal requirement makes it cost-
  justified here.
- *"How do you version events?"* — `.vN` in routing key and class name;
  compatibility test in CI rejects breaking changes.
- *"How do you roll back a bad deploy?"* — blue/green with automatic
  rollback on ALB health-check + CloudWatch alarm.
- *"How do you handle POPIA erasure when events are immutable?"* —
  crypto-shredding via KMS key deletion.
- *"What happens if Anthropic is down?"* — factory falls back to
  `MockClinicalCopilot`; feature degrades gracefully.

---

## Quick pattern-to-code index

| Pattern | Representative file(s) |
|---|---|
| AggregateRoot | `libs/shared_kernel/src/shared_kernel/domain/aggregate_root.py` |
| Event-sourced aggregate | `libs/shared_kernel/src/shared_kernel/domain/event_sourced_aggregate.py`, `services/clinical/.../domain/encounter.py` |
| Value Object | `libs/shared_kernel/src/shared_kernel/domain/value_object.py`, `libs/shared_kernel/src/shared_kernel/types/*` |
| Specification | `libs/shared_kernel/src/shared_kernel/domain/specification.py`, `services/pharmacy/.../domain/specifications.py` |
| Repository | `libs/shared_kernel/src/shared_kernel/domain/repository.py` |
| Unit of Work | `libs/shared_kernel/src/shared_kernel/infrastructure/sqlalchemy_uow.py` |
| Outbox / Inbox | `libs/shared_kernel/src/shared_kernel/infrastructure/{outbox,inbox}.py` |
| Event bus (AMQP) | `libs/shared_kernel/src/shared_kernel/infrastructure/event_bus.py` |
| Published Language | `services/<context>/src/<context>/published_language/events_v1.py` |
| Anti-Corruption Layer | `services/pharmacy/src/pharmacy/acl/` |
| Saga / Process Manager | `services/saga_orchestrator/src/saga_orchestrator/domain/patient_visit_saga.py` |
| Event Sourcing write store | `services/clinical/src/clinical/infrastructure/event_store.py` |
| CQRS projections | `services/clinical/src/clinical/infrastructure/projections.py` |
| Hexagonal port (AI) | `libs/shared_kernel/src/shared_kernel/ai/copilot_port.py` |
| OIDC validator | `libs/shared_kernel/src/shared_kernel/infrastructure/security.py` |
| RFC 7807 errors | `libs/shared_kernel/src/shared_kernel/fastapi/exception_handlers.py` |
| Correlation / tracing | `libs/shared_kernel/src/shared_kernel/infrastructure/{correlation,tracing}.py` |
| Structured logging | `libs/shared_kernel/src/shared_kernel/infrastructure/logging.py` |
| Prometheus metrics | `libs/shared_kernel/src/shared_kernel/infrastructure/metrics.py` |
| Fitness functions | `libs/shared_kernel/tests/fitness/test_architecture.py` |
| GitHub Actions | `.github/workflows/ci.yml` |
| Compose stack | `docker-compose.yml` |

---

## Appendix — headline patterns scorecard

| Marking-scheme criterion | Our evidence |
|---|---|
| **Pattern selection justified?** | 13 ADRs, each with considered options + decision outcome + trade-offs |
| **All DDD relationship types?** | Yes — Partnership, Customer-Supplier, Conformist, ACL, Shared Kernel, Published Language |
| **Multiple architecture views?** | 10 Ilograph perspectives + arc42 §3–§7 + context map |
| **ATAM thinking?** | 10 QAS with tactics; trade-offs + sensitivity points + risks |
| **Working prototype?** | `docker compose up` → seeded demo end-to-end; Grafana live |
| **DevOps maturity?** | 9-job GitHub Actions pipeline; OIDC-federated AWS deploy; blue/green |
| **Observability?** | Three correlated pillars + AlertManager + SLO rules |
| **Security & compliance?** | Keycloak OIDC, WAF, KMS, hash-chain, crypto-shredding, audit trail |
| **Innovation?** | Hash-chained tamper-evident event store (ADR-0012); AI copilot under a hexagonal port (ADR-0013) |
| **Documentation?** | arc42 + 13 ADRs + context map + QAS + trade-offs + glossary |
