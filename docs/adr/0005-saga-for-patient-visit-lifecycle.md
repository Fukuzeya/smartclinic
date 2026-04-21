# ADR-0005 — Saga for the Patient Visit lifecycle

- Status: Accepted
- Date: 2026-04-11
- Deciders: TARUVINGA, KATONDO, FUKUZEYA
- Tags: process-manager, saga, cross-context

## Context and Problem Statement

A single patient visit crosses every bounded context: check-in
(Scheduling) → encounter (Clinical) → dispensing (Pharmacy) → lab
fulfilment (Laboratory) → invoicing (Billing) → payment. This is a
**long-running, multi-step, cross-context workflow** with failure
semantics at every hop — there is no distributed transaction that
fits. And we have a business requirement: *if dispensing fails
because a drug is out of stock, the issued prescription must be
cancelled and the encounter flagged*.

## Decision Drivers

- No 2PC across six services (ADR-0002); we need compensation, not
  rollback.
- Each step is asynchronous; the workflow must survive restarts.
- We need to **observe** the workflow (where is the visit right now?).
- The marking scheme explicitly rewards the Saga pattern.

## Considered Options

1. **Choreography** — each service reacts to upstream events; no
   central co-ordinator.
2. **Orchestration** — a dedicated Process Manager (`PatientVisitSaga`
   aggregate) drives the flow.
3. **Hybrid** — choreography for the happy path, orchestration only
   for compensation.
4. **Distributed transactions (2PC / XA)** — not on the table with
   RabbitMQ + Postgres.

## Decision Outcome

Chosen option: **Option 2 — Orchestration**, implemented in the
`saga_orchestrator` service.

### Positive Consequences
- Workflow state is **one aggregate**, one row, one place to query.
  The "where is visit V?" question has a single answer.
- Compensation logic is centralised — the map of {event → compensating
  command} is visible and reviewable.
- The saga log itself is a valuable audit trail of the visit.
- Timeouts and dead-letter handling live in one place.

### Negative Consequences
- The orchestrator is a central point — its failure halts *new*
  transitions. Mitigations: (i) state is persisted, so restart resumes;
  (ii) idempotent consumers (ADR-0009) mean no data loss on restart;
  (iii) the orchestrator is stateless-plus-DB and scales horizontally.
- Orchestrator knows the domain shapes of many contexts — a *mild*
  coupling accepted explicitly.

## Pros and Cons of the Options

### Choreography
- Good, because each service only knows its neighbours.
- Good, because the most loosely coupled option.
- Bad, because the *workflow itself* is nowhere in code — it exists
  only as an emergent property of reactions.
- Bad, because cross-cutting concerns (timeout, retry, compensation)
  get duplicated in every service.

### Orchestration
- Good, because explicit state machine in the domain model.
- Good, because compensation is first-class.
- Bad, because mild coupling to the aggregate shapes being co-ordinated.

### Hybrid
- Good, because pragmatic.
- Bad, because harder to teach and reason about — two control planes.

### 2PC
- Bad, because not viable with RabbitMQ.
- Bad, because even if it were, it is operationally awful and blocks
  on slow participants.

## Compensating commands (initial map)

| Originating failure                             | Compensation                                   |
|-------------------------------------------------|------------------------------------------------|
| `pharmacy.dispensing.rejected.v1`               | `CancelPrescription` on Clinical               |
| `laboratory.order.cancelled.v1`                 | Note the failure in the encounter; continue    |
| `billing.invoice.payment_failed` (future)       | `IssueReminder` (no structural rollback)       |
| Encounter finalisation timeout (> 24h open)     | `ForceCloseEncounter`, flag for review         |

## Links
- ADR-0002, ADR-0009.
- Garcia-Molina & Salem 1987, "Sagas".
- Richardson, "Microservices Patterns" — ch. 4 (Saga), ch. 5 (Process Manager).
