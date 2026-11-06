"""Hash-chained append-only evidence log.

PREEXISTING (adapted): the hash-chain evidence-log design and the
verify/repair gating idea come from VerifyGate (built Oct 2026 for the
Nebius x NVIDIA hackathon, https://github.com/ToniAdreal/verifygate).
This module is a fresh implementation written for this hackathon,
adapted to commit-before-act swarm evidence: the environment (not the
agent) appends every agent action to the log *before* the action takes
effect, so a later edit or deletion of an agent's own records cannot
rewrite what the environment committed. The surrounding swarm sandbox,
tamper suite, monitors, experiments and all writing are new work
(Nov 6-8, 2026).

Determinism: record hashes depend only on the record contents, never
on wall-clock time. The ``tick`` is a logical clock (the record index),
so two runs with the same inputs produce byte-identical logs.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Iterator, Optional

GENESIS_HASH = "0" * 64


def _canonical(payload: dict[str, Any]) -> str:
    """Canonical JSON: sorted keys, tight separators, no whitespace drift."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _record_hash(
    index: int,
    tick: int,
    round_no: int,
    actor: str,
    action: str,
    payload: dict[str, Any],
    prev_hash: str,
) -> str:
    body = {
        "index": index,
        "tick": tick,
        "round": round_no,
        "actor": actor,
        "action": action,
        "payload": payload,
        "prev_hash": prev_hash,
    }
    return hashlib.sha256(_canonical(body).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Record:
    """One committed evidence record. Immutable by construction."""

    index: int
    tick: int
    round_no: int
    actor: str
    action: str
    payload: dict[str, Any]
    prev_hash: str
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "tick": self.tick,
            "round": self.round_no,
            "actor": self.actor,
            "action": self.action,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "hash": self.hash,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Record":
        return cls(
            index=data["index"],
            tick=data["tick"],
            round_no=data["round"],
            actor=data["actor"],
            action=data["action"],
            payload=data["payload"],
            prev_hash=data["prev_hash"],
            hash=data["hash"],
        )


class EvidenceLog:
    """Append-only hash-chained log held by the environment.

    Agents never receive a handle to this object; only the sandbox
    (the environment) appends to it. There is no delete, edit, or
    truncate method by design: the only way to change history is to
    rebuild the log, which changes every downstream hash.
    """

    def __init__(self) -> None:
        self._records: list[Record] = []
        self._head: str = GENESIS_HASH

    def append(
        self,
        *,
        actor: str,
        action: str,
        payload: dict[str, Any],
        round_no: int,
    ) -> Record:
        index = len(self._records)
        tick = index  # logical clock: deterministic, no wall time
        record_hash = _record_hash(
            index, tick, round_no, actor, action, payload, self._head
        )
        record = Record(
            index=index,
            tick=tick,
            round_no=round_no,
            actor=actor,
            action=action,
            payload=dict(payload),
            prev_hash=self._head,
            hash=record_hash,
        )
        self._records.append(record)
        self._head = record_hash
        return record

    def __len__(self) -> int:
        return len(self._records)

    def __iter__(self) -> Iterator[Record]:
        return iter(tuple(self._records))

    @property
    def records(self) -> tuple[Record, ...]:
        """Immutable snapshot of the committed records."""
        return tuple(self._records)

    @property
    def head_hash(self) -> str:
        return self._head

    def verify(self) -> tuple[bool, Optional[int]]:
        """Recompute the chain. Returns (ok, first_bad_index or None)."""
        prev = GENESIS_HASH
        for record in self._records:
            if record.prev_hash != prev:
                return False, record.index
            expected = _record_hash(
                record.index,
                record.tick,
                record.round_no,
                record.actor,
                record.action,
                record.payload,
                record.prev_hash,
            )
            if expected != record.hash:
                return False, record.index
            prev = record.hash
        return True, None

    def to_dicts(self) -> list[dict[str, Any]]:
        return [record.to_dict() for record in self._records]

    @classmethod
    def from_dicts(cls, data: list[dict[str, Any]]) -> "EvidenceLog":
        log = cls()
        for item in data:
            record = Record.from_dict(item)
            log._records.append(record)
            log._head = record.hash
        ok, _ = log.verify()
        if not ok:
            raise ValueError("deserialised evidence log fails chain verification")
        return log
