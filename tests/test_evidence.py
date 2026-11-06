"""Tests for the hash-chained append-only evidence log."""

import pytest

from receipts.evidence import GENESIS_HASH, EvidenceLog, Record


def _sample_log() -> EvidenceLog:
    log = EvidenceLog()
    log.append(actor="agent-0", action="post_message", payload={"text": "hi"}, round_no=0)
    log.append(actor="agent-1", action="tool_call", payload={"kind": "search"}, round_no=0)
    log.append(actor="agent-0", action="resource_write", payload={"new": 1}, round_no=1)
    return log


def test_empty_log_verifies_with_genesis_head():
    log = EvidenceLog()
    assert len(log) == 0
    assert log.head_hash == GENESIS_HASH
    ok, bad = log.verify()
    assert ok and bad is None


def test_append_chains_and_verifies():
    log = _sample_log()
    assert len(log) == 3
    ok, bad = log.verify()
    assert ok and bad is None
    records = log.records
    assert records[0].prev_hash == GENESIS_HASH
    assert records[1].prev_hash == records[0].hash
    assert records[2].prev_hash == records[1].hash
    assert log.head_hash == records[-1].hash


def test_deterministic_same_inputs_same_hash():
    log_a, log_b = _sample_log(), _sample_log()
    assert log_a.head_hash == log_b.head_hash
    assert [r.hash for r in log_a.records] == [r.hash for r in log_b.records]


def test_payload_tamper_detected_at_right_index():
    log = _sample_log()
    tampered = Record(
        index=log.records[1].index,
        tick=log.records[1].tick,
        round_no=log.records[1].round_no,
        actor=log.records[1].actor,
        action=log.records[1].action,
        payload={"kind": "forged"},
        prev_hash=log.records[1].prev_hash,
        hash=log.records[1].hash,  # attacker kept the old hash
    )
    log._records[1] = tampered
    ok, bad = log.verify()
    assert not ok and bad == 1


def test_prev_hash_tamper_detected():
    log = _sample_log()
    tampered = Record(
        index=log.records[2].index,
        tick=log.records[2].tick,
        round_no=log.records[2].round_no,
        actor=log.records[2].actor,
        action=log.records[2].action,
        payload=log.records[2].payload,
        prev_hash="f" * 64,
        hash=log.records[2].hash,
    )
    log._records[2] = tampered
    ok, bad = log.verify()
    assert not ok and bad == 2


def test_records_snapshot_is_immutable():
    log = _sample_log()
    with pytest.raises(AttributeError):
        log.records.append(log.records[0])  # type: ignore[attr-defined]
    assert len(log) == 3


def test_serialisation_round_trip_preserves_chain():
    log = _sample_log()
    restored = EvidenceLog.from_dicts(log.to_dicts())
    assert restored.head_hash == log.head_hash
    ok, bad = restored.verify()
    assert ok and bad is None


def test_deserialising_tampered_dump_raises():
    log = _sample_log()
    data = log.to_dicts()
    data[0]["payload"] = {"text": "forged"}
    with pytest.raises(ValueError):
        EvidenceLog.from_dicts(data)
