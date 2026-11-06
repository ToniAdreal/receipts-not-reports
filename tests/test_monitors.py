"""Tests for the M4 monitors (naive vs evidence-gated).

All expectations are grounded in real runs of the sandbox with fixed
seeds — the numbers below (10 events, 5 detected by naive, ...) are
what the code actually produces for those inputs, checked by running
them, not hand-computed.
"""

from __future__ import annotations

import dataclasses

import pytest

from receipts.evidence import EvidenceLog
from receipts.monitors import (
    EvidenceMonitor,
    NaiveMonitor,
    score,
    spoofed_claims,
)
from receipts.sandbox import run_swarm
from receipts.tamper import KINDS, TamperConfig

MIXED = TamperConfig(fraction=0.5)  # all kinds, tamperers agent-1, agent-2
NAIVE = NaiveMonitor()
EVIDENCE = EvidenceMonitor()


def _mixed_run(seed: int = 42):
    return run_swarm(agents=4, rounds=5, seed=seed, tamper=MIXED)


def _clean_run(seed: int = 42):
    return run_swarm(agents=4, rounds=5, seed=seed)


# -- clean runs: neither monitor cries wolf -------------------------------


def test_clean_run_no_flags_either_monitor():
    run = _clean_run()
    for monitor in (NAIVE, EVIDENCE):
        result = monitor.audit(run)
        assert result.flagged_agents == ()
        assert result.discrepancies == ()
        assert result.spoofed_claims == 0
        assert result.chain_ok is True
    assert score(run, NAIVE.audit(run))["false_positive_rate"] == 0.0
    assert score(run, EVIDENCE.audit(run))["false_positive_rate"] == 0.0


def test_clean_run_detection_rate_is_undefined_not_zero():
    run = _clean_run()
    assert run.tamper_events == ()
    for monitor in (NAIVE, EVIDENCE):
        assert score(run, monitor.audit(run))["detection_rate"] is None


# -- mixed tampering: evidence wins on every metric ------------------------


def test_evidence_detects_all_mixed_events_naive_half():
    run = _mixed_run()
    assert len(run.tamper_events) == 10
    naive = score(run, NAIVE.audit(run))
    evidence = score(run, EVIDENCE.audit(run))
    assert evidence["detected"] == 10
    assert evidence["detection_rate"] == 1.0
    assert naive["detected"] == 5
    assert naive["detection_rate"] == 0.5


def test_evidence_per_kind_detection_is_complete_on_mixed_run():
    run = _mixed_run()
    by_kind = score(run, EVIDENCE.audit(run))["by_kind"]
    for kind in KINDS:
        assert by_kind[kind]["events"] > 0
        assert by_kind[kind]["rate"] == 1.0


def test_naive_misses_edit_and_spoof_entirely():
    for kinds in (("edit",), ("spoof",)):
        run = run_swarm(
            agents=4,
            rounds=5,
            seed=42,
            tamper=TamperConfig(fraction=0.5, kinds=kinds),
        )
        assert len(run.tamper_events) == 10
        assert score(run, NAIVE.audit(run))["detection_rate"] == 0.0
        assert score(run, EVIDENCE.audit(run))["detection_rate"] == 1.0


def test_naive_detects_delete_fully():
    run = run_swarm(
        agents=4,
        rounds=5,
        seed=42,
        tamper=TamperConfig(fraction=0.5, kinds=("delete",)),
    )
    assert score(run, NAIVE.audit(run))["detection_rate"] == 1.0
    assert score(run, EVIDENCE.audit(run))["detection_rate"] == 1.0


# -- spoofed claims ---------------------------------------------------------


def test_spoofed_claims_accepted_naive_all_evidence_none():
    run = _mixed_run()
    assert len(spoofed_claims(run)) == 3
    naive = score(run, NAIVE.audit(run))
    evidence = score(run, EVIDENCE.audit(run))
    assert naive["spoof_acceptance_rate"] == 1.0
    assert evidence["spoof_acceptance_rate"] == 0.0


def test_spoof_only_run_claims_fewer_than_events_when_entries_reused():
    # 10 spoof events but only 8 distinct spoofed claims: two events
    # re-altered the same memory entry. The metric counts claims, not
    # events, so the report must cite claims (8), not events (10).
    run = run_swarm(
        agents=4,
        rounds=5,
        seed=42,
        tamper=TamperConfig(fraction=0.5, kinds=("spoof",)),
    )
    assert len(run.tamper_events) == 10
    assert len(spoofed_claims(run)) == 8


