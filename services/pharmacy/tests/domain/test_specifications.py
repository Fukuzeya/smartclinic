"""Specification Pattern unit tests — the primary Phase 5 demonstration.

These tests verify every specification in isolation and the composed
``make_dispensable_specification`` chain. All tests are pure: no database,
no HTTP client, no infrastructure. The ``DispensableCandidate`` VO is
constructed directly with the exact inputs needed to exercise each path.

Test goals:
* Each primitive spec: satisfied and not-satisfied paths.
* ``reasons_for_failure`` returns specific, actionable strings.
* Composition: AND chain fails with ALL reasons aggregated (not just first).
* Composition: NOT spec inverts correctly.
* The canonical ``make_dispensable_specification`` passes when all conditions met.
* The canonical spec fails with informative reasons when any condition fails.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from shared_kernel.domain.specification import SpecificationViolation

from pharmacy.domain.specifications import (
    AllDrugsInStockSpecification,
    NoModerateDrugInteractionSpecification,
    NoSevereDrugInteractionSpecification,
    PatientConsentGrantedSpecification,
    make_dispensable_specification,
)
from pharmacy.domain.value_objects import (
    DispensableCandidate,
    DrugInteraction,
    InteractionSeverity,
    StockLevel,
)

# ---------------------------------------------------------------------------
# Helpers

PATIENT_ID = "pat_test123"
RX_ID = "rx_abc456"


def make_candidate(
    drug_names: list[str] | None = None,
    stock: list[StockLevel] | None = None,
    has_consent: bool = True,
    interactions: list[DrugInteraction] | None = None,
) -> DispensableCandidate:
    drug_names = drug_names or ["AMOXICILLIN"]
    stock = stock or [
        StockLevel(drug_name="AMOXICILLIN", quantity_on_hand=Decimal("100"), unit="capsules")
    ]
    return DispensableCandidate(
        prescription_id=RX_ID,
        patient_id=PATIENT_ID,
        drug_names=drug_names,
        stock_levels=stock,
        has_treatment_consent=has_consent,
        interactions=interactions or [],
    )


def severe_interaction(a: str = "WARFARIN", b: str = "ASPIRIN") -> DrugInteraction:
    return DrugInteraction(
        drug_a=a, drug_b=b,
        severity=InteractionSeverity.SEVERE,
        description="Increased bleeding risk — do not combine",
    )


def moderate_interaction(a: str = "WARFARIN", b: str = "IBUPROFEN") -> DrugInteraction:
    return DrugInteraction(
        drug_a=a, drug_b=b,
        severity=InteractionSeverity.MODERATE,
        description="Moderate bleeding risk — monitor closely",
    )


# ---------------------------------------------------------------------------
# AllDrugsInStockSpecification

class TestAllDrugsInStockSpecification:
    spec = AllDrugsInStockSpecification()

    def test_satisfied_when_all_drugs_in_stock(self):
        candidate = make_candidate(
            drug_names=["AMOXICILLIN"],
            stock=[StockLevel(drug_name="AMOXICILLIN", quantity_on_hand=Decimal("50"), unit="capsules")],
        )
        assert self.spec.is_satisfied_by(candidate) is True

    def test_not_satisfied_when_drug_missing_from_inventory(self):
        candidate = make_candidate(drug_names=["CIPROFLOXACIN"], stock=[])
        assert self.spec.is_satisfied_by(candidate) is False

    def test_not_satisfied_when_quantity_is_zero(self):
        candidate = make_candidate(
            drug_names=["AMOXICILLIN"],
            stock=[StockLevel(drug_name="AMOXICILLIN", quantity_on_hand=Decimal("0"), unit="capsules")],
        )
        assert self.spec.is_satisfied_by(candidate) is False

    def test_reasons_name_missing_drug(self):
        candidate = make_candidate(drug_names=["RAREDRUG"], stock=[])
        reasons = self.spec.reasons_for_failure(candidate)
        assert len(reasons) == 1
        assert "RAREDRUG" in reasons[0]
        assert "not found" in reasons[0].lower()

    def test_reasons_name_out_of_stock_drug(self):
        candidate = make_candidate(
            drug_names=["AMOXICILLIN"],
            stock=[StockLevel(drug_name="AMOXICILLIN", quantity_on_hand=Decimal("0"), unit="capsules")],
        )
        reasons = self.spec.reasons_for_failure(candidate)
        assert "out of stock" in reasons[0].lower()
        assert "AMOXICILLIN" in reasons[0]

    def test_reasons_lists_all_out_of_stock_drugs(self):
        """All violations reported, not just the first."""
        candidate = make_candidate(drug_names=["DRUG_A", "DRUG_B"], stock=[])
        reasons = self.spec.reasons_for_failure(candidate)
        assert len(reasons) == 2

    def test_case_insensitive_lookup(self):
        candidate = DispensableCandidate(
            prescription_id=RX_ID, patient_id=PATIENT_ID,
            drug_names=["amoxicillin"],   # lowercase from Clinical
            stock_levels=[StockLevel(drug_name="AMOXICILLIN", quantity_on_hand=Decimal("10"), unit="capsules")],
            has_treatment_consent=True, interactions=[],
        )
        assert self.spec.is_satisfied_by(candidate) is True

    def test_satisfied_with_multiple_drugs_all_in_stock(self):
        candidate = make_candidate(
            drug_names=["AMOXICILLIN", "PARACETAMOL"],
            stock=[
                StockLevel(drug_name="AMOXICILLIN", quantity_on_hand=Decimal("100"), unit="capsules"),
                StockLevel(drug_name="PARACETAMOL", quantity_on_hand=Decimal("200"), unit="tablets"),
            ],
        )
        assert self.spec.is_satisfied_by(candidate) is True


# ---------------------------------------------------------------------------
# PatientConsentGrantedSpecification

class TestPatientConsentGrantedSpecification:
    spec = PatientConsentGrantedSpecification()

    def test_satisfied_when_consent_active(self):
        assert self.spec.is_satisfied_by(make_candidate(has_consent=True)) is True

    def test_not_satisfied_when_consent_absent(self):
        assert self.spec.is_satisfied_by(make_candidate(has_consent=False)) is False

    def test_reason_mentions_patient_id(self):
        candidate = make_candidate(has_consent=False)
        reasons = self.spec.reasons_for_failure(candidate)
        assert PATIENT_ID in reasons[0]
        assert "TREATMENT" in reasons[0]

    def test_reason_mentions_consent_requirement(self):
        reasons = PatientConsentGrantedSpecification().reasons_for_failure(
            make_candidate(has_consent=False)
        )
        assert "consent" in reasons[0].lower()


# ---------------------------------------------------------------------------
# NoSevereDrugInteractionSpecification

class TestNoSevereDrugInteractionSpecification:
    spec = NoSevereDrugInteractionSpecification()

    def test_satisfied_when_no_interactions(self):
        assert self.spec.is_satisfied_by(make_candidate()) is True

    def test_satisfied_when_only_moderate_interaction(self):
        candidate = make_candidate(interactions=[moderate_interaction()])
        assert self.spec.is_satisfied_by(candidate) is True

    def test_not_satisfied_when_severe_interaction_present(self):
        candidate = make_candidate(interactions=[severe_interaction()])
        assert self.spec.is_satisfied_by(candidate) is False

    def test_reasons_describe_severe_interaction(self):
        candidate = make_candidate(interactions=[severe_interaction("WARFARIN", "ASPIRIN")])
        reasons = self.spec.reasons_for_failure(candidate)
        assert len(reasons) == 1
        assert "WARFARIN" in reasons[0]
        assert "ASPIRIN" in reasons[0]
        assert "SEVERE" in reasons[0]

    def test_reasons_list_all_severe_interactions(self):
        interactions = [
            severe_interaction("WARFARIN", "ASPIRIN"),
            severe_interaction("METHOTREXATE", "NSAID"),
        ]
        candidate = make_candidate(interactions=interactions)
        reasons = self.spec.reasons_for_failure(candidate)
        assert len(reasons) == 2

    def test_not_satisfied_with_mixed_severities(self):
        candidate = make_candidate(interactions=[severe_interaction(), moderate_interaction()])
        assert self.spec.is_satisfied_by(candidate) is False


# ---------------------------------------------------------------------------
# NoModerateDrugInteractionSpecification (advisory)

class TestNoModerateDrugInteractionSpecification:
    spec = NoModerateDrugInteractionSpecification()

    def test_satisfied_when_no_moderate_interactions(self):
        assert self.spec.is_satisfied_by(make_candidate()) is True

    def test_not_satisfied_when_moderate_interaction_present(self):
        candidate = make_candidate(interactions=[moderate_interaction()])
        assert self.spec.is_satisfied_by(candidate) is False

    def test_reasons_mention_pharmacist_review(self):
        candidate = make_candidate(interactions=[moderate_interaction()])
        reasons = self.spec.reasons_for_failure(candidate)
        assert "pharmacist" in reasons[0].lower()


# ---------------------------------------------------------------------------
# Composed specification: AND chain

class TestComposedSpecification:
    def test_and_satisfied_when_all_pass(self):
        spec = AllDrugsInStockSpecification() & PatientConsentGrantedSpecification()
        candidate = make_candidate(has_consent=True)
        assert spec.is_satisfied_by(candidate) is True

    def test_and_fails_when_left_fails(self):
        spec = AllDrugsInStockSpecification() & PatientConsentGrantedSpecification()
        candidate = make_candidate(drug_names=["RARE"], stock=[], has_consent=True)
        assert spec.is_satisfied_by(candidate) is False

    def test_and_fails_when_right_fails(self):
        spec = AllDrugsInStockSpecification() & PatientConsentGrantedSpecification()
        candidate = make_candidate(has_consent=False)
        assert spec.is_satisfied_by(candidate) is False

    def test_and_aggregates_all_reasons(self):
        """Both violations reported, not just the first."""
        spec = AllDrugsInStockSpecification() & PatientConsentGrantedSpecification()
        candidate = make_candidate(drug_names=["MISSING"], stock=[], has_consent=False)
        reasons = spec.reasons_for_failure(candidate)
        assert len(reasons) >= 2  # stock + consent

    def test_not_inverts_specification(self):
        # ~AllDrugsInStockSpecification means "NOT all drugs in stock" — passes when OOS
        spec = ~AllDrugsInStockSpecification()
        out_of_stock = make_candidate(drug_names=["RARE"], stock=[])
        in_stock = make_candidate()
        assert spec.is_satisfied_by(out_of_stock) is True
        assert spec.is_satisfied_by(in_stock) is False

    def test_or_satisfied_when_either_passes(self):
        spec = AllDrugsInStockSpecification() | PatientConsentGrantedSpecification()
        # Stock fails but consent passes → OR should pass
        candidate = make_candidate(drug_names=["RARE"], stock=[], has_consent=True)
        assert spec.is_satisfied_by(candidate) is True


# ---------------------------------------------------------------------------
# Canonical dispensable specification

class TestMakeDispensableSpecification:
    def test_satisfied_when_all_conditions_met(self):
        spec = make_dispensable_specification()
        candidate = make_candidate(
            drug_names=["AMOXICILLIN"],
            stock=[StockLevel(drug_name="AMOXICILLIN", quantity_on_hand=Decimal("50"), unit="capsules")],
            has_consent=True,
            interactions=[],
        )
        assert spec.is_satisfied_by(candidate) is True

    def test_not_satisfied_when_out_of_stock(self):
        spec = make_dispensable_specification()
        candidate = make_candidate(drug_names=["RARE"], stock=[], has_consent=True)
        assert spec.is_satisfied_by(candidate) is False

    def test_not_satisfied_when_no_consent(self):
        spec = make_dispensable_specification()
        candidate = make_candidate(has_consent=False)
        assert spec.is_satisfied_by(candidate) is False

    def test_not_satisfied_when_severe_interaction(self):
        spec = make_dispensable_specification()
        candidate = make_candidate(interactions=[severe_interaction()])
        assert spec.is_satisfied_by(candidate) is False

    def test_assert_satisfied_raises_with_all_reasons(self):
        spec = make_dispensable_specification()
        # Both stock missing AND no consent AND severe interaction
        candidate = make_candidate(
            drug_names=["RARE"], stock=[],
            has_consent=False,
            interactions=[severe_interaction()],
        )
        with pytest.raises(SpecificationViolation) as exc_info:
            spec.assert_satisfied_by(candidate)
        assert len(exc_info.value.reasons) >= 3  # stock + consent + interaction

    def test_reasons_are_human_readable(self):
        spec = make_dispensable_specification()
        candidate = make_candidate(drug_names=["WARFARIN", "ASPIRIN"],
                                   stock=[
                                       StockLevel(drug_name="WARFARIN", quantity_on_hand=Decimal("10"), unit="tablets"),
                                       StockLevel(drug_name="ASPIRIN", quantity_on_hand=Decimal("10"), unit="tablets"),
                                   ],
                                   has_consent=True,
                                   interactions=[severe_interaction("WARFARIN", "ASPIRIN")])
        reasons = spec.reasons_for_failure(candidate)
        # Should mention the two drugs by name
        combined = " ".join(reasons)
        assert "WARFARIN" in combined
        assert "ASPIRIN" in combined

    def test_moderate_interaction_does_not_block_dispensing(self):
        """MODERATE interactions are advisory — canonical spec should still pass."""
        spec = make_dispensable_specification()
        candidate = make_candidate(interactions=[moderate_interaction()])
        assert spec.is_satisfied_by(candidate) is True


# ---------------------------------------------------------------------------
# Prescription aggregate — quick sanity

class TestPrescriptionAggregate:
    def test_receive_creates_pending_prescription(self):
        from pharmacy.domain.prescription import Prescription
        from pharmacy.domain.value_objects import PrescriptionLine
        from shared_kernel.types.identifiers import PrescriptionId

        rx_id = PrescriptionId.new()
        prescription = Prescription.receive(
            prescription_id=rx_id,
            patient_id=PATIENT_ID,
            encounter_id="enc_abc",
            lines=[PrescriptionLine(drug_name="AMOXICILLIN", dose="500mg",
                                    route="oral", frequency="TDS", duration_days=7)],
            issued_by="doc_x",
        )
        assert prescription.status.value == "pending"
        assert len(prescription.peek_domain_events()) == 1

    def test_dispense_transitions_to_dispensed(self):
        from pharmacy.domain.prescription import Prescription
        from pharmacy.domain.value_objects import PrescriptionLine
        from shared_kernel.types.identifiers import PrescriptionId

        rx_id = PrescriptionId.new()
        prescription = Prescription.receive(
            prescription_id=rx_id,
            patient_id=PATIENT_ID,
            encounter_id="enc_abc",
            lines=[PrescriptionLine(drug_name="AMOXICILLIN", dose="500mg",
                                    route="oral", frequency="TDS", duration_days=7)],
            issued_by="doc_x",
        )
        prescription.pull_domain_events()
        prescription.dispense(dispensed_by="pharm_1")
        assert prescription.status.value == "dispensed"

    def test_cannot_dispense_rejected_prescription(self):
        from pharmacy.domain.exceptions import PreconditionFailed
        from pharmacy.domain.prescription import Prescription
        from pharmacy.domain.value_objects import PrescriptionLine
        from shared_kernel.domain.exceptions import PreconditionFailed
        from shared_kernel.types.identifiers import PrescriptionId

        rx_id = PrescriptionId.new()
        prescription = Prescription.receive(
            prescription_id=rx_id,
            patient_id=PATIENT_ID,
            encounter_id="enc_abc",
            lines=[PrescriptionLine(drug_name="AMOXICILLIN", dose="500mg",
                                    route="oral", frequency="TDS", duration_days=7)],
            issued_by="doc_x",
        )
        prescription.pull_domain_events()
        prescription.reject(reasons=["Drug unavailable"], rejected_by="pharm_1")
        prescription.pull_domain_events()
        with pytest.raises(PreconditionFailed):
            prescription.dispense(dispensed_by="pharm_1")
