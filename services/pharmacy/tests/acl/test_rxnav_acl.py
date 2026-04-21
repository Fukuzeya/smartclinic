"""ACL unit tests — verify the port/adapter contract without network I/O.

Tests use ``StubDrugInteractionChecker`` and verify that:
* The port Protocol is correctly implemented by all adapters.
* The stub adapter filters by drug name correctly.
* The null adapter always returns empty (fail-open behaviour).
"""

from __future__ import annotations

import pytest

from pharmacy.acl.drug_interaction_port import (
    DrugInteractionChecker,
    NullDrugInteractionChecker,
    StubDrugInteractionChecker,
)
from pharmacy.domain.value_objects import DrugInteraction, InteractionSeverity


def make_severe(a: str, b: str) -> DrugInteraction:
    return DrugInteraction(
        drug_a=a, drug_b=b,
        severity=InteractionSeverity.SEVERE,
        description="Test severe interaction",
    )


class TestNullDrugInteractionChecker:
    async def test_always_returns_empty(self):
        checker = NullDrugInteractionChecker()
        result = await checker.check_interactions(["WARFARIN", "ASPIRIN"])
        assert result == []

    async def test_single_drug_returns_empty(self):
        checker = NullDrugInteractionChecker()
        assert await checker.check_interactions(["WARFARIN"]) == []

    async def test_empty_list_returns_empty(self):
        checker = NullDrugInteractionChecker()
        assert await checker.check_interactions([]) == []

    def test_satisfies_protocol(self):
        checker = NullDrugInteractionChecker()
        assert isinstance(checker, DrugInteractionChecker)


class TestStubDrugInteractionChecker:
    async def test_returns_matching_interactions(self):
        checker = StubDrugInteractionChecker(interactions=[
            make_severe("WARFARIN", "ASPIRIN"),
        ])
        result = await checker.check_interactions(["WARFARIN", "ASPIRIN"])
        assert len(result) == 1
        assert result[0].drug_a == "WARFARIN"

    async def test_case_insensitive_filter(self):
        checker = StubDrugInteractionChecker(interactions=[
            make_severe("WARFARIN", "ASPIRIN"),
        ])
        result = await checker.check_interactions(["warfarin", "aspirin"])
        assert len(result) == 1

    async def test_returns_empty_when_no_matching_drugs(self):
        checker = StubDrugInteractionChecker(interactions=[
            make_severe("WARFARIN", "ASPIRIN"),
        ])
        result = await checker.check_interactions(["PARACETAMOL", "AMOXICILLIN"])
        assert result == []

    async def test_partial_match_returns_interaction(self):
        checker = StubDrugInteractionChecker(interactions=[
            make_severe("WARFARIN", "ASPIRIN"),
        ])
        # Only WARFARIN present — still returns the interaction
        result = await checker.check_interactions(["WARFARIN", "PARACETAMOL"])
        assert len(result) == 1

    def test_satisfies_protocol(self):
        checker = StubDrugInteractionChecker()
        assert isinstance(checker, DrugInteractionChecker)

    async def test_multiple_interactions_all_returned(self):
        checker = StubDrugInteractionChecker(interactions=[
            make_severe("WARFARIN", "ASPIRIN"),
            make_severe("WARFARIN", "NSAID"),
        ])
        result = await checker.check_interactions(["WARFARIN", "ASPIRIN", "NSAID"])
        assert len(result) == 2
