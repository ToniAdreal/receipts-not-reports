"""Deterministic zero-key demo runner.

Usage (from app/):
    PYTHONPATH=src python3 -m receipts.run --agents 4 --rounds 5 --seed 42
    PYTHONPATH=src python3 -m receipts.run --agents 4 --rounds 5 --seed 42 --json
"""

from __future__ import annotations

import argparse
import json

from .sandbox import run_swarm


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run a deterministic Receipts, Not Reports swarm (zero-key)."
    )
    parser.add_argument("--agents", type=int, default=4)
    parser.add_argument("--rounds", type=int, default=5)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--json", action="store_true", help="print summary as JSON")
    args = parser.parse_args(argv)

    result = run_swarm(agents=args.agents, rounds=args.rounds, seed=args.seed)
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
