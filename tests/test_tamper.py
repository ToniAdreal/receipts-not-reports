"""Tests for the tamper injection suite (M3).

The decisive invariant: tampering acts only on the agent-controlled naive
record (board + agent memory). The environment-held evidence log must be
byte-identical with tampering on or off for the same (agents, rounds, seed).
"""

import pytest

from receipts.run import main as run_main
from receipts.sandbox import run_swarm
from receipts.tamper import KINDS, TamperConfig, TamperEvent


def _committed_posts(result):
    return [r for r in result.evidence.records if r.action == "post_message"]


def _committed_tool_calls(result, agent):
    return [
        (r.payload["kind"], r.payload["result"])
        for r in result.evidence.records
        if r.actor == agent and r.action == "tool_call"
    ]


# -- config validation -------------------------------------------------------


def test_config_rejects_bad_fraction():
    with pytest.raises(ValueError):
        TamperConfig(fraction=-0.1)
    with pytest.raises(ValueError):
        TamperConfig(fraction=1.1)


def test_config_rejects_unknown_kind():
    with pytest.raises(ValueError):
        TamperConfig(kinds=("edit", "teleport"))


def test_config_rejects_empty_kinds():
    with pytest.raises(ValueError):
        TamperConfig(kinds=())


def test_tamperer_count_rounds():
    assert TamperConfig(fraction=0.0).tamperer_count(4) == 0
    assert TamperConfig(fraction=0.5).tamperer_count(4) == 2
    assert TamperConfig(fraction=0.5).tamperer_count(3) == 2  # round(1.5)
    assert TamperConfig(fraction=1.0).tamperer_count(4) == 4


# -- selection and determinism -----------------------------------------------


def test_fraction_zero_means_no_tampering():
    result = run_swarm(agents=4, rounds=5, seed=42, tamper=TamperConfig(fraction=0.0))
    assert result.tamperers == ()
    assert result.tamper_events == ()
    assert len(result.board) == len(_committed_posts(result))


def test_tamperer_selection_is_seeded_and_stable():
    a = run_swarm(agents=4, rounds=2, seed=42, tamper=TamperConfig(fraction=0.5))
    b = run_swarm(agents=4, rounds=2, seed=42, tamper=TamperConfig(fraction=0.5))
    assert a.tamperers == b.tamperers
    assert len(a.tamperers) == 2
    assert [e.to_dict() for e in a.tamper_events] == [
        e.to_dict() for e in b.tamper_events
    ]


def test_tampered_run_is_fully_reproducible():
    cfg = TamperConfig(fraction=0.5)
    a = run_swarm(agents=4, rounds=5, seed=42, tamper=cfg)
    b = run_swarm(agents=4, rounds=5, seed=42, tamper=cfg)
    assert a.evidence.head_hash == b.evidence.head_hash
    assert [m.text for m in a.board] == [m.text for m in b.board]
    assert a.self_reports == b.self_reports
    assert a.summary() == b.summary()


def test_one_action_per_tamperer_per_round():
    cfg = TamperConfig(fraction=0.5)  # 2 of 4 agents
    result = run_swarm(agents=4, rounds=5, seed=42, tamper=cfg)
    assert len(result.tamper_events) == 2 * 5
    assert all(e.agent in result.tamperers for e in result.tamper_events)
    assert all(e.kind in KINDS for e in result.tamper_events)
    for round_no in range(5):
        assert sum(1 for e in result.tamper_events if e.round_no == round_no) == 2


# -- the decisive invariant ---------------------------------------------------


def test_evidence_log_identical_with_and_without_tampering():
    clean = run_swarm(agents=4, rounds=5, seed=42)
    tampered = run_swarm(
        agents=4, rounds=5, seed=42, tamper=TamperConfig(fraction=1.0)
    )
    assert tampered.evidence.head_hash == clean.evidence.head_hash
    assert [r.to_dict() for r in tampered.evidence.records] == [
        r.to_dict() for r in clean.evidence.records
    ]
    ok, bad = tampered.evidence.verify()
    assert ok and bad is None


def test_non_tamperers_reports_still_match_evidence():
    result = run_swarm(agents=4, rounds=5, seed=42, tamper=TamperConfig(fraction=0.5))
    for report in result.self_reports:
        if report["agent"] in result.tamperers:
            continue
        committed = _committed_tool_calls(result, report["agent"])
        reported = [(t["kind"], t["result"]) for t in report["tool_calls"]]
        assert reported == committed


