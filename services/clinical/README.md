# Clinical — Bounded Context

## Responsibility

The **core domain**. Owns the electronic medical record: encounters,
clinical notes, vitals, diagnoses, prescriptions, lab orders and
allergies. Aggregate roots include `Encounter`, `ClinicalRecord`,
`Prescription` (as part of an Encounter), and `LabOrder` (as part of an
Encounter).

This context is **Event Sourced** and **CQRS** — see ADR-0003 and
ADR-0004. Every change to an aggregate is an immutable event; the read
model is a projection maintained by subscribing to its own events.

An **innovative extension** (ADR-0012) applies a **hash-chained,
tamper-evident** structure to the event store so any retroactive edit
is cryptographically detectable. This is a medico-legal win.

## Published Language

- `clinical.encounter.started.v1`
- `clinical.encounter.note_recorded.v1`
- `clinical.encounter.diagnosis_recorded.v1`
- `clinical.encounter.prescription_issued.v1`
- `clinical.encounter.lab_ordered.v1`
- `clinical.encounter.finalised.v1`

## Relationship to other contexts

| Peer                | Relationship          | Notes                                                              |
|---------------------|-----------------------|--------------------------------------------------------------------|
| Patient Identity    | Downstream ← Customer | Subscribes to `patient.*` to keep a patient read-model.            |
| Scheduling          | Downstream ← Customer | Consumes `scheduling.appointment.checked_in.v1` to start an encounter. |
| Pharmacy            | Upstream → Customer   | `prescription_issued` drives dispensing.                           |
| Laboratory          | Upstream → Customer   | `lab_ordered` drives fulfilment.                                   |
| Billing             | Upstream → Customer   | `encounter.finalised` triggers invoicing.                          |
| Saga Orchestrator   | Partner               | Participates in the Patient Visit saga.                            |

## Phase

Scaffolded in Phase 1; implemented in **Phase 4 — Clinical (Event Sourcing)**.
