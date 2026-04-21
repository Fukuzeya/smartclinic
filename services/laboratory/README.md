# Laboratory — Bounded Context

## Responsibility

Fulfils lab tests ordered during encounters. Models specimen collection,
result recording, and abnormal-flag policy (the range a result is
considered "abnormal" is a domain concept — not presentation logic).
Aggregate root: `LabOrder`.

## Published Language

- `laboratory.order.accepted.v1`
- `laboratory.specimen.collected.v1`
- `laboratory.result.recorded.v1`
- `laboratory.result.amended.v1`

## Relationship to other contexts

| Peer                | Relationship          | Notes                                                      |
|---------------------|-----------------------|------------------------------------------------------------|
| Clinical            | Downstream ← Customer | Subscribes to `clinical.encounter.lab_ordered.v1`.         |
| Billing             | Upstream → Customer   | `laboratory.result.recorded.v1` feeds the invoice.         |

## Phase

Scaffolded in Phase 1; implemented in **Phase 6 — Laboratory**.
