---
name: finding-skill-opportunities
description: Use when asked to find skill opportunities in a codebase, audit a repo for automatable workflows, decide what skills to write, or mine git history and existing automation for recurring multi-step procedures worth turning into Claude Code skills.
---

# Finding Skill Opportunities

## Overview

A **skill opportunity** is a recurring, multi-step procedure that involves judgment and keeps getting repeated by hand. Git history and a codebase's existing automation are the evidence: the procedures a team performs over and over leave fingerprints — repeated commit types, files that always change together, release/migration keywords, half-written Makefile targets and runbook docs.

This skill scans those fingerprints **deterministically** (via the bundled scripts) so you don't eyeball thousands of commits, then applies judgment to turn the raw signals into a ranked list of skill candidates with evidence.

**Core principle:** Let the scripts find the *repetition*; you decide which repetitions are worth a skill.

## When to Use

- "What skills should we write for this repo?"
- Auditing a codebase for automatable or skill-worthy workflows
- Onboarding to an unfamiliar repo and wanting to know its recurring rituals
- Before writing skills, to ground them in real evidence instead of guesses

**Not for:** writing the skill itself (use `superpowers:writing-skills` once you've picked a candidate) or one-off tasks with no repetition.

## Workflow

Run the two scripts, then synthesize. Both are read-only and deterministic.

1. **Mine git history** for repetition signals:
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/git-signals.sh" --repo <path> --top 20
   # optionally scope recent work: --since "1 year ago"
   ```

2. **Inventory existing workflow encodings** (these are the lowest-hanging fruit — the steps already exist):
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/scan-workflows.sh" --repo <path>
   ```

3. **Cross-reference and synthesize.** A signal is strong when it shows up in *both* outputs — e.g. release keywords in commit subjects AND a `release` package.json script AND a `CHANGELOG`/manifest co-change cluster all describe one release procedure.

4. **Rank candidates** against the criteria below and write the report (see Output).

5. **Hand each chosen candidate to `superpowers:writing-skills`** to author the actual SKILL.md. This skill finds opportunities; it does not write the skills.

## Signal Interpretation

What each script section tends to mean:

| Signal (from `git-signals.sh`) | Likely skill opportunity |
| :----------------------------- | :----------------------- |
| High-frequency commit **prefix** (e.g. many `chore:`, `release:`) | A routine procedure tied to that type |
| **Recurring keywords** (release, deploy, migrate, bump, regenerate, rotate, seed, backfill) | The named chore is done repeatedly by hand |
| **Hot files** (changed in many commits) | A repeated editing ritual centered on that file |
| **Co-changed pairs** (files that move together) | A "change A, remember to also change B" procedure — high-value, easy to forget steps |
| **Busiest directories** | Where the team's repeated work concentrates |

| Signal (from `scan-workflows.sh`) | Likely skill opportunity |
| :-------------------------------- | :----------------------- |
| Makefile targets / package.json scripts / task-runner recipes | Commands a skill can wrap with context and judgment |
| CI workflow jobs | Procedures currently only encoded for machines — a human/agent equivalent may be missing |
| `scripts/` and `bin/` entries | Existing automation that a skill can orchestrate |
| "How to" / runbook doc sections | Procedural knowledge already written in prose, ready to become a skill |
| **Existing skills** | Do NOT propose these — gaps, not duplicates, are the goal |

## What Makes a Good Skill Candidate

Rank each candidate by these. A strong candidate hits most of them:

- **Recurring** — happens repeatedly (the signals prove this), not once.
- **Multi-step** — enough steps that order and completeness matter.
- **Error-prone / forgettable** — co-change pairs and "don't forget to also…" rituals are gold.
- **Involves judgment** — if it's purely mechanical and a script already does it end-to-end, it may not need a *skill* (point to the script instead).
- **Reusable / generalizable** — applies across the project, not a single fix.
- **Not already a skill** — check the existing-skills section first.

Drop candidates that are: one-offs, already fully automated with no judgment, or purely project-trivia better left in a CLAUDE.md.

## Output

Produce a ranked report, strongest first. For each candidate:

```
### <candidate skill name (verb-first, e.g. "cutting-a-release")>
Evidence:   <which signals, with counts — e.g. "52 'release' subjects;
            CHANGELOG.md+package.json co-change x62; package.json `release` script">
Procedure:  <the repeated steps, as far as the evidence reveals them>
Why a skill: <which criteria it hits>
Next step:  hand to superpowers:writing-skills
```

End with a short list of signals you considered and **rejected**, so the audit is auditable (e.g. "lockfile churn — mechanical, no skill needed").

## Common Mistakes

- **Proposing skills for fully-mechanical tasks.** If a script already does it with no decisions, recommend the script, not a skill.
- **Ignoring co-change pairs.** They're the highest-signal section — they reveal the steps humans forget.
- **Duplicating existing skills.** Always read the existing-skills section of `scan-workflows.sh` first.
- **Trusting one signal.** Confidence comes from corroboration across both scripts.
- **Writing the skill here.** This skill stops at a ranked candidate list; authoring is `superpowers:writing-skills`.

## Scripts

- `scripts/git-signals.sh` — deterministic git-history analysis (prefixes, keywords, hot files, co-change pairs, busy dirs). `--repo`, `--since`, `--top`. Run `--help` for details.
- `scripts/scan-workflows.sh` — inventories Makefiles, package.json scripts, task runners, CI, `scripts/`, runbook docs, and existing skills. `--repo`. Run `--help` for details.

Both default to the current directory and emit sorted, timestamp-free output, so reruns on unchanged history are byte-identical.

**If a script can't run here** (missing `bash`/a tool, or a different OS): don't abandon the task — the scripts only automate ordinary git/text commands, so reproduce the same steps directly with whatever tools this environment has.
