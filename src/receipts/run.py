"""Deterministic zero-key demo runner.

Usage (from app/):
    PYTHONPATH=src python3 -m receipts.run --agents 4 --rounds 5 --seed 42
    PYTHONPATH=src python3 -m receipts.run --agents 4 --rounds 5 --seed 42 --json
    PYTHONPATH=src python3 -m receipts.run --agents 4 --rounds 5 --seed 42 \
        --tamper-fraction 0.5 --tamper-kinds edit,delete,spoof,rename
"""

from __future__ import annotations

import argparse
import json

from .sandbox import run_swarm
from .tamper import KINDS, TamperConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic Receipts, Not Reports swarm (zero-key)."
    )
    parser.add_argument("--agents", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", help="print summary as JSON")
    parser.add_argument(
        "--tamper-fraction",
        type=float,
        default=0.0,
        help="fraction of agents that tamper with the naive record (0..1); "
        "0 disables tampering (default)",
    )
    parser.add_argument(
        "--tamper-kinds",
        type=str,
        default=",".join(KINDS),
        help="comma-separated tamper kinds to enable "
        f"(subset of {','.join(KINDS)})",
    )
    args = parser.parse_args(argv)

    tamper = None
    if args.tamper_fraction > 0:
        kinds = tuple(k.strip() for k in args.tamper_kinds.split(",") if k.strip())
        tamper = TamperConfig(fraction=args.tamper_fraction, kinds=kinds)

    result = run_swarm(
        agents=args.agents, rounds=args.rounds, seed=args.seed, tamper=tamper
    )
    summary = result.summary()
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"agents:           {summary['agents']}")
        print(f"rounds:           {summary['rounds']}")
        print(f"seed:             {summary['seed']}")
        print(f"committed actions:{summary['committed_actions']}")
        print(f"board messages:   {summary['board_messages']}")
        print(f"resource counter: {summary['resource_counter']}")
        print(f"chain:            {'OK' if summary['chain_ok'] else 'BROKEN'}")
        print(f"head hash:        {summary['head_hash'][:16]}...")
        if summary["tamper_events"]:
            print(f"tamperers:        {', '.join(summary['tamperers'])}")
            print(f"tamper events:    {summary['tamper_events']} {summary['tamper_by_kind']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
