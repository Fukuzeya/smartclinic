# Billing — Bounded Context

## Responsibility

Produces and collects on invoices. Aggregates consultation fees from
Clinical, dispensing line-items from Pharmacy and lab fees from
Laboratory into a single `Invoice` aggregate. Supports multi-currency
(USD / ZWL) via the shared `Money` value object.

Aggregate roots: `Invoice`, `Payment`.

## Published Language

- `billing.invoice.issued.v1`
- `billing.invoice.paid.v1`
- `billing.invoice.overdue.v1`
- `billing.payment.received.v1`
- `billing.payment.refunded.v1`

## Relationship to other contexts

| Peer             | Relationship          | Notes                                                              |
|------------------|-----------------------|--------------------------------------------------------------------|
| Clinical         | Downstream ← Customer | Consumes `clinical.encounter.finalised.v1`.                        |
| Pharmacy         | Downstream ← Customer | Consumes `pharmacy.dispensing.completed.v1`.                       |
| Laboratory       | Downstream ← Customer | Consumes `laboratory.result.recorded.v1`.                          |
| Saga Orchestrator| Partner               | Finalises the Patient Visit saga once the invoice is settled.      |

## Phase

Scaffolded in Phase 1; implemented in **Phase 7 — Billing**.
