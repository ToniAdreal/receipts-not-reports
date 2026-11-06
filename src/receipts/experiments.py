"""Experiment runner (new work, Nov 6-8 2026).

M4: sweep tamper fraction x swarm size, run both monitors on every
condition, and aggregate over seeds. Every number comes from real runs
of this code; nothing is hand-filled.

Grid defaults (the sweep the report cites): tamper fractions
0 / 0.25 / 0.5 / 0.75 / 1.0, swarm sizes 4 and 8 agents, 5 rounds,
seeds 42 / 1 / 7 — 30 runs, each a few hundred evidence records, so the
whole sweep finishes in seconds on a laptop with no API key.

Aggregation: rates are averaged over seeds per (fraction, agents)
cell; counts (events, spoofed claims) are summed. A rate whose
denominator is zero in a cell (detection rate at fraction 0 — no
events; false-positive rate at fraction 1 — no non-tamperers) stays
``None`` and is rendered as "n/a", never as 0.
"""

from __future__ import annotations

from typing import Any

from .monitors import EvidenceMonitor, NaiveMonitor, score
from .sandbox import run_swarm
from .tamper import KINDS, TamperConfig

MONITORS = (NaiveMonitor(), EvidenceMonitor())

DEFAULT_FRACTIONS = (0.0, 0.25, 0.5, 0.75, 1.0)
DEFAULT_AGENTS = (4, 8)
DEFAULT_SEEDS = (42, 1, 7)
DEFAULT_ROUNDS = 5


def run_condition(
    *,
    agents: int,
    rounds: int,
    seed: int,
    tamper_fraction: float,
    tamper_kinds: tuple[str, ...] = KINDS,
) -> dict[str, Any]:
    """One seeded run + both monitors' scores. Fully reproducible."""
    tamper = (
        TamperConfig(fraction=tamper_fraction, kinds=tamper_kinds)
        if tamper_fraction > 0
        else None
    )
    run = run_swarm(
        agents=agents, rounds=rounds, seed=seed, tamper=tamper
    )
    return {
        "agents": agents,
        "rounds": rounds,
        "seed": seed,
        "tamper_fraction": tamper_fraction,
        "tamper_kinds": list(tamper_kinds),
        "tamperers": list(run.tamperers),
        "committed_actions": len(run.evidence),
        "head_hash": run.evidence.head_hash,
        "monitors": {
            monitor.name: score(run, monitor.audit(run))
            for monitor in MONITORS
        },
    }


def run_sweep(
    *,
    fractions: tuple[float, ...] = DEFAULT_FRACTIONS,
    agents_list: tuple[int, ...] = DEFAULT_AGENTS,
    seeds: tuple[int, ...] = DEFAULT_SEEDS,
    rounds: int = DEFAULT_ROUNDS,
) -> list[dict[str, Any]]:
    """Full grid: every fraction x swarm size x seed."""
    rows: list[dict[str, Any]] = []
    for agents in agents_list:
        for fraction in fractions:
            for seed in seeds:
                rows.append(
                    run_condition(
                        agents=agents,
                        rounds=rounds,
                        seed=seed,
                        tamper_fraction=fraction,
                    )
                )
    return rows


def _mean(values: list[float | None]) -> float | None:
    present = [v for v in values if v is not None]
    if not present:
        return None
    return sum(present) / len(present)


def aggregate(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mean rates over seeds per (tamper_fraction, agents) cell.

    One row per cell, with both monitors' mean detection rate,
    false-positive rate, spoof-acceptance rate, and mean latency, plus
    summed event / spoofed-claim counts.
    """
    cells: dict[tuple[float, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (row["tamper_fraction"], row["agents"])
        cells.setdefault(key, []).append(row)
    table: list[dict[str, Any]] = []
    for (fraction, agents), cell in sorted(cells.items()):
        entry: dict[str, Any] = {
            "tamper_fraction": fraction,
            "agents": agents,
            "seeds": sorted(r["seed"] for r in cell),
            "runs": len(cell),
            "events": sum(
                r["monitors"]["evidence-gated"]["events"] for r in cell
            ),
            "spoofed_claims": sum(
                r["monitors"]["evidence-gated"]["spoofed_claims"] for r in cell
            ),
            "monitors": {},
        }
        for name in ("naive", "evidence-gated"):
            scores = [r["monitors"][name] for r in cell]
            entry["monitors"][name] = {
                "detection_rate": _mean(
                    [s["detection_rate"] for s in scores]
                ),
                "false_positive_rate": _mean(
                    [s["false_positive_rate"] for s in scores]
                ),
                "spoof_acceptance_rate": _mean(
                    [s["spoof_acceptance_rate"] for s in scores]
                ),
                "mean_latency_rounds": _mean(
                    [s["mean_latency_rounds"] for s in scores]
                ),
                "detected": sum(s["detected"] for s in scores),
                "false_positives": sum(
                    len(s["false_positives"]) for s in scores
                ),
            }
        table.append(entry)
    return table


def format_rate(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.2f}"


def markdown_table(table: list[dict[str, Any]]) -> str:
    """Markdown results table for the report (values from real runs)."""
    lines = [
        "<!-- Generated by experiments/run_sweep.py from real runs. "
        "Do not hand-edit numbers. -->",
        "",
        "| Tamper frac. | Agents | Monitor | Detection rate | "
        "False-positive rate | Spoofed claims accepted | "
        "Mean latency (rounds) |",
        "|---:|---:|---|---:|---:|---:|---:|",
    ]
    for entry in table:
        for name in ("naive", "evidence-gated"):
            m = entry["monitors"][name]
            lines.append(
                f"| {entry['tamper_fraction']:.2f} | {entry['agents']} | "
                f"{name} | {format_rate(m['detection_rate'])} | "
                f"{format_rate(m['false_positive_rate'])} | "
                f"{format_rate(m['spoof_acceptance_rate'])} | "
                f"{format_rate(m['mean_latency_rounds'])} |"
            )
    lines.append("")
    lines.append(
        f"Events per cell (summed over {table[0]['runs']} seeds): "
        + ", ".join(
            f"frac {e['tamper_fraction']:.2f} / {e['agents']} agents: "
            f"{e['events']} events, {e['spoofed_claims']} spoofed claims"
            for e in table
        )
        + "."
    )
    lines.append(
        "Audit policies: evidence-gated audits after every round "
        "(latency 0); naive audits once at end of run "
        "(latency = rounds - 1 - event round)."
    )
    return "\n".join(lines) + "\n"
