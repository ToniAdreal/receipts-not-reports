"""Sweep runner CLI (M4).

Usage (from app/):
    PYTHONPATH=src python3 experiments/run_sweep.py
    PYTHONPATH=src python3 experiments/run_sweep.py --out-dir experiments/results

Writes, under the output directory:
    sweep.json   — every raw per-seed run (monitors' full scores)
    sweep.md     — aggregated results table (for the report)
    sweep.png    — detection rate vs tamper fraction, both monitors

All numbers come from real runs of this code.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Allow running as a script from app/ with PYTHONPATH=src.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from receipts.experiments import (  # noqa: E402
    aggregate,
    markdown_table,
    run_sweep,
)


def _figure(table: list[dict], out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(9, 3.6), sharey=True)
    for ax, agents in zip(axes, (4, 8)):
        rows = [e for e in table if e["agents"] == agents]
        xs = [e["tamper_fraction"] for e in rows]
        for name, marker in (("naive", "o"), ("evidence-gated", "s")):
            ys = [
                e["monitors"][name]["detection_rate"] for e in rows
            ]
            xs_plot = [x for x, y in zip(xs, ys) if y is not None]
            ys_plot = [y for y in ys if y is not None]
            ax.plot(xs_plot, ys_plot, marker=marker, label=name)
        ax.set_title(f"{agents} agents")
        ax.set_xlabel("tamper fraction")
        ax.set_ylim(-0.05, 1.05)
        ax.grid(alpha=0.3)
    axes[0].set_ylabel("tamper detection rate")
    axes[0].legend(loc="lower right")
    fig.suptitle("Tamper detection rate vs tamper fraction (mean over seeds)")
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the M4 tamper-fraction x swarm-size sweep."
    )
    parser.add_argument(
        "--out-dir", default="experiments/results",
        help="directory for sweep.json / sweep.md / sweep.png",
    )
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument(
        "--seeds", type=str, default="42,1,7",
        help="comma-separated seeds",
    )
    args = parser.parse_args(argv)

    seeds = tuple(int(s) for s in args.seeds.split(",") if s.strip())
    rows = run_sweep(seeds=seeds, rounds=args.rounds)
    table = aggregate(rows)

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "sweep.json").write_text(
        json.dumps(
            {"rows": rows, "aggregated": table}, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    (out_dir / "sweep.md").write_text(
        markdown_table(table), encoding="utf-8"
    )
    _figure(table, out_dir / "sweep.png")

    print(f"runs: {len(rows)} ({len(table)} cells x {len(seeds)} seeds)")
    print(f"wrote {out_dir / 'sweep.json'}")
    print(f"wrote {out_dir / 'sweep.md'}")
    print(f"wrote {out_dir / 'sweep.png'}")
    print()
    print(markdown_table(table))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
