"""Anti-Corruption Layer — Drug Interaction Port (ADR 0007).

The **Port** (interface) insulates the Pharmacy domain from the external
RxNav drug-interaction API.  Any change to RxNav's API contract — URL changes,
response schema mutations, a migration to a different provider — is absorbed
here and is invisible to the domain's ``NoDrugInteractionSpecification``.

Two adapters are provided:

* :class:`RxNavDrugInteractionChecker` — the real adapter that calls
  ``https://rxnav.nlm.nih.gov/REST/``.  Uses ``httpx`` with a timeout.
* :class:`NullDrugInteractionChecker` — always returns no interactions.
  Used in tests and in environments where RxNav is unreachable (e.g.
  an on-call laptop in a Zimbabwean rural clinic with no internet).
* :class:`StubDrugInteractionChecker` — returns pre-configured interactions.
  Used for integration tests and demo scenarios without network access.

This follows the Ports & Adapters (Hexagonal Architecture) pattern: the
domain only depends on the ``DrugInteractionChecker`` Protocol, never on
``httpx`` or on RxNav's vocabulary.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pharmacy.domain.value_objects import DrugInteraction


@runtime_checkable
class DrugInteractionChecker(Protocol):
    """Port: check for drug–drug interactions given a list of drug names.

    Implementations must:
    * Be idempotent (safe to call multiple times for the same input).
    * Return an empty list when no interactions are found.
    * Never raise exceptions for network failures — catch and return empty
      (fail-open) or raise a domain-level error (fail-closed). The
      ``RxNavDrugInteractionChecker`` uses fail-open with a structured log.
    """

    async def check_interactions(self, drug_names: list[str]) -> list[DrugInteraction]:
        """Return all known interactions between the supplied drugs."""
        ...


class NullDrugInteractionChecker:
    """Null adapter — always returns no interactions.

    Safe default for environments without network access (off-line clinics).
    Pharmacists must use their own clinical judgement when this adapter is
    active; an application-level warning should inform them.
    """

    async def check_interactions(self, drug_names: list[str]) -> list[DrugInteraction]:
        return []


class StubDrugInteractionChecker:
    """Test / demo stub — returns a pre-configured list of interactions.

    Usage::

        checker = StubDrugInteractionChecker(interactions=[
            DrugInteraction(
                drug_a="WARFARIN", drug_b="ASPIRIN",
                severity=InteractionSeverity.SEVERE,
                description="Increased bleeding risk — avoid combination",
            ),
        ])
    """

    def __init__(self, interactions: list[DrugInteraction] | None = None) -> None:
        self._interactions = interactions or []

    async def check_interactions(self, drug_names: list[str]) -> list[DrugInteraction]:
        upper = {n.upper() for n in drug_names}
        return [
            i for i in self._interactions
            if i.drug_a.upper() in upper or i.drug_b.upper() in upper
        ]
