# Patient Identity — Bounded Context

## Responsibility

The Patient Identity context is the **system of record for patients**. It owns:

- Patient registration and demographic profile.
- National ID validation (Zimbabwean format).
- Unique, immutable `PatientId` assignment (UUIDv7).
- Contact details (email, phone, next-of-kin).
- Consent flags (POPIA-equivalent data-processing consent).

Everything downstream (Scheduling, Clinical, Pharmacy, Laboratory, Billing)
treats `PatientId` as an opaque reference; only this context is allowed
to **create** a `Patient` or mutate demographic data.

## Published Language

- `patient.registered.v1`
- `patient.demographics_updated.v1`
- `patient.consent_granted.v1`
- `patient.consent_revoked.v1`

(Event payload schemas live under `src/patient_identity/published_language/`.)

## Relationship to other contexts

| Peer         | Relationship          | Notes                                                              |
|--------------|-----------------------|--------------------------------------------------------------------|
| Scheduling   | Upstream → Customer   | Scheduling subscribes to `patient.*` to keep its read-model fresh. |
| Clinical     | Upstream → Customer   | Clinical subscribes to `patient.*` for encounter display.          |
| Billing      | Upstream → Customer   | Billing subscribes to capture payer/contact details on invoices.   |

## Phase

This context is **scaffolded** in Phase 1 (shared-kernel + infrastructure).
Business logic, aggregates, repositories and HTTP handlers will be built
in **Phase 2 — Patient Identity**, once the Shared Kernel is accepted.
