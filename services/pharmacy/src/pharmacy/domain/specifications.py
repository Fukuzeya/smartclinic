"""Pharmacy Specification Pattern (ADR 0006).

This module is the primary demonstration of the Specification Pattern with
composition. Every dispensing decision flows through a composed specification
tree rather than procedural ``if/elif`` chains, which gives us:

* **Explainability**: ``reasons_for_failure`` collects *all* violations so the
  pharmacist sees every blocking reason simultaneously, not just the first one.
* **Testability**: each spec is a pure class with no I/O; tested independently.
* **Extensibility**: new clinical rules (e.g. pregnancy contraindications) are
  new ``Specification`` subclasses, not changes to existing code (OCP).
* **Composability**: the canonical dispensing spec is assembled from four
  primitive specs using ``&`` operators — readable as a business rule.

The canonical composition used by the dispensing handler::

    dispensable_spec = (
        AllDrugsInStockSpecification(stock_levels)
        & PatientConsentGrantedSpecification()
        & NoSevereDrugInteractionSpecification()
        & PrescriptionNotExpiredSpecification()
    )
    dispensable_spec.assert_satisfied_by(candidate)

If any sub-spec fails, ``assert_satisfied_by`` raises
:class:`SpecificationViolation` with a combined ``reasons`` list that the API
returns as an RFC 7807 problem detail.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from shared_kernel.domain.specification import Specification

from pharmacy.domain.value_objects import (
    DispensableCandidate,
    InteractionSeverity,
)


class AllDrugsInStockSpecification(Specification[DispensableCandidate]):
    """All drugs on the prescription must have at least one unit in stock.

    The spec is intentionally conservative: it does not attempt a partial
    dispense. If any drug is out of stock the full prescription is blocked so
    the pharmacist can decide to substitute or split the order.
    """

    def is_satisfied_by(self, candidate: DispensableCandidate) -> bool:
        stock_map = {s.drug_name.upper(): s for s in candidate.stock_levels}
        return all(
            stock_map.get(name.upper(), None) is not None
            and stock_map[name.upper()].is_available()
            for name in candidate.drug_names
        )

    def reasons_for_failure(self, candidate: DispensableCandidate) -> list[str]:
        stock_map = {s.drug_name.upper(): s for s in candidate.stock_levels}
        out: list[str] = []
        for name in candidate.drug_names:
            stock = stock_map.get(name.upper())
            if stock is None:
                out.append(f"Drug '{name}' is not found in the dispensary inventory.")
            elif not stock.is_available():
                out.append(
                    f"Drug '{name}' is out of stock "
                    f"(on hand: {stock.quantity_on_hand} {stock.unit})."
                )
        return out


class PatientConsentGrantedSpecification(Specification[DispensableCandidate]):
    """The patient must have an active TREATMENT consent record.

    Under POPIA / HIPAA-inspired SmartClinic policy (ADR 0011), dispensing
    medication is a treatment-purpose processing activity that requires
    informed consent.  If the patient's consent has been revoked (e.g.
    right-to-be-forgotten trigger), we must halt dispensing and route to
    the treating clinician.
    """

    def is_satisfied_by(self, candidate: DispensableCandidate) -> bool:
        return candidate.has_treatment_consent

    def reasons_for_failure(self, candidate: DispensableCandidate) -> list[str]:
        return [
            f"Patient '{candidate.patient_id}' does not have an active TREATMENT "
            "consent on file. Obtain consent before dispensing."
        ]


class NoSevereDrugInteractionSpecification(Specification[DispensableCandidate]):
    """No SEVERE drug–drug interaction may be present.

    SEVERE interactions are a hard block — the pharmacist must not override
    them.  MODERATE interactions are handled by a separate advisory spec
    (see :class:`NoModerateDrugInteractionSpecification`) and surface as
    warnings, not blockers.

    Interaction data is pre-loaded into the ``DispensableCandidate`` by the
    RxNav ACL before the spec chain runs — the spec itself has no I/O.
    """

    def is_satisfied_by(self, candidate: DispensableCandidate) -> bool:
        return not any(
            i.severity == InteractionSeverity.SEVERE
            for i in candidate.interactions
        )

    def reasons_for_failure(self, candidate: DispensableCandidate) -> list[str]:
        return [
            f"SEVERE drug interaction: {i.drug_a} ↔ {i.drug_b} — {i.description}"
            for i in candidate.interactions
            if i.severity == InteractionSeverity.SEVERE
        ]


class NoModerateDrugInteractionSpecification(Specification[DispensableCandidate]):
    """Advisory: no MODERATE interactions present.

    Unlike SEVERE, a MODERATE interaction is a *soft block* — the spec
    fails but the pharmacist may override with a documented clinical
    justification.  Surfaced as a warning in the API response.
    """

    def is_satisfied_by(self, candidate: DispensableCandidate) -> bool:
        return not any(
            i.severity == InteractionSeverity.MODERATE
            for i in candidate.interactions
        )

    def reasons_for_failure(self, candidate: DispensableCandidate) -> list[str]:
        return [
            f"MODERATE interaction (pharmacist review required): "
            f"{i.drug_a} ↔ {i.drug_b} — {i.description}"
            for i in candidate.interactions
            if i.severity == InteractionSeverity.MODERATE
        ]


# ---------------------------------------------------------------------------
# Canonical composed specification used by the dispensing handler

def make_dispensable_specification() -> Specification[DispensableCandidate]:
    """Return the canonical dispensing specification.

    Composition::

        ALL drugs in stock
        AND patient has treatment consent
        AND no SEVERE drug interactions

    MODERATE interactions are handled as warnings via a separate advisory
    spec; they do not block the primary dispensing decision.

    The factory pattern lets callers inject mocked sub-specs in tests
    by calling the primitives directly rather than via this function.
    """
    return (
        AllDrugsInStockSpecification()
        & PatientConsentGrantedSpecification()
        & NoSevereDrugInteractionSpecification()
    )
