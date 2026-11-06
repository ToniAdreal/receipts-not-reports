"""Tests for the M4 experiment runner."""

from __future__ import annotations

from receipts.experiments import (
    aggregate,
    format_rate,
    markdown_table,
    run_condition,
    run_sweep,
)


def test_run_condition_keys_and_reproducibility():
    row = run_condition(
        agents=4, rounds=5, seed=42, tamper_fraction=0.5
    )
    assert row["agents"] == 4
    assert row["tamper_fraction"] == 0.5
    assert row["tamperers"] == ["agent-1", "agent-2"]
    assert row["committed_actions"] == 100
    assert set(row["monitors"]) == {"naive", "evidence-gated"}
    assert row["monitors"]["evidence-gated"]["detection_rate"] == 1.0
    assert row["monitors"]["naive"]["detection_rate"] == 0.5
    # Same inputs, same row (head hash pins the whole run).
    again = run_condition(
        agents=4, rounds=5, seed=42, tamper_fraction=0.5
    )
    assert row == again


def test_clean_condition_rates_undefined():
    row = run_condition(
        agents=4, rounds=5, seed=42, tamper_fraction=0.0
    )
    for name in ("naive", "evidence-gated"):
        assert row["monitors"][name]["detection_rate"] is None
        assert row["monitors"][name]["spoof_acceptance_rate"] is None
        assert row["monitors"][name]["false_positive_rate"] == 0.0


def test_sweep_grid_size_and_aggregation():
    rows = run_sweep(
        fractions=(0.0, 0.5), agents_list=(4,), seeds=(42, 1), rounds=5
    )
    assert len(rows) == 4  # 2 fractions x 1 size x 2 seeds
    table = aggregate(rows)
    assert len(table) == 2
    frac_half = next(e for e in table if e["tamper_fraction"] == 0.5)
    assert frac_half["runs"] == 2
    assert frac_half["events"] == sum(
        r["monitors"]["evidence-gated"]["events"] for r in rows
        if r["tamper_fraction"] == 0.5
    )
    # Evidence detection is 1.0 at fraction 0.5 for both seeds here.
    assert frac_half["monitors"]["evidence-gated"]["detection_rate"] == 1.0
    # Undefined stays undefined after aggregation (fraction 0: no events).
    frac_zero = next(e for e in table if e["tamper_fraction"] == 0.0)
    assert frac_zero["monitors"]["naive"]["detection_rate"] is None
    assert frac_zero["monitors"]["evidence-gated"]["detection_rate"] is None


def test_markdown_table_renders_undefined_as_na():
    table = aggregate(
        run_sweep(
            fractions=(0.0,), agents_list=(4,), seeds=(42,), rounds=5
        )
    )
    text = markdown_table(table)
    rows = [line for line in text.splitlines() if line.startswith("| 0.00")]
    assert len(rows) == 2  # one row per monitor
    for row in rows:
        # Detection rate and spoof acceptance are undefined at fraction
        # 0 (no events, no spoofed claims): rendered "n/a", never 0.
        assert "| n/a | 0.00 | n/a | n/a |" in row
    assert "evidence-gated" in text and "naive" in text


def test_format_rate():
    assert format_rate(None) == "n/a"
    assert format_rate(0.5) == "0.50"
    assert format_rate(1.0) == "1.00"
