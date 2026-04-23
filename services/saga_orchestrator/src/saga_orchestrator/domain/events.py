"""Saga Orchestrator domain events."""

from __future__ import annotations

import uuid

from pydantic import Field

from shared_kernel.domain.domain_event import DomainEvent


class SagaEvent(DomainEvent):
    aggregate_type: str = Field(default="PatientVisitSaga")


class PatientVisitSagaStartedV1(SagaEvent):
    event_type: str = Field(default="saga.patient_visit.started.v1")

    @classmethod
    def build(
        cls, *, saga_id: uuid.UUID, aggregate_version: int,
        patient_id: str, appointment_id: str, **kw,
    ) -> PatientVisitSagaStartedV1:
        return cls(
            aggregate_id=str(saga_id),
            aggregate_version=aggregate_version,
            payload={"patient_id": patient_id, "appointment_id": appointment_id},
            **kw,
        )


class SagaStepAdvancedV1(SagaEvent):
    """Emitted each time the saga transitions to a new step."""
    event_type: str = Field(default="saga.patient_visit.step_advanced.v1")

    @classmethod
    def build(
        cls, *, saga_id: uuid.UUID, aggregate_version: int,
        from_step: str, to_step: str, trigger_event_type: str, **kw,
    ) -> SagaStepAdvancedV1:
        return cls(
            aggregate_id=str(saga_id),
            aggregate_version=aggregate_version,
            payload={
                "from_step": from_step,
                "to_step": to_step,
                "trigger_event_type": trigger_event_type,
            },
            **kw,
        )


class PatientVisitSagaCompletedV1(SagaEvent):
    """Emitted when the full visit lifecycle (including billing) is settled."""
    event_type: str = Field(default="saga.patient_visit.completed.v1")

    @classmethod
    def build(
        cls, *, saga_id: uuid.UUID, aggregate_version: int,
        patient_id: str, encounter_id: str, **kw,
    ) -> PatientVisitSagaCompletedV1:
        return cls(
            aggregate_id=str(saga_id),
            aggregate_version=aggregate_version,
            payload={"patient_id": patient_id, "encounter_id": encounter_id},
            **kw,
        )


class PatientVisitSagaCancelledV1(SagaEvent):
    """Emitted when the saga is cancelled (appointment cancelled or void)."""
    event_type: str = Field(default="saga.patient_visit.cancelled.v1")

    @classmethod
    def build(
        cls, *, saga_id: uuid.UUID, aggregate_version: int,
        reason: str, trigger_event_type: str, **kw,
    ) -> PatientVisitSagaCancelledV1:
        return cls(
            aggregate_id=str(saga_id),
            aggregate_version=aggregate_version,
            payload={"reason": reason, "trigger_event_type": trigger_event_type},
            **kw,
        )


class SagaSubstitutionRequiredV1(SagaEvent):
    """Compensating event: pharmacy blocked by OOS — doctor must substitute.

    This is the canonical demonstration of a saga compensating action.
    The saga transitions to SUBSTITUTION_REQUIRED and signals the Clinical
    context to notify the prescribing doctor that a drug substitution is needed.
    """
    event_type: str = Field(default="saga.patient_visit.substitution_required.v1")

    @classmethod
    def build(
        cls, *,
        saga_id: uuid.UUID,
        aggregate_version: int,
        patient_id: str,
        encounter_id: str,
        prescription_id: str,
        out_of_stock_drugs: list[str],
        **kw,
    ) -> SagaSubstitutionRequiredV1:
        return cls(
            aggregate_id=str(saga_id),
            aggregate_version=aggregate_version,
            payload={
                "patient_id": patient_id,
                "encounter_id": encounter_id,
                "prescription_id": prescription_id,
                "out_of_stock_drugs": out_of_stock_drugs,
                "action_required": (
                    f"Doctor must substitute: {', '.join(out_of_stock_drugs)} — "
                    "issue a replacement prescription."
                ),
            },
            **kw,
        )
