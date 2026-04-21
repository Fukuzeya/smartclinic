# Scheduling — Bounded Context

## Responsibility

Owns the **appointment lifecycle**: booking, rescheduling, cancellation,
check-in, and no-show reconciliation. Aggregate root is `Appointment`.
Clinician calendars and room/resource availability are modelled here.

## Published Language

- `scheduling.appointment.booked.v1`
- `scheduling.appointment.rescheduled.v1`
- `scheduling.appointment.cancelled.v1`
- `scheduling.appointment.checked_in.v1`
- `scheduling.appointment.no_show.v1`

## Relationship to other contexts

| Peer                | Relationship            | Notes                                                           |
|---------------------|-------------------------|-----------------------------------------------------------------|
| Patient Identity    | Downstream ← Customer   | Subscribes to `patient.*` to validate `PatientId` references.   |
| Clinical            | Upstream → Partnership  | `scheduling.appointment.checked_in.v1` triggers an encounter.   |
| Saga Orchestrator   | Upstream → Partnership  | Drives the Patient Visit saga from check-in onward.             |

## Phase

Scaffolded in Phase 1; implemented in **Phase 3 — Scheduling**.
