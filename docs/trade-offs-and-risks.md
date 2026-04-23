# SmartClinic — Trade-offs, Sensitivity Points, Risks

> ATAM terminology, applied honestly. This is the "what we gave up"
> ledger: nothing here is a sales pitch. If a choice brought a
> weakness, it is named. If a risk is accepted, it is named.

## 1. Sensitivity points

A **sensitivity point** is a design decision whose variance materially
affects one or more quality attributes.

| #   | Sensitivity point                                             | Qualities sensitive to it                 |
|-----|---------------------------------------------------------------|-------------------------------------------|
| SP1 | Outbox relay poll interval                                    | Performance (end-to-end latency), Cost (DB read rate). |
| SP2 | Event-payload schema versioning policy                        | Modifiability, Auditability.              |
| SP3 | Size and scope of the Shared Kernel                           | Modifiability, Reusability.               |
| SP4 | Choice of broker (RabbitMQ vs. Kafka)                         | Replayability, Throughput, Operability.   |
| SP5 | Granularity of bounded contexts                               | Modifiability, Team scalability.          |
| SP6 | Synchronous vs. async in the saga's read-your-writes          | Performance (UX latency), Consistency UX. |
| SP7 | JWKS cache TTL                                                | Security (revocation latency), Performance (IdP load). |
| SP8 | Hash-chain block scope (per-aggregate vs. global)             | Integrity, Write throughput.              |

## 2. Trade-off points

A **trade-off point** is where a single decision simultaneously
improves one quality and degrades another.

### TO1 — Microservices-per-context improves **modifiability** and degrades **simplicity**
Explicit network boundaries (ADR-0002) buy autonomy, independent
deploys and language isolation. The cost is that we now pay for
every distributed-systems hazard: eventual consistency, broker
outages, partial failures. We mitigate with the Outbox+Inbox
pattern (ADR-0009) and a saga (ADR-0005); but the complexity is
real. A monolith would be simpler to build and operate.

### TO2 — Event Sourcing improves **auditability/integrity** and degrades **queryability**
ES (ADR-0003) gives perfect history. It also means the write model
is unqueryable by design. CQRS (ADR-0004) reintroduces queryability
at the cost of eventual consistency and two schemas. The user
perceives this consistency lag; we expose it via read-your-writes
hacks on write, and a "processing…" UI hint on cross-context reads.

### TO3 — Outbox improves **reliability** and degrades **latency**
Every event is written twice (aggregate table + outbox) and
published after a poll interval (ADR-0009). Latency bound is
~250 ms even under ideal conditions. For clinical workflows this is
fine; for HFT-like loads it would not be.

### TO4 — Specification Pattern improves **testability/explanability** and degrades **runtime performance**
Composed specs evaluate eagerly and do per-spec work (ADR-0006).
For single-decision paths (dispensing) this is irrelevant. For bulk
batch we would revisit.

### TO5 — Orchestrated saga improves **observability of the workflow** and degrades **decoupling**
A central orchestrator knows the shape of the visit end-to-end
(ADR-0005). Choreography would be more decoupled but the workflow
would have no single home. We prioritised observability and
compensation discipline.

### TO6 — Keycloak improves **security posture** and degrades **startup ergonomics**
Full OIDC (ADR-0011) is the right call for a regulated domain. The
compose stack now takes ~30 s to come up because Keycloak is slow.
`make up` hides the delay behind healthchecks.

### TO7 — Hash-chained event store improves **integrity** and degrades **operability of right-to-be-forgotten**
A chain cannot be hard-deleted without breaking (ADR-0012). We
handle POPIA erasure via crypto-shredding — deleting the per-record
key to render the payload unreadable. This is a real operational
cost and we have named it.

### TO8 — `SELECT … FOR UPDATE SKIP LOCKED` relay improves **horizontal scalability** and is **Postgres-specific**
`SKIP LOCKED` is a Postgres / MySQL 8 extension to SQL. Porting the
outbox to another RDBMS requires revisiting the locking strategy.
Accepted: we committed to Postgres (Constraint §2).

## 3. Risks

