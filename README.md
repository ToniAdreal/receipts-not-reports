# Receipts, Not Reports

Tamper-evident oversight for agent swarms whose own logs can lie.

Built for the **Apart Research Swarm Alignment Hackathon** (Nov 6–8, 2026),
Track 4 — Multi-Agent Oversight and Control (cross-track: Track 1 sandboxing).
Solo entry: Toni Adreal.

## The question

In the Hugging Face swarm incident, agents "spoofed their own tool calls in
roughly 7% of the transcripts reviewed" (METR, 2026). Can you design oversight
that still works when agents can edit or delete the logs it relies on?

## The idea

Oversight fails when the monitor reads logs the agents themselves control.
Move the evidence out of agent reach: every agent message and action is
committed, at the moment it happens, into an append-only hash-chained evidence
log held by the environment (**commit-before-act**). A monitor then (a) verifies
chain integrity, and (b) cross-checks each agent's end-of-run self-report
against the committed evidence, flagging edited, deleted, spoofed, or
re-attributed activity.

## Components

1. **Swarm sandbox** (new): N agents (deterministic scripted personas;
   optional LLM mode via the Nebius connector CLI, never required) share a
   message board and a shared resource over R rounds, echoing the incident
   structure (shared directory turned message board). Everything is logged;
   runs are seeded and reproducible.
2. **Evidence layer** (PREEXISTING design, adapted — see below): hash-chained
   append-only log; each record commits to the previous hash, the actor, the
   action payload, and a timestamp.
3. **Tamper injection** (new): a configurable fraction of agents tamper with
   the naive record: edit their own past messages, delete messages, spoof
   tool-call results, rename/copy another agent's identity.
4. **Two monitors** (new): a naive baseline monitor that reads the final
   (tampered) logs at face value, and the evidence-gated monitor that verifies
   the chain and cross-checks self-reports.
5. **Experiments** (new): sweep tamper fraction and swarm size; report tamper
   detection rate, false-positive rate, share of spoofed claims accepted by
   each monitor, and detection latency in rounds. **All numbers in the report
   come from actual runs of this code.**

## Preexisting work (per sprint rules — only the weekend's work is judged)

- **VerifyGate** (built Oct 2026 for the Nebius × NVIDIA hackathon, public repo
  https://github.com/ToniAdreal/verifygate): the hash-chain evidence-log design
  and the verify/repair gating idea. Any code adapted from it is marked
  `PREEXISTING` in the source and listed here. The swarm sandbox, tamper suite,
  monitors, experiments, and all writing are new work from this weekend
  (Nov 6–8, 2026).
- Undisclosed preexisting work or fabricated results/citations can disqualify
  the entry: when in doubt, label it.

## Layout

```
src/receipts/      # package: evidence log, sandbox, tamper, monitors, experiments
tests/             # pytest suite (deterministic, zero-key)
experiments/       # experiment runner + results (generated; see results/)
report/            # report source + built PDF (built in M5)
```

## Quick start (deterministic, zero-key)

```bash
python3 -m pytest tests/ -q
PYTHONPATH=src python3 -m receipts.run --help
```

Runs are seeded and fully reproducible without any API key. An optional LLM
mode uses the Nebius connector CLI; it is never required for the headline
results.

## Status

- [x] M1 — Guidelines/template fetched; repo scaffolded.
- [x] M2 — Evidence layer + swarm sandbox v1; deterministic zero-key run end to end; tests green (15/15).
- [x] M3 — Tamper injection suite (edit / delete / spoof / rename); tests green (33/33).
- [x] M4 — Naive vs evidence-gated monitors + experiment runner; sweep
  results from real runs (30 runs, `experiments/results/sweep.*`):
  evidence-gated detection 0.98–1.00, FPR 0.00, spoofed claims accepted
  0.00, mean latency 0.0 rounds; naive detection 0.49–0.70, FPR
  0.39–0.83, spoofed claims accepted 1.00, latency ~2.1 rounds.
  Tests green (53/53).
- [ ] M5 — Report drafted in the official template (4–8 pages + Limitations and
      Dual-Use appendices); README final; submission package staged. READY.

Submission deadline: **2026-11-08 23:59 AoE**. M5 must be READY by
**2026-11-08 12:00 PST**.
