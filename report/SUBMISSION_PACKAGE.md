# Submission package — Receipts, Not Reports (M5 READY)

Staged 2026-11-05 22:41 PST. Deadline: **2026-11-08 23:59 AoE**
(Mon 2026-11-09 11:59 UTC / 03:59 PST). M5 READY target was 2026-11-08
12:00 PST; this package is ready ~2.5 days early.

## What is ready

- **Report PDF** — `report/Receipts_Not_Reports.pdf` (11 pages total:
  8 body pages + References + Appendices A–B). Body is inside the
  4–8 page cap; References and appendices are excluded from the count
  per the Guidelines. Abstract 230 words (template range 150–250).
  Official-template structure: Abstract, 1 Introduction,
  2 Related Work, 3 Methods, 4 Results (Tables 1–2 + Figure 1),
  5 Discussion and Limitations (+ Future Work), 6 Conclusion,
  Code and Data, Author Contributions, References,
  Appendix A Limitations and Dual-Use / Ethical Considerations
  (required), Appendix B Extended Results, LLM Usage Statement.
- **Report source** — `report/report.md` + `report/build_pdf.py`
  (WeasyPrint; rebuild with `python3 report/build_pdf.py`, which
  fails loudly if the body leaves 4–8 pages).
- **Code** — `src/receipts/` + `tests/` (59/59 green) +
  `experiments/run_sweep.py` + `experiments/results/` (sweep.json /
  sweep.md / sweep.png). Re-running the sweep reproduces
  byte-identical `sweep.json`/`sweep.md` (verified this round).
- **README** — final, with PREEXISTING VerifyGate labels and the
  correction that no LLM mode is implemented (scripted agents only).

## Headline numbers (all from real runs, guarded by tests/test_report.py)

Evidence-gated monitor: 446/450 tamper events detected (0.99), 0/85
spoofed claims accepted, 0 false positives, 0.0-round latency.
Naive monitor: 251/450 (0.56), 85/85 spoofed claims accepted,
27 false positives, 2.1-round mean latency. Known blind spot, reported
in the paper: same-round cancelling renames (4 missed events).

## Main agent still to do (NOT this worker's job)

1. Create the public code repository and add its link to the report's
   Code and Data section (currently: "included in the submission
   package; public link to be added on submission") and to the README.
   Rebuild the PDF after adding the link and re-check the page count.
2. Submit via the official sprint submission form before 2026-11-08
   23:59 AoE (same title on any resubmission replaces the old one).
3. Confirm the submission confirmation email arrives; check spam,
   else email sprints@apartresearch.com.
4. Do NOT submit by email (per FAQ: do not email the PDF).

## Open watch items (not blockers)

- Adaption $500 hackathon credit + 3mo Premium: still not visible as of
  this round (account shows Free plan, 1,000 signup credits); expected
  around kickoff 2026-11-06. Sentinel re-checks each round.
- Discord join: pending the user's phone-app action; announcements-only,
  not a build blocker.