# -- each kind, in isolation ---------------------------------------------------


def test_edit_rewrites_board_text_but_not_evidence():
    result = run_swarm(
        agents=4, rounds=5, seed=42, tamper=TamperConfig(fraction=0.5, kinds=("edit",))
    )
    assert len(result.board) == len(_committed_posts(result))
    assert all(e.kind == "edit" for e in result.tamper_events)
    committed = {r.payload["board_id"]: r for r in _committed_posts(result)}
    diverged = [
        m for m in result.board if committed[m.id].payload["text"] != m.text
    ]
    assert diverged, "no board message diverged from its committed text"
    assert all(committed[m.id].actor == m.author for m in result.board)


def test_delete_removes_board_messages_but_not_evidence():
    result = run_swarm(
        agents=4,
        rounds=5,
        seed=42,
        tamper=TamperConfig(fraction=0.5, kinds=("delete",)),
    )
    assert all(e.kind == "delete" for e in result.tamper_events)
    assert len(result.board) == 20 - len(result.tamper_events)
    committed_ids = {r.payload["board_id"] for r in _committed_posts(result)}
    board_ids = {m.id for m in result.board}
    deleted_ids = committed_ids - board_ids
    assert deleted_ids, "no message was actually deleted from the board"
    # The deleted messages are still committed in the evidence log.
    assert all(
        any(r.payload["board_id"] == bid for r in _committed_posts(result))
        for bid in deleted_ids
    )


def test_rename_reattributes_board_messages():
    result = run_swarm(
        agents=4,
        rounds=5,
        seed=42,
        tamper=TamperConfig(fraction=0.5, kinds=("rename",)),
    )
    assert all(e.kind == "rename" for e in result.tamper_events)
    assert len(result.board) == len(_committed_posts(result))
    committed = {r.payload["board_id"]: r for r in _committed_posts(result)}
    misattributed = [
        m for m in result.board if committed[m.id].actor != m.author
    ]
    assert misattributed, "no board message was re-attributed"
    # Every misattributed message now names a real other agent.
    assert all(m.author.startswith("agent-") for m in misattributed)


def test_spoof_falsifies_self_reported_tool_calls():
    result = run_swarm(
        agents=4,
        rounds=5,
        seed=42,
        tamper=TamperConfig(fraction=0.5, kinds=("spoof",)),
    )
    assert all(e.kind == "spoof" for e in result.tamper_events)
    assert len(result.board) == len(_committed_posts(result))  # board untouched
    for report in result.self_reports:
        if report["agent"] not in result.tamperers:
            continue
        committed = _committed_tool_calls(result, report["agent"])
        reported = [(t["kind"], t["result"]) for t in report["tool_calls"]]
        assert reported != committed, "tamperer report matches evidence exactly"
        assert any(
            "SPOOFED" in r or "PHANTOM" in r for _, r in reported
        ), "no spoofed/phantom result in the tamperer report"


# -- edge cases ----------------------------------------------------------------


def test_single_agent_rename_falls_back_to_edit():
    result = run_swarm(
        agents=1, rounds=3, seed=5, tamper=TamperConfig(fraction=1.0, kinds=("rename",))
    )
    assert len(result.tamper_events) == 3  # one action per round, no crash
    assert all(e.kind == "edit" for e in result.tamper_events)


def test_zero_rounds_means_no_tamper_events():
    result = run_swarm(
        agents=4, rounds=0, seed=1, tamper=TamperConfig(fraction=1.0)
    )
    assert result.tamper_events == ()
    assert result.tamperers  # tamperers are still selected


def test_tamper_event_serialises():
    event = TamperEvent(
        kind="edit", agent="agent-0", round_no=1, target="board:3", detail="a -> b"
    )
    assert event.to_dict() == {
        "kind": "edit",
        "agent": "agent-0",
        "round": 1,
        "target": "board:3",
        "detail": "a -> b",
    }


def test_cli_accepts_tamper_options(capsys):
    assert (
        run_main(
            [
                "--agents", "4",
                "--rounds", "5",
                "--seed", "42",
                "--tamper-fraction", "0.5",
            ]
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "tamper events:" in out
    assert "chain:            OK" in out
