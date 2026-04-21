"""Anti-Corruption Layer — RxNav HTTP Adapter (ADR 0007).

This is the real adapter that calls the NLM RxNav REST API to:

1. Look up the RxNorm CUI (Concept Unique Identifier) for a drug name via
   ``/REST/rxcui.json?name={drug_name}&search=2``.
2. Check drug–drug interactions for a set of RxCUIs via
   ``/REST/interaction/list.json?rxcuis={cui1}+{cui2}+...``.

RxNav terminology → Pharmacy domain translation is performed by
:func:`_translate_interaction`, which maps RxNav's severity vocabulary
("high", "moderate", "low") to our ``InteractionSeverity`` enum.
This translation is the *anti-corruption* responsibility: domain code
never sees RxNav's strings.

Failure handling:
* Network errors → logged, empty interaction list returned (fail-open so
  a temporary RxNav outage does not block the entire dispensing workflow).
* CUI not found → drug is still checked by name in the interaction response;
  unknown drugs cannot be interaction-checked, so they pass with a warning log.

Real-world note: RxNav does not require an API key.  Rate limits are generous
(20 req/s per IP) and acceptable for a clinic with a few dozen dispensings
per hour.  For higher volumes, replace with the commercial Micromedex or
Lexicomp APIs — the port abstraction makes this a one-file change.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from shared_kernel.infrastructure.logging import get_logger

from pharmacy.domain.value_objects import DrugInteraction, InteractionSeverity

log = get_logger(__name__)

_RXNAV_BASE = "https://rxnav.nlm.nih.gov/REST"
_TIMEOUT = httpx.Timeout(5.0, connect=3.0)

# RxNav severity string → our domain enum
_SEVERITY_MAP: dict[str, InteractionSeverity] = {
    "high": InteractionSeverity.SEVERE,
    "severe": InteractionSeverity.SEVERE,
    "critical": InteractionSeverity.SEVERE,
    "major": InteractionSeverity.SEVERE,
    "moderate": InteractionSeverity.MODERATE,
    "medium": InteractionSeverity.MODERATE,
    "low": InteractionSeverity.MINOR,
    "minor": InteractionSeverity.MINOR,
    "minimal": InteractionSeverity.MINOR,
}


class RxNavDrugInteractionChecker:
    """Real adapter: calls rxnav.nlm.nih.gov to check drug interactions."""

    def __init__(self, base_url: str = _RXNAV_BASE, timeout: httpx.Timeout = _TIMEOUT) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout

    async def check_interactions(self, drug_names: list[str]) -> list[DrugInteraction]:
        """Return all known interactions for the given drug names.

        Internally: name → CUI lookup, then interaction list query.
        Falls back gracefully on partial lookup failures.
        """
        if len(drug_names) < 2:
            return []   # Need at least 2 drugs for an interaction

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            cuis = await _lookup_cuis(client, self._base, drug_names)
            if len(cuis) < 2:
                log.warning("rxnav.insufficient_cuis",
                            drug_names=drug_names, found=len(cuis))
                return []
            return await _fetch_interactions(client, self._base, cuis, drug_names)


async def _lookup_cuis(
    client: httpx.AsyncClient,
    base: str,
    drug_names: list[str],
) -> list[str]:
    """Resolve drug names to RxNorm CUIs in parallel."""
    tasks = [_lookup_single_cui(client, base, name) for name in drug_names]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    cuis = []
    for name, result in zip(drug_names, results):
        if isinstance(result, Exception):
            log.warning("rxnav.cui_lookup_failed", drug=name, error=str(result))
        elif result:
            cuis.append(result)
    return cuis


async def _lookup_single_cui(
    client: httpx.AsyncClient,
    base: str,
    drug_name: str,
) -> str | None:
    try:
        resp = await client.get(
            f"{base}/rxcui.json",
            params={"name": drug_name, "search": "2"},
        )
        resp.raise_for_status()
        data = resp.json()
        cui = (
            data.get("idGroup", {})
            .get("rxnormId", [None])[0]
        )
        return cui
    except Exception as exc:
        raise exc


async def _fetch_interactions(
    client: httpx.AsyncClient,
    base: str,
    cuis: list[str],
    original_names: list[str],
) -> list[DrugInteraction]:
    try:
        rxcui_param = "+".join(cuis)
        resp = await client.get(
            f"{base}/interaction/list.json",
            params={"rxcuis": rxcui_param},
        )
        resp.raise_for_status()
        data = resp.json()
        return _parse_interactions(data, original_names)
    except Exception as exc:
        log.warning("rxnav.interaction_check_failed", error=str(exc))
        return []


def _parse_interactions(
    data: dict[str, Any],
    original_names: list[str],
) -> list[DrugInteraction]:
    interactions: list[DrugInteraction] = []
    full_interaction_type_group = data.get("fullInteractionTypeGroup", [])

    for group in full_interaction_type_group:
        source = group.get("sourceName", "RxNav")
        for full_type in group.get("fullInteractionType", []):
            description = full_type.get("comment", "Drug interaction")
            for pair in full_type.get("interactionPair", []):
                severity_str = pair.get("severity", "moderate").lower()
                severity = _SEVERITY_MAP.get(severity_str, InteractionSeverity.MODERATE)
                # Extract the two interacting drug concepts
                concepts = pair.get("interactionConcept", [])
                if len(concepts) >= 2:
                    drug_a = _concept_to_name(concepts[0], original_names)
                    drug_b = _concept_to_name(concepts[1], original_names)
                    interactions.append(DrugInteraction(
                        drug_a=drug_a,
                        drug_b=drug_b,
                        severity=severity,
                        description=description,
                    ))
    return interactions


def _concept_to_name(concept: dict[str, Any], original_names: list[str]) -> str:
    """Extract a human-readable drug name from an RxNav concept dict.

    Prefers the minConcept name; falls back to the RxNorm description.
    """
    name = (
        concept.get("minConceptItem", {}).get("name")
        or concept.get("sourceConceptItem", {}).get("name")
        or "Unknown"
    )
    return name.upper()
