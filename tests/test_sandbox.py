"""Tests for the swarm sandbox v1 (deterministic, zero-key)."""

from receipts.sandbox import ACTIONS_PER_TURN, run_swarm


def test_run_commits_every_action_before_act():
    result = run_swarm(agents=4, rounds=5, seed=42)
    assert len(result.evidence) == 4 * 5 * ACTIONS_PER_TURN
    ok, bad = result.evidence.verify()
    assert ok and bad is None
    assert len(result.board) == 4 * 5
    assert result.resource.counter == 4 * 5
    assert result.resource.writes == 4 * 5
    assert result.resource.last_writer in {f"agent-{i}" for i in range(4)}
    assert result.resource.holder is None  # all claims released


def test_same_seed_reproduces_identical_run():
    a = run_swarm(agents=4, rounds=5, seed=42)
    b = run_swarm(agents=4, rounds=5, seed=42)
    assert a.evidence.head_hash == b.evidence.head_hash
    assert [m.text for m in a.board] == [m.text for m in b.board]
    assert a.self_reports == b.self_reports
    assert a.summary() == b.summary()


def test_different_seed_changes_the_run():
    a = run_swarm(agents=4, rounds=5, seed=42)
    b = run_swarm(agents=4, rounds=5, seed=43)
    assert a.evidence.head_hash != b.evidence.head_hash


def test_board_messages_match_committed_posts():
    result = run_swarm(agents=3, rounds=2, seed=7)
    posts = [r for r in result.evidence.records if r.action == "post_message"]
    assert len(posts) == len(result.board)
    for record, message in zip(posts, result.board):
        assert record.actor == message.author
        assert record.payload["text"] == message.text
        assert record.payload["board_id"] == message.id
        assert record.round_no == message.round_no


def test_self_reports_match_evidence_in_clean_run():
    result = run_swarm(agents=4, rounds=3, seed=11)
    for report in result.self_reports:
        agent = report["agent"]
        committed = [r for r in result.evidence.records if r.actor == agent]
        assert report["messages_posted"] == sum(
            1 for r in committed if r.action == "post_message"
        )
        assert report["resource_writes"] == sum(
            1 for r in committed if r.action == "resource_write"
        )
        assert len(report["tool_calls"]) == sum(
            1 for r in committed if r.action == "tool_call"
        )
        assert len(report["actions"]) == len(committed)
        # every reported action is present in the evidence log, verbatim
        for action in report["actions"]:
            assert any(
                r.action == action["action"]
                and all(r.payload.get(k) == v for k, v in action.items() if k != "action")
                for r in committed
            )


def test_empty_swarm_and_zero_rounds():
    empty = run_swarm(agents=0, rounds=5, seed=1)
    assert len(empty.evidence) == 0
    assert empty.board == []
    assert empty.self_reports == []
    ok, _ = empty.evidence.verify()
    assert ok

    no_rounds = run_swarm(agents=3, rounds=0, seed=1)
    assert len(no_rounds.evidence) == 0
    assert no_rounds.board == []
    assert len(no_rounds.self_reports) == 3
    assert all(r["messages_posted"] == 0 for r in no_rounds.self_reports)


def test_larger_swarm_scales_linearly():
    result = run_swarm(agents=8, rounds=10, seed=99)
    assert len(result.evidence) == 8 * 10 * ACTIONS_PER_TURN
    ok, _ = result.evidence.verify()
    assert ok
