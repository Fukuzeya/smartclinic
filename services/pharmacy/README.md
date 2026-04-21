# Pharmacy — Bounded Context

## Responsibility

Dispenses prescriptions written by the Clinical context and keeps a
minimal stock/inventory model. Runs **clinical decision support** for
drug–drug interactions and allergy conflicts via a rules engine built
on the **Specification Pattern** (ADR-0006).

An **Anti-Corruption Layer** (ADR-0007) shields the domain from the
external drug/interaction database (RxNav), translating its shape into
the local `Medication` value object.

Aggregate root: `DispensingOrder`.

## Published Language

- `pharmacy.dispensing.rejected.v1`        (with reasons from specs)
- `pharmacy.dispensing.partially_filled.v1`
- `pharmacy.dispensing.completed.v1`
- `pharmacy.stock.replenished.v1`

## Relationship to other contexts

| Peer                | Relationship                          | Notes                                                      |
|---------------------|---------------------------------------|------------------------------------------------------------|
| Clinical            | Downstream ← Customer                 | Subscribes to `clinical.encounter.prescription_issued.v1`. |
| Billing             | Upstream → Customer                   | `pharmacy.dispensing.completed.v1` feeds the invoice.      |
| Drug Database (ext) | Conformist-via-ACL (Anti-Corruption) | RxNav shape translated at boundary into our `Medication`.  |

## Phase

Scaffolded in Phase 1; implemented in **Phase 5 — Pharmacy**.
