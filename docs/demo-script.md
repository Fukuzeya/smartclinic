# SmartClinic — Demo Script

**Duration:** 8–10 minutes core walkthrough  
**Audience:** Academic assessors, software architecture module  
**Seeded by:** `make seed` (creates Chipo, Tendai, Rudo with all required state)

---

## Setup checklist (before the demo)

```bash
make up          # start full stack (≈ 2 min first time)
make seed        # create demo patients, stock, appointments
```

Open tabs in advance:
| Tab | URL | Role |
|-----|-----|------|
| SmartClinic | http://localhost:4200 | — |
| RabbitMQ mgmt | http://localhost:15672 | admin / admin |
| Grafana | http://localhost:3000 | admin / admin |
| pgAdmin / psql | localhost:5433 | postgres |

---

## Section 1 — Architecture overview (2 min)

> *"SmartClinic solves a real problem in Zimbabwean private clinics: fragmented
> workflows where appointments, consultations, prescriptions, lab results, and
> billing live in silos. DDD is the right tool because each department speaks a
> different language about the same 'visit'."*

**Show `docs/arc42/architecture.md`** — point to:
- Six bounded contexts, each with its own microservice, schema, and language
- The context map: Patient Identity → Shared Kernel → all others
- The event-driven backbone: RabbitMQ + outbox/inbox pattern

**Show `docs/context-map.md`** — name each relationship type deliberately:
> *"Clinical is the upstream supplier; Billing is a conformist downstream consumer
> that auto-generates invoices from domain events without any coupling to the
> Clinical schema."*

---

## Section 2 — Happy path: full patient visit (3 min)

**Login as `receptionist1` / `receptionist1`**

1. **Patient list → Chipo Moyo** — show demographics, medical aid, visit history
2. **Appointments → today's list** — show Chipo's 09:00 slot as *checked in*
3. **Visit Tracker** — show saga step: `In Consultation`

**Login as `doctor1` / `doctor1`**

4. **Encounters → Chipo's encounter**
   - Show vitals panel (already recorded by seed)
   - Show SOAP note, diagnosis (J06.9), prescription (Amoxicillin + Paracetamol)
   - Show lab order (FBC)

5. **Event Timeline** (bottom of encounter detail page)
   > *"This is the event-sourced history. Every change to the encounter is an
   > immutable fact in `clinical_events`. The chain hash proves no event has
   > been silently modified — ADR 0012."*
   - Point to sequence numbers, event types, chain hash prefixes
   - Click **"Verify audit chain"** → show green `✓ Chain intact` badge
   - Explain: *"This is how medico-legal audit works in an event-sourced system.
   We can answer 'what did the record look like at 14:32?' by replaying only
   events up to that timestamp."*

**Login as `pharmacist1` / `pharmacist1`**

6. **Prescriptions → Chipo's prescription (pending)**
   - Show the **Specification Chain panel** on the right
     > *"The spec chain is composable: AllDrugsInStock ∧ PatientConsent ∧
     > NoSevereInteraction. Each spec is a pure class — no I/O. The ACL hits
     > RxNav *before* the spec runs. This is ADR 0006 + 0007."*
   - Click **"Dispense All"** → shows `✓ Dispensed`

**Login as `accounts1` / `accounts1`**

7. **Invoices → Chipo's invoice (auto-generated)**
   > *"Billing never asked Clinical for data. The `clinical.encounter.closed.v1`
   > event was consumed by the Billing context's inbox handler, which created a
   > DRAFT invoice and immediately issued it. No synchronous call, no shared DB."*
   - Show charge lines (consultation fee, lab fee)
   - Click **Record Payment** → invoice moves to PAID

**Visit Tracker** — show saga step `Completed` ✅

---

## Section 3 — Saga compensation: drug out of stock (2 min)

**Login as `pharmacist1` / `pharmacist1`**

1. **Prescriptions → Tendai Dube's prescription (pending)**
   - Click **"Dispense All"**
   - Show `✗ Dispensing blocked` — *"AllDrugsInStock specification fails: Warfarin not in dispensary"*
   - Highlight: *"The out_of_stock_drugs list is in the rejection event payload.
   The Saga Orchestrator picks this up."*

**Visit Tracker → Tendai's saga**

2. Show saga step: `⚠ Substitution Needed`
   > *"This is the compensating action. The saga emitted
   > `saga.patient_visit.substitution_required.v1`. In a production system, this
   > triggers a notification to the prescribing doctor. The saga remains active —
   > it's not cancelled. When the doctor issues a substitute prescription, the
   > saga resumes. This demonstrates saga compensation without rollback."*

---

