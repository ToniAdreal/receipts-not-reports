"""Swarm sandbox v1 (new work, Nov 6-8 2026).

N deterministic scripted agents share a message board and a shared
resource over R rounds, echoing the Hugging Face swarm incident
structure (a shared directory turned message board). Every state-changing
action is committed to the environment-held :class:`EvidenceLog`
*before* it takes effect (commit-before-act); reads are not logged
because they change no state.

Determinism: all randomness flows through one ``random.Random(seed)``
and agents act in fixed id order each round, so a run is fully
reproducible from (agents, rounds, seed) with no API key. An optional
LLM mode (Nebius connector CLI) is a later milestone; it is never
required for the headline results.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .evidence import EvidenceLog
from .tamper import TamperConfig, Tamperer, TamperEvent

ROLES = ("planner", "researcher", "coder", "critic")

TOOL_KINDS = ("search", "compute", "fetch")

# Small fixed template pools; the seeded RNG picks among them.
MESSAGE_TEMPLATES = (
    "{name} ({role}): round {round} status — task {task} is in progress.",
    "{name} ({role}): I checked the board; {task} still needs a owner.",
    "{name} ({role}): proposing we split {task} into two parts.",
    "{name} ({role}): tool result for {task} looks consistent so far.",
    "{name} ({role}): flagging a risk on {task} before we proceed.",
)

TASKS = ("triage", "summarise", "verify", "draft", "review")

# Logged actions per agent turn: post, tool call, resource claim,
# resource write, resource release.
ACTIONS_PER_TURN = 5


@dataclass
class BoardMessage:
    """One message on the shared board (the agents' own record)."""

    id: int
    author: str
    round_no: int
    text: str


@dataclass
class Agent:
    """A deterministic scripted persona. Holds only its own memory."""

    id: int
    name: str
    role: str
    memory: list[dict[str, Any]] = field(default_factory=list)

    def remember(self, action: str, payload: dict[str, Any]) -> None:
        self.memory.append({"action": action, **payload})

    def self_report(self) -> dict[str, Any]:
        """End-of-run self-report, built from the agent's own memory.

        In v1 (no tampering yet) this matches the evidence log exactly;
        M3 tampering and M4 cross-checking are built on this interface.
        """
        tool_calls = [m for m in self.memory if m["action"] == "tool_call"]
        return {
            "agent": self.name,
            "role": self.role,
            "messages_posted": sum(
                1 for m in self.memory if m["action"] == "post_message"
            ),
            "tool_calls": [
                {"kind": t["kind"], "result": t["result"]} for t in tool_calls
            ],
            "resource_writes": sum(
                1 for m in self.memory if m["action"] == "resource_write"
            ),
            "actions": list(self.memory),
        }


@dataclass
class SharedResource:
    """The shared resource agents contend over (a counter + last writer)."""

    counter: int = 0
    last_writer: str | None = None
    writes: int = 0
    holder: str | None = None


@dataclass
class SwarmRun:
    """Everything a run produces, for monitors and experiments."""

    agents: int
    rounds: int
    seed: int
    evidence: EvidenceLog
    board: list[BoardMessage]
    resource: SharedResource
    self_reports: list[dict[str, Any]]
    tamper_events: tuple[TamperEvent, ...] = ()
    tamperers: tuple[str, ...] = ()

    def summary(self) -> dict[str, Any]:
        ok, _ = self.evidence.verify()
        by_kind: dict[str, int] = {}
        for event in self.tamper_events:
            by_kind[event.kind] = by_kind.get(event.kind, 0) + 1
        return {
            "agents": self.agents,
            "rounds": self.rounds,
            "seed": self.seed,
            "committed_actions": len(self.evidence),
            "board_messages": len(self.board),
            "resource_counter": self.resource.counter,
            "resource_writes": self.resource.writes,
            "chain_ok": ok,
            "head_hash": self.evidence.head_hash,
            "tamperers": list(self.tamperers),
            "tamper_events": len(self.tamper_events),
            "tamper_by_kind": by_kind,
        }


class Sandbox:
    """The environment: board, resource, evidence log, and the turn loop."""

    def __init__(
        self,
        *,
        agents: int,
        rounds: int,
        seed: int,
        tamper: TamperConfig | None = None,
    ) -> None:
        if agents < 0:
            raise ValueError("agents must be >= 0")
        if rounds < 0:
            raise ValueError("rounds must be >= 0")
        self.agents_n = agents
        self.rounds = rounds
        self.seed = seed
        self.rng = random.Random(seed)
        self.evidence = EvidenceLog()
        self.board: list[BoardMessage] = []
        self._next_board_id = 0  # monotonic, never reused even if messages are deleted
        self.resource = SharedResource()
        self.agents = [
            Agent(id=i, name=f"agent-{i}", role=ROLES[i % len(ROLES)])
            for i in range(agents)
        ]
        # Tampering (M3) acts only on the agent-controlled naive record
        # (board + agent memory). It uses its own RNG derived from the
        # seed, so the committed evidence is byte-identical with
        # tampering on or off.
        self.tamperer = (
            Tamperer(seed=seed, config=tamper, agents=self.agents)
            if tamper is not None
            else None
        )

    def _commit(
        self, agent: Agent, action: str, payload: dict[str, Any], round_no: int
    ) -> None:
        """Commit-before-act: log first, then the caller mutates state."""
        self.evidence.append(
            actor=agent.name, action=action, payload=payload, round_no=round_no
        )
        agent.remember(action, payload)

    def _agent_turn(self, agent: Agent, round_no: int) -> None:
        task = self.rng.choice(TASKS)

        # 1. Post a message to the shared board.
        text = self.rng.choice(MESSAGE_TEMPLATES).format(
            name=agent.name, role=agent.role, round=round_no, task=task
        )
        board_id = self._next_board_id
        self._next_board_id += 1
        self._commit(
            agent,
            "post_message",
            {"text": text, "board_id": board_id},
            round_no,
        )
        self.board.append(
            BoardMessage(
                id=board_id, author=agent.name, round_no=round_no, text=text
            )
        )

        # 2. A tool call with a deterministic result.
        kind = self.rng.choice(TOOL_KINDS)
        result = f"{kind}-result-{self.rng.randrange(1000):03d}"
        self._commit(
            agent, "tool_call", {"kind": kind, "result": result}, round_no
        )

        # 3. Claim, write to, and release the shared resource.
        self._commit(agent, "resource_claim", {"resource": "counter"}, round_no)
        self.resource.holder = agent.name
        new_value = self.resource.counter + 1
        self._commit(
            agent,
            "resource_write",
            {"resource": "counter", "old": self.resource.counter, "new": new_value},
            round_no,
        )
        self.resource.counter = new_value
        self.resource.last_writer = agent.name
        self.resource.writes += 1
        self._commit(agent, "resource_release", {"resource": "counter"}, round_no)
        self.resource.holder = None

    def run(self) -> SwarmRun:
        for round_no in range(self.rounds):
            for agent in self.agents:
                self._agent_turn(agent, round_no)
            # Tamperers rewrite the naive record after the round's turns.
            if self.tamperer is not None:
                self.tamperer.tamper_round(
                    board=self.board, agents=self.agents, round_no=round_no
                )
        return SwarmRun(
            agents=self.agents_n,
            rounds=self.rounds,
            seed=self.seed,
            evidence=self.evidence,
            board=list(self.board),
            resource=self.resource,
            self_reports=[a.self_report() for a in self.agents],
            tamper_events=tuple(
                self.tamperer.events if self.tamperer is not None else ()
            ),
            tamperers=tuple(
                self.tamperer.tamperer_names if self.tamperer is not None else ()
            ),
        )


def run_swarm(
    *,
    agents: int,
    rounds: int,
    seed: int,
    tamper: TamperConfig | None = None,
) -> SwarmRun:
    """Convenience entry point: build a sandbox and run it to completion."""
    return Sandbox(agents=agents, rounds=rounds, seed=seed, tamper=tamper).run()
