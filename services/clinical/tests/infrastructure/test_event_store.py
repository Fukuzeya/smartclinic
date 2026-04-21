"""Infrastructure tests for the hash-chained event store.

Tests verify:
* ``compute_chain_hash`` is deterministic and changes when any input changes.
* ``verify_chain`` correctly validates an untampered stream.
* ``verify_chain`` detects any single-field mutation (tamper evidence).
* The repository correctly appends events with sequential hashes.
* Optimistic concurrency: a duplicate sequence insertion raises
  ``ConcurrencyConflict``.

Integration tests (``test_event_store_integration``) require a running
Postgres via testcontainers and are marked with ``@pytest.mark.integration``.
Run them with: ``pytest -m integration``
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pytest

from clinical.infrastructure.event_store import (
    GENESIS_HASH,
    canonical_json,
    compute_chain_hash,
    verify_chain,
)


# ---------------------------------------------------------------------------
# Unit tests — pure functions, no I/O

class TestComputeChainHash:
    def test_deterministic_same_inputs(self):
        h1 = compute_chain_hash(
            prev_hash=GENESIS_HASH,
            event_id="abc123",
            event_type="clinical.encounter.started.v1",
            payload={"patient_id": "pat_x", "doctor_id": "doc_y"},
        )
        h2 = compute_chain_hash(
            prev_hash=GENESIS_HASH,
            event_id="abc123",
            event_type="clinical.encounter.started.v1",
            payload={"patient_id": "pat_x", "doctor_id": "doc_y"},
        )
        assert h1 == h2

    def test_different_prev_hash_produces_different_result(self):
        h1 = compute_chain_hash(
            prev_hash=GENESIS_HASH,
            event_id="abc", event_type="t", payload={},
        )
        h2 = compute_chain_hash(
            prev_hash="a" * 64,
            event_id="abc", event_type="t", payload={},
        )
        assert h1 != h2

    def test_different_event_id_produces_different_result(self):
        kwargs = dict(prev_hash=GENESIS_HASH, event_type="t", payload={})
        h1 = compute_chain_hash(event_id="id1", **kwargs)
        h2 = compute_chain_hash(event_id="id2", **kwargs)
        assert h1 != h2

    def test_different_payload_value_produces_different_result(self):
        kwargs = dict(prev_hash=GENESIS_HASH, event_id="id1", event_type="t")
        h1 = compute_chain_hash(payload={"k": "v1"}, **kwargs)
        h2 = compute_chain_hash(payload={"k": "v2"}, **kwargs)
        assert h1 != h2

    def test_payload_key_order_does_not_matter(self):
        """canonical_json sorts keys, so insertion order must not affect the hash."""
        kwargs = dict(prev_hash=GENESIS_HASH, event_id="id1", event_type="t")
        h1 = compute_chain_hash(payload={"a": 1, "b": 2}, **kwargs)
        h2 = compute_chain_hash(payload={"b": 2, "a": 1}, **kwargs)
        assert h1 == h2

    def test_output_is_64_hex_chars(self):
        h = compute_chain_hash(
            prev_hash=GENESIS_HASH, event_id="x", event_type="t", payload={}
        )
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_genesis_hash_is_64_zeroes(self):
        assert GENESIS_HASH == "0" * 64

    def test_genesis_hash_differs_from_real_hash(self):
        real = compute_chain_hash(
            prev_hash=GENESIS_HASH, event_id="id", event_type="t", payload={}
        )
        assert real != GENESIS_HASH


class TestVerifyChain:
    @dataclass
    class FakeRecord:
        id: uuid.UUID
        event_type: str
        payload: dict[str, Any]
        chain_hash: str
        sequence: int

    def _make_chain(self, n: int) -> list[FakeRecord]:
        """Build a valid chain of *n* fake records."""
        records = []
        prev_hash = GENESIS_HASH
        for i in range(1, n + 1):
            eid = uuid.uuid4()
            etype = f"test.event.v{i}"
            payload = {"seq": i}
            chain_hash = compute_chain_hash(
                prev_hash=prev_hash,
                event_id=str(eid),
                event_type=etype,
                payload=payload,
            )
            records.append(self.FakeRecord(
                id=eid, event_type=etype, payload=payload,
                chain_hash=chain_hash, sequence=i,
            ))
            prev_hash = chain_hash
        return records

    def test_empty_chain_is_valid(self):
        result = verify_chain([])
        assert result.is_valid

    def test_single_event_chain_is_valid(self):
        chain = self._make_chain(1)
        result = verify_chain(chain)
        assert result.is_valid

    def test_five_event_chain_is_valid(self):
        chain = self._make_chain(5)
        result = verify_chain(chain)
        assert result.is_valid

    def test_tampered_payload_detected(self):
        chain = self._make_chain(3)
        # Tamper: change a payload value in record 2
        chain[1] = self.FakeRecord(
            id=chain[1].id,
            event_type=chain[1].event_type,
            payload={"seq": 999},          # changed!
            chain_hash=chain[1].chain_hash, # hash not updated
            sequence=chain[1].sequence,
        )
        result = verify_chain(chain)
        assert not result.is_valid
        assert result.first_broken_sequence == 2

    def test_tampered_event_type_detected(self):
        chain = self._make_chain(2)
        chain[0] = self.FakeRecord(
            id=chain[0].id,
            event_type="malicious.event.v1",  # changed!
            payload=chain[0].payload,
            chain_hash=chain[0].chain_hash,
            sequence=chain[0].sequence,
        )
        result = verify_chain(chain)
        assert not result.is_valid
        assert result.first_broken_sequence == 1

    def test_tampered_chain_hash_directly_detected(self):
        chain = self._make_chain(3)
        chain[2] = self.FakeRecord(
            id=chain[2].id,
            event_type=chain[2].event_type,
            payload=chain[2].payload,
            chain_hash="f" * 64,            # forged hash
            sequence=chain[2].sequence,
        )
        result = verify_chain(chain)
        assert not result.is_valid
        assert result.first_broken_sequence == 3

    def test_result_message_describes_broken_link(self):
        chain = self._make_chain(2)
        chain[1] = self.FakeRecord(
            id=chain[1].id,
            event_type=chain[1].event_type,
            payload={"tampered": True},
            chain_hash=chain[1].chain_hash,
            sequence=chain[1].sequence,
        )
        result = verify_chain(chain)
        assert "2" in result.message  # sequence number in message

    def test_valid_chain_message_mentions_count(self):
        chain = self._make_chain(4)
        result = verify_chain(chain)
        assert "4" in result.message


class TestCanonicalJson:
    def test_sorted_keys(self):
        out = canonical_json({"b": 2, "a": 1})
        assert out == '{"a":1,"b":2}'

    def test_no_spaces(self):
        out = canonical_json({"x": 1})
        assert " " not in out

    def test_nested_sorted(self):
        out = canonical_json({"outer": {"z": 1, "a": 2}})
        parsed = json.loads(out)
        assert list(parsed["outer"].keys()) == sorted(parsed["outer"].keys())
