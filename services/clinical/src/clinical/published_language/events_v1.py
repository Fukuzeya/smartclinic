"""Clinical published language — schemas shared with downstream contexts.

These Pydantic models define the **stable contract** that Pharmacy, Billing,
and Laboratory contexts depend on.  They carry only the fields needed by
downstream subscribers; full clinical detail (SOAP notes, vital-sign readings)
stays inside the Clinical context and is never broadcast.

Versioning policy: add new *optional* fields freely.  Removing or renaming
fields requires a new event version (e.g. ``EncounterClosedV2``) with a
transition period where both versions are published in parallel.

``extra="allow"`` on every schema is deliberate: subscribers that have not yet
been deployed to support a new optional field will still accept the message
without crashing.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)


class EncounterStartedPayloadV1(_Base):
    """Payload of ``clinical.encounter.started.v1``.

    Used by: Laboratory context (pre-population of expected orders),
    Billing context (opens an in-progress encounter billing record).
    """

    patient_id: str
    doctor_id: str
    appointment_id: str | None = None
    started_by: str


class EncounterClosedPayloadV1(_Base):
    """Payload of ``clinical.encounter.closed.v1``.

    This is the primary cross-context integration event:
    * **Pharmacy**: ``has_prescription=True`` triggers fulfilment workflow.
    * **Billing**: triggers invoice generation (encounter + any procedures).
    * **Laboratory**: ``has_lab_order=True`` triggers sample-collection workflow.
    """

    patient_id: str
    doctor_id: str
    primary_icd10: str | None = None    # ICD-10 code for billing classification
    has_prescription: bool = False
    has_lab_order: bool = False
    closed_by: str


class PrescriptionIssuedPayloadV1(_Base):
    """Payload of ``clinical.encounter.prescription_issued.v1``.

    Used by: Pharmacy context to initiate dispensing.
    Drug names are included here because the Pharmacy context needs them to
    run drug-interaction checks (Specification Pattern + ACL to RxNav).
    """

    prescription_id: str
    lines: list[PrescriptionLineV1]
    issued_by: str


class PrescriptionLineV1(_Base):
    drug_name: str
    dose: str
    route: str
    frequency: str
    duration_days: int
    instructions: str | None = None


class LabOrderPlacedPayloadV1(_Base):
    """Payload of ``clinical.encounter.lab_order_placed.v1``.

    Used by: Laboratory context to create specimen-collection tasks.
    """

    lab_order_id: str
    tests: list[LabTestV1]
    ordered_by: str


class LabTestV1(_Base):
    test_code: str
    urgency: str
    notes: str | None = None


class EncounterVoidedPayloadV1(_Base):
    """Payload of ``clinical.encounter.voided.v1``.

    Compensation event: downstream contexts should roll back any work
    they started in response to ``EncounterStarted``.
    """

    reason: str
    voided_by: str
