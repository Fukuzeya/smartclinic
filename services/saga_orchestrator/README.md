# Saga Orchestrator

## Responsibility

Runs the **Patient Visit** process manager, co-ordinating the end-to-end
flow across bounded contexts:

```
Scheduling.CheckedIn
   ↓
Clinical.EncounterStarted
   ↓
(Clinical.PrescriptionIssued → Pharmacy.DispensingCompleted)*
(Clinical.LabOrdered          → Laboratory.ResultRecorded   )*
   ↓
Clinical.EncounterFinalised
   ↓
Billing.InvoiceIssued
   ↓
Billing.InvoicePaid  →  VisitCompleted (terminal)
```

This is **orchestration** (a central co-ordinator), not choreography —
see ADR-0005 for the trade-off. The saga is its own aggregate:
`PatientVisitSaga`, state-machine persisted, optimistically concurrent.
On any step failure the saga runs compensating commands (e.g.
`CancelDispensing`, `VoidInvoice`).

This service does **not** own domain data — it owns only the workflow
state and the compensation map.

## Published Language

The saga consumes the published languages of every upstream context and
emits only:

- `saga.patient_visit.started.v1`
- `saga.patient_visit.completed.v1`
- `saga.patient_visit.compensated.v1`

## Phase

Scaffolded in Phase 1; implemented in **Phase 8 — Saga Orchestration**.
