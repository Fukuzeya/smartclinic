"""Hash-chained event store utilities (ADR 0012).

The chain hash is a pure function of the previous hash and the event being
appended.  It is computed here and stored on the ``EventStoreRecord`` row so
that any post-hoc modification to the event table is immediately detectable
by running :func:`verify_chain`.

Hash construction (deterministic, no secret — this is integrity, not secrecy):

    chain_hash[0] = SHA-256(GENESIS_HASH + "|" + event_id + "|" + event_type
                            + "|" + canonical_json(payload))
    chain_hash[n] = SHA-256(chain_hash[n-1] + "|" + event_id + "|" + event_type
                            + "|" + canonical_json(payload))

``canonical_json`` is ``json.dumps(payload, sort_keys=True, separators=(",", ":"))``
so the hash is deterministic regardless of dict insertion order.

The ``GENESIS_HASH`` sentinel is 64 zeroes — a value that cannot appear as an
actual SHA-256 output, so the first event in any aggregate's stream is
unambiguously identifiable without a special ``is_first`` column.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from typing import Any, Sequence

GENESIS_HASH: str = "0" * 64


def canonical_json(payload: dict[str, Any]) -> str:
    """Canonical JSON representation used for hashing (deterministic, compact)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_chain_hash(
    *,
    prev_hash: str,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> str:
    """Compute the chain hash for a new event appended after *prev_hash*."""
    data = "|".join([prev_hash, event_id, event_type, canonical_json(payload)])
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ChainVerificationResult:
    is_valid: bool
    first_broken_sequence: int | None = None
    expected_hash: str | None = None
    stored_hash: str | None = None
    message: str = ""


def verify_chain(records: Sequence[Any]) -> ChainVerificationResult:
    """Verify the integrity of an event stream for one aggregate.

    *records* must be ordered by ``sequence`` ascending and all belong to the
    same ``aggregate_id``.  Returns a :class:`ChainVerificationResult` with
    ``is_valid=True`` when every hash in the chain matches the recomputed value.

    This function is intentionally non-async and side-effect free so it can be
    called from tests, a CLI audit tool, or an admin API endpoint without
    touching the database.
    """
    if not records:
        return ChainVerificationResult(is_valid=True, message="Empty chain — trivially valid")

    prev_hash = GENESIS_HASH
    for record in records:
        expected = compute_chain_hash(
            prev_hash=prev_hash,
            event_id=str(record.id),
            event_type=record.event_type,
            payload=record.payload,
        )
        if expected != record.chain_hash:
            return ChainVerificationResult(
                is_valid=False,
                first_broken_sequence=record.sequence,
                expected_hash=expected,
                stored_hash=record.chain_hash,
                message=(
                    f"Chain broken at sequence {record.sequence} "
                    f"(event_id={record.id}, type={record.event_type}): "
                    f"expected {expected[:12]}…, got {record.chain_hash[:12]}…"
                ),
            )
        prev_hash = record.chain_hash

    return ChainVerificationResult(
        is_valid=True,
        message=f"Chain of {len(records)} events verified OK",
    )
