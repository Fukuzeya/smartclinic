# SmartClinic — Ubiquitous Language

> A term may mean different things in different bounded contexts.
> That is not a bug — it is the whole point of bounded contexts.
> This file documents the canonical meaning **per context**. A term
> with no entry in a context does not exist there.

## Cross-cutting (Shared Kernel)

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Aggregate**        | A consistency boundary around a cluster of entities and value objects. One aggregate, one transaction, one save.       |
| **Aggregate root**   | The single entity through which the aggregate is accessed.                                                             |
| **Value object**     | An immutable model element defined solely by its attribute values; has no id.                                          |
| **Domain event**     | Immutable fact that something meaningful happened; past tense; carries `event_type` and versioned schema.              |
| **Published Language** | The set of event names, routing keys and payload shapes published on the bus. Contract between contexts.             |
| **Specification**    | Boolean predicate over a domain object that knows its own name and `explain()`s failure.                               |
| **Outbox**           | A DB table written inside the same transaction as an aggregate; the event relay reads from it and publishes.           |
| **Inbox**            | A DB table keyed by `(event_id, consumer)`; inserting first makes event handling idempotent.                           |
| **Correlation ID**   | Per-request identifier; propagated as a header, injected into logs and OTel baggage.                                   |
| **Causation ID**     | The `event_id` of the event that *caused* the current event (or command).                                              |

## Patient Identity

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Patient**          | A registered natural person known to the clinic. Aggregate root.                                                       |
| **Patient ID**       | Opaque, immutable UUIDv7 assigned on registration. The only cross-context handle.                                      |
| **National ID**      | Zimbabwean identity document (format `NN-NNNNNNN[A-Z]-NN`); validated at registration.                                 |
| **Demographics**     | Name, date of birth, sex, address, contacts.                                                                           |
| **Consent**          | POPIA-equivalent data-processing consent; booleans with timestamp of grant/revoke.                                     |
| **Next of kin**      | A contact separate from the patient; not an entity in its own right.                                                   |

## Scheduling

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Appointment**      | A scheduled meeting between a patient and a clinician. Aggregate root.                                                 |
| **Slot**             | A booked interval in a clinician's calendar; includes room/resource allocation.                                        |
| **Check-in**         | Receptionist acknowledgement that the patient has arrived; triggers the start of an Encounter in Clinical.             |
| **No-show**          | An appointment reached its start time without check-in.                                                                |
| **Reschedule**       | Moving an appointment to a new slot.                                                                                   |

## Clinical (core)

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Encounter**        | A single clinician-patient contact — the unit of clinical work. Aggregate root.                                        |
| **Clinical note**    | Free-text narrative recorded during an Encounter.                                                                      |
| **Vital**            | A typed measurement (blood pressure, pulse, temp, SpO₂) with unit and reference range.                                 |
| **Diagnosis**        | An ICD-10 coded conclusion recorded in an Encounter.                                                                   |
| **Prescription**     | A request to dispense medication; belongs to an Encounter.                                                             |
| **Lab order**        | A request for a laboratory investigation; belongs to an Encounter.                                                     |
| **Finalise**         | Closing an Encounter for edits; triggers billing.                                                                      |
| **Event stream**     | The append-only ordered log of all events against a single aggregate id.                                               |
| **Chain hash**       | SHA-256 over the canonical event payload plus the previous event's hash; see ADR-0012.                                 |

> Note: `Appointment` does **not** exist in Clinical. The Encounter is
> created as a reaction to `scheduling.appointment.checked_in.v1` but
> carries only its own identity and a link to the upstream event.

## Pharmacy

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Dispensing Order** | The pharmacy's response to a Prescription from Clinical. Aggregate root.                                               |
| **Medication**       | Our internal value-object for a drug (name, ingredients, strength). Translated from RxNav via the ACL.                 |
| **Interaction**      | A known pharmacological interaction between two medications.                                                           |
| **Allergy**          | A patient sensitivity to an ingredient, carried in the patient read-model.                                             |
| **Dispensing decision** | The result of evaluating a Specification composition over a Dispensing Order.                                       |

## Laboratory

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Lab Order**        | A laboratory's record of a clinical lab order being fulfilled. Aggregate root.                                         |
| **Specimen**         | A physical sample collected from a patient; state-tracked within a Lab Order.                                          |
| **Result**           | A measured value with a reference range and an abnormality flag computed by domain policy.                             |
| **Amendment**        | A corrected Result — appended, never in-place.                                                                         |

## Billing

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Invoice**          | The bill for one Patient Visit. Aggregate root.                                                                        |
| **Line item**        | A charge originating in Clinical, Pharmacy or Laboratory.                                                              |
| **Payment**          | An amount received against an Invoice. Aggregate root.                                                                 |
| **Payer**            | Who pays — patient, medical aid, employer, sponsor.                                                                    |
| **Overdue**          | Invoice past due-date with non-zero balance.                                                                           |

## Saga Orchestrator

| Term                 | Definition                                                                                                             |
|----------------------|------------------------------------------------------------------------------------------------------------------------|
| **Patient Visit**    | The end-to-end process from check-in to invoice settlement — the saga's unit of work.                                  |
| **Compensating command** | A command that undoes the effect of a previous step upon downstream failure (e.g., `CancelPrescription`).          |
| **Saga state**       | The process manager's machine state (`awaiting_encounter`, `dispensing_pending`, `awaiting_payment`, `completed`).     |

## Why these differences matter

"Encounter" in Clinical is not "Appointment" in Scheduling; "Patient"
in Patient Identity is not "Patient" in Billing (Billing holds only
a cached projection with `Invoice`-shaped details). The contexts
refuse to share the words because they refuse to share the models.
This is the whole apparatus of bounded contexts and published
language in one table.