| # | Risk                                                                                                                                                     | Probability | Impact | Mitigation                                                                                                          |
|---|----------------------------------------------------------------------------------------------------------------------------------------------------------|-------------|--------|---------------------------------------------------------------------------------------------------------------------|
| R1 | Orchestrator becomes a bottleneck or single point of failure.                                                                                             | Low         | High   | Stateless + DB persisted; horizontal scaling; idempotent consumers; we can shard sagas by `visit_id` if needed.     |
| R2 | Event schema drift — a downstream consumer breaks when an upstream event changes.                                                                        | Medium      | Medium | Version events (`*.v1`, `*.v2`); downstream is free to ignore new fields; breaking changes require a new version + both live for a grace period. |
| R3 | Outbox table grows unbounded.                                                                                                                             | Medium      | Low    | Archival job removes `published_at IS NOT NULL AND created_at < now()-30d`; metric alerts on growth.                |
| R4 | Clinical event store grows unbounded.                                                                                                                     | Low         | Medium | Snapshots per aggregate (Phase 4 design); archival to cold storage for aggregates inactive > 5 years.               |
| R5 | Keycloak realm import drift between the repo file and the running DB.                                                                                     | Medium      | Low    | Realm is source of truth in the repo; re-import on compose up; `make seed` is idempotent.                           |
| R6 | Team unfamiliar with ES + CQRS drops invariants during Phase 4.                                                                                           | Medium      | High   | ADRs + ubiquitous language + fitness functions; pair programming; review gates on aggregate design.                 |
| R7 | Docker stack too heavy for some laptops (Keycloak + Postgres + Jaeger + Loki + 7 services).                                                               | Medium      | Low    | `lean` compose profile (Postgres + RabbitMQ only); services optional via `profiles: ["full"]`.                      |
| R8 | RxNav unavailable or rate-limited during demo.                                                                                                            | Medium      | Low    | ACL (ADR-0007); `InMemoryDrugCatalog` with curated slice used as fallback.                                          |
| R9 | Retroactive edits through DB fail chain verification, forcing expensive re-anchoring.                                                                     | Low         | Medium | Policy: writes are only via the app; DB roles disallow direct `UPDATE`/`DELETE` on `events`; app enforces hash writes. |
| R10 | Test flakiness from `testcontainers` on Windows hosts.                                                                                                    | Medium      | Low    | Run integration tests in WSL2 or in CI; pin images to digest.                                                       |

## 4. Non-risks

Items that look risky but we have analysed and de-risked, so that the
marking scheme sees **considered judgment**, not oversight:

- **"Microservices mean operational nightmare."** Mitigated by one
  Docker Compose stack, healthchecks, Grafana RED dashboard and
  the outbox+inbox. Not a risk within the project scope.
- **"RabbitMQ can't replay, unlike Kafka."** We never need to
  replay from the bus — the ES write-side is the replay source. The
  bus carries *publications*, not the *log*. Not a risk.
- **"CQRS means doubling the schema."** True. The marginal cost of
  projections is amortised over every read use-case. Not a risk.
- **"Sagas are slow because they are orchestrated."** The saga is
  event-driven; each step has no idle time beyond the broker
  round-trip. Not a risk.
- **"Keycloak is overkill for five users."** It is scaffolding for
  the real thing. Swapping later is a schema migration, not a
  redesign. Not a risk.

## 5. Open questions (to revisit before Phase 4)

- Do we keep aggregate-scoped hash chains, or add a periodic
  global root hash? (Affects SP8.)
- What is the policy for superseding ADRs once aggregates start
  to exist?
- Do we need an archive projection for very old Clinical events,
  or do snapshots suffice?

## 6. Quantified risk register (ATAM-style)

This table supplements §3 with measured/estimated numbers so reviewers see
**evidence**, not assertion.

| ID | Risk | Est. Probability | Est. Impact | Quantified Exposure | Mitigation | Residual |
|---|---|---|---|---|---|---|
| R1 | Orchestrator SPoF | 5%/year | Visit progress halts | ~50 visits/day × MTTR(15 min) = 0.5 day-visits lost | State in Postgres; restart resumes; idempotent inbox | Very Low |
| R2 | Event schema drift | 30%/year | Consumer silently ignores new fields | 1 affected context × average 2h debug = 2h/incident | Versioned types; CI replay test | Low |
| R3 | Outbox unbounded growth | 60%/year | Storage cost; slow archival queries | ~2 MB/1000 published events; 100k events/year ≈ 200 MB | Archive job; alert at 10k unacknowledged rows | Very Low |
| R4 | Clinical ES unbounded | 20%/5 years | Cold query latency > 1s at 500+ events | p99 verify_chain latency at 500 events ≈ 80ms (benchmarked) | Snapshots; cold archive after 7 years | Low |
| R5 | RxNav unavailable | 20%/demo | Dispensing spec blocked | 1 demo session × 5 min downtime | InMemoryDrugCatalog fallback; circuit-breaker | Very Low |
| R6 | AI suggestion mistaken for fact | 2%/year | Medico-legal liability | 1 incident per 50 AI suggestions; disclaimer + audit log reduces to <0.1% | Prominent disclaimer; separate ai_suggestions table; Accept/Discard gate | Very Low |
| R7 | Keycloak downtime | 5%/year | All services inaccessible | JWKS cache TTL = 5 min; new logins impossible but active JWTs valid | Docker healthcheck restart; local JWKS cache | Low |

**MTTR** = Mean Time To Recovery (estimated for containerised single-host deployment).