## Section 4 — Event sourcing deep dive (1 min — optional)

Open pgAdmin or run:
```sql
\c clinical_write
SELECT sequence, event_type, occurred_at, chain_hash
FROM clinical_events
WHERE aggregate_id = '<Chipo encounter UUID>'
ORDER BY sequence;
```

> *"No `encounters` state table exists. The aggregate lives entirely in this
> append-only event log. Replay all events = current state. Replay events 1–3
> = state at 09:12. That's temporal query — free from event sourcing."*

Show `verify_chain` via:
```
GET /encounters/<uuid>/audit
```
→ `{ "is_valid": true, "event_count": 7, "message": "Chain of 7 events verified OK" }`

---

## Section 5 — Observability (30 s)

- **Grafana → http://localhost:3000** — show Prometheus metrics, Loki log stream, Jaeger trace for the prescription dispense call (trace spans across pharmacy service + outbox relay)
- > *"Correlation IDs flow from HTTP header through the domain layer to the event
  > store and outbox. One trace ID links the HTTP request, the domain event, the
  > outbox write, and the RabbitMQ publish. This is ADR 0008 + 0009."*

---

## Section 6 — AI Clinical Copilot (1 min)

**Login as `doctor1`**

- Open any encounter in progress
- Click **"AI: Draft SOAP"** button in the SOAP panel
- Show the generated SOAP skeleton from vitals + presenting complaint
  > *"The AI suggestion is clearly labelled, non-authoritative, and logged in
  > the `ai_suggestions` audit table separately from clinical facts. The
  > prescribing doctor must explicitly accept or discard it. The AI provider
  > is behind a port — swapping to a different model is a one-file change."*
- Show the drug-safety narrative panel on the prescription page
  > *"Rather than exposing raw spec violation strings, the copilot generates a
  > clinician-readable explanation: 'Warfarin + Aspirin have a SEVERE interaction
  > risk for bleeding — consider dose adjustment or alternative anticoagulant.'
  > The specification is still the enforcement gate; AI adds human readability."*

---

## Anticipated Q&A answers

| Question | Answer |
|---|---|
| Why event sourcing only in Clinical? | Medico-legal requirement — encounter records need immutable, temporally-queryable audit. The overhead is justified there; state-based aggregates suffice for simpler lifecycles (Invoice, Appointment). ADR 0003. |
| Why saga *orchestration* not choreography? | With 6 contexts, choreography produces implicit coupling via shared event sequences — adding a new step requires changes across multiple consumers. Orchestration externalises the lifecycle into a single testable aggregate. ADR 0005. |
| How does the ACL protect the domain? | RxNav returns `{ sourceName, severity: "high", interactionPair: [...] }`. None of that vocabulary enters the domain. The adapter maps `"high" → InteractionSeverity.SEVERE` and wraps it in a `DrugInteraction` VO. The domain never imports `httpx`. ADR 0007. |
| What's in the Shared Kernel? | Only things all contexts need and that change rarely: `Money`, `Identifier` types, `AggregateRoot`, `EventSourcedAggregateRoot`, `Specification`, `DomainEvent`, `Outbox`, `Inbox`, auth middleware, OTel wiring. No business logic. ADR 0010. |
| How do contexts stay independent? | Separate databases (one schema per context), no shared ORM models, all cross-context communication via RabbitMQ + outbox/inbox. An integration test with Postgres shows this: `SELECT * FROM clinical_events` fails from the billing connection by design. |
| What would break if you removed the Saga? | Pharmacy would still receive prescriptions and Billing would still auto-invoice — those are event-driven. The saga's role is to track the *correlated lifecycle* and handle compensation. Without it you lose OOS routing, payment status correlation, and cross-context cancellation. |
| How is the hash chain different from a transaction log? | A WAL/transaction log is an infrastructure artefact — writable by a DBA, not visible to the application, not part of the business model. Our chain is part of the *domain record*: it is computed by application code, stored in the same table as the event, and verifiable by any stakeholder with read access. |

---

## Demo flow cheat-sheet (print this)

```
make up && make seed

1. Receptionist → see Chipo checked in
2. Doctor → Chipo encounter → Event Timeline → Verify chain
3. Pharmacist → Dispense Chipo prescription → DISPENSED
4. Accounts → Pay Chipo invoice → PAID
5. Visit Tracker → COMPLETED

6. Pharmacist → Dispense Tendai prescription → BLOCKED (OOS Warfarin)
7. Visit Tracker → SUBSTITUTION REQUIRED (compensation branch)

8. Doctor → start SOAP note → AI Draft → accept/discard
9. Grafana → show trace + metrics
10. psql → show raw clinical_events table
```
