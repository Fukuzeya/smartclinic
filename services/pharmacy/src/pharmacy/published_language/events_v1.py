"""Pharmacy published language — schemas for downstream contexts.

* ``DispensingCompletedV1`` → Billing: trigger prescription line items on invoice.
* ``DispensingRejectedV1`` → Scheduling (informational): flag for follow-up.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class DispensingCompletedPayloadV1(_Base):
    patient_id: str
    dispensed_by: str
    lines_dispensed: list[dict]


class DispensingRejectedPayloadV1(_Base):
    patient_id: str
    reasons: list[str]
    rejected_by: str
