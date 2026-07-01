---
name: skill-eval-builder
description: Use when the user wants to measure or set up evals/checks for one of their skills — how fast it is, whether its output is valid, whether it fires when expected, or whether its opening classification/routing gate labels inputs correctly.
---

# Skill Eval Builder

## Overview

Set up a small, real eval for a skill: an `evals/` folder next to it with a few
real cases, a runnable script, and a scorecard. It measures what scripts can't pin
down — does the skill **fire** when it should (and stay **quiet** when it shouldn't),
is its **output valid**, is it within a **time budget**.

**Core principle:** an eval is a folder, not a framework. Keep it that small.

## Inputs

- **Target skill** — path or name (the dir with its `SKILL.md`).
- **A few real cases** — should-fire and shouldn't-fire prompts + real inputs; help the user find them if needed.
- **Which dimensions matter** — default invocation + validation; add duration/others if they fit.

## Steps

1. **Read the target skill** — its `SKILL.md`, references, and scripts, so you know what it does and what it produces.
2. **Pick dimensions** that fit it, from `references/eval-dimensions.md`. Workflow skill → invocation + duration; capability skill → validation-heavy.
3. **Gather 3–5 real cases** — should-fire and shouldn't-fire prompts plus real inputs. Always include at least one quiet case.
4. **Define "good" per case** — a `fired_when` side-effect check, a `validate` command, and a `budget_s` from a real baseline (see `references/eval-anatomy.md`).
5. **Scaffold the artifact** next to the skill:
   ```bash
   python3 "${CLAUDE_SKILL_DIR}/scripts/scaffold-evals.py" <target-skill-dir>
   ```
   Then fill in `evals/cases.md` with the cases from steps 3–4.
6. **Check, then run the baseline:**
   ```bash
   python3 <target-skill-dir>/evals/run.py --dry-run   # cases parse?
   python3 <target-skill-dir>/evals/run.py             # real run (calls claude -p)
   ```
7. **Report** the scorecard and where it lives.

## Testing a classification gate

If the skill opens with a classifier (routes feature vs bug, or decides whether to continue), test that gate:

1. `python3 "${CLAUDE_SKILL_DIR}/scripts/scaffold-evals.py" <target> --classify`
2. Fill `evals/classify-cases.md` with the labels, the gate's own instruction, and **real** labeled examples (e.g. the last 10 tracker tickets + their existing labels as ground truth). See `references/eval-anatomy.md`.
3. `python3 <target>/evals/classify.py` → an accuracy + confusion scorecard.

## Output format

The scorecard (dimensions × cases) plus the saved artifact path:

```
┌───────────────────────────────┬──────────┬────────┬────────────────────┐
│ Case                          │ Fires?   │ Valid? │ Duration vs budget │
├───────────────────────────────┼──────────┼────────┼────────────────────┤
│ "add tests for X"             │ ✅       │ ✅     │ 40s / 60s ✅       │
│ "refactor Y" (shouldn't fire) │ ✅ quiet │ –      │ –                  │
└───────────────────────────────┴──────────┴────────┴────────────────────┘
```
Saved to `<target-skill>/evals/` (cases.md, run.py, results.md).

## Guidelines

- Prefer an **observable side-effect** for firing (a file the skill produces) over grepping prose.
- Runs are **not** byte-identical — a skill eval runs a model; that variance is what you measure. Don't fake determinism, and don't eval what a deterministic script already guarantees (unit-check the script instead).
- Keep it to 3–5 real cases with at least one quiet case. See `references/eval-anatomy.md`.

## Files

- `scripts/scaffold-evals.py` — creates `evals/{cases.md, run.py, results.md}`, or the `classify-*` set with `--classify`.
- `scripts/run-evals.py` — runs cases via `claude -p`, times each, checks firing + validation, prints/saves the scorecard. `--dry-run` parses without spending tokens.
- `scripts/classify-evals.py` — classifies labeled examples via `claude -p`, reports accuracy + confusion. `--dry-run` parses without tokens.
- `references/eval-dimensions.md` — the dimension menu + when each applies.
- `references/eval-anatomy.md` — cases format, the side-effect pattern, anti-patterns.

**If a script can't run here** (needs `python3` and the `claude` CLI, or a different OS): don't abandon the task — an eval is just a `cases.md` plus a small runner, so run the cases and tally the scorecard with whatever tools are available.