# -- false positives: rename victims ----------------------------------------


def test_naive_flags_rename_victim_evidence_does_not():
    run = _mixed_run()
    naive = score(run, NAIVE.audit(run))
    evidence = score(run, EVIDENCE.audit(run))
    # agent-3 never tampers; the naive count check flags it because a
    # renamed message now carries its name.
    assert naive["false_positives"] == ["agent-3"]
    assert naive["false_positive_rate"] == 0.5
    assert evidence["false_positives"] == []
    assert evidence["false_positive_rate"] == 0.0
    # The evidence monitor blames the evidence author, never the victim.
    result = EVIDENCE.audit(run)
    assert set(result.flagged_agents) == {"agent-1", "agent-2"}


# -- latency: measured, never negative --------------------------------------


def test_evidence_latency_zero_naive_positive_on_mixed_run():
    run = _mixed_run()
    evidence = score(run, EVIDENCE.audit(run))
    naive = score(run, NAIVE.audit(run))
    assert evidence["mean_latency_rounds"] == 0.0
    assert naive["mean_latency_rounds"] == 2.2
    for latency in EVIDENCE.audit(run).latencies:
        assert latency >= 0


def test_no_false_positive_rate_when_everyone_tampers():
    run = run_swarm(
        agents=4, rounds=5, seed=42, tamper=TamperConfig(fraction=1.0)
    )
    for monitor in (NAIVE, EVIDENCE):
        assert score(run, monitor.audit(run))["false_positive_rate"] is None


# -- audit-cadence limit: same-round cancelling renames ---------------------


def test_same_round_cancelling_rename_stays_invisible():
    # 20 rename events at fraction 1.0, seed 42: two renames of board:17
    # in round 4 cancel out between audits, so the evidence monitor
    # detects 18/20. This is the documented per-round-audit limit.
    run = run_swarm(
        agents=4,
        rounds=5,
        seed=42,
        tamper=TamperConfig(fraction=1.0, kinds=("rename",)),
    )
    assert len(run.tamper_events) == 20
    evidence = score(run, EVIDENCE.audit(run))
    assert evidence["detected"] == 18
    assert evidence["detection_rate"] == 0.9
    undetected = [
        e for e in run.tamper_events if e not in EVIDENCE.audit(run).detected_events
    ]
    assert {e.target for e in undetected} == {"board:17"}
    assert {e.round_no for e in undetected} == {4}


# -- chain integrity --------------------------------------------------------


def test_evidence_monitor_reports_broken_chain():
    log = EvidenceLog()
    log.append(actor="agent-0", action="post_message", payload={"text": "a", "board_id": 0}, round_no=0)
    log.append(actor="agent-0", action="tool_call", payload={"kind": "search", "result": "r"}, round_no=0)
    assert log.verify()[0] is True
    # Corrupt the second record's payload in a copy of the log.
    corrupted = dataclasses.replace(log.records[1], payload={"kind": "search", "result": "FORGED"})
    broken = EvidenceLog()
    broken._records = [log.records[0], corrupted]  # noqa: SLF001 - test-only
    broken._head = corrupted.hash  # noqa: SLF001 - test-only
    assert broken.verify() == (False, 1)

    run = run_swarm(agents=1, rounds=1, seed=1)
    object.__setattr__(run, "evidence", broken)
    result = EVIDENCE.audit(run)
    assert result.chain_ok is False
    assert any(d.kind == "chain" for d in result.discrepancies)


# -- determinism + edges ----------------------------------------------------


def test_monitor_results_deterministic():
    run_a = _mixed_run()
    run_b = _mixed_run()
    for monitor in (NAIVE, EVIDENCE):
        assert monitor.audit(run_a) == monitor.audit(run_b)


def test_monitors_handle_empty_runs():
    run = run_swarm(agents=0, rounds=0, seed=1)
    for monitor in (NAIVE, EVIDENCE):
        result = monitor.audit(run)
        assert result.flagged_agents == ()
        assert result.chain_ok is True
        assert score(run, result)["detection_rate"] is None
