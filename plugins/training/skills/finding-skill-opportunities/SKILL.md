---
name: finding-skill-opportunities
description: Use when asked to find skill opportunities in a codebase, audit a repo for automatable workflows, decide what skills to write, or mine git history, existing automation, and recent Claude Code session transcripts for recurring multi-step procedures worth turning into Claude Code skills.
---

# Finding Skill Opportunities

## Overview

A **skill opportunity** is a recurring, multi-step procedure that involves judgment and keeps getting repeated by hand. Two independent bodies of evidence show where those live:

- **The repo** — git history and existing automation. Repeated commit types, files that always change together, release/migration keywords, half-written Makefile targets and runbook docs.
- **The sessions** — local Claude Code transcripts. What people actually *asked for*, the tool sequences they ran, and the files they touched.

They fail in opposite directions, which is why the default is both. Git sees only work that ended in a commit, so a ritual done by hand every week in a repo nobody commits to is invisible to it. Sessions see the ask but not the long arc, and they only cover the transcripts on *this* machine.

This skill scans both **deterministically** (via the bundled scripts) so you don't eyeball thousands of commits or sessions, then applies judgment to turn the raw signals into a ranked list of skill candidates with evidence.

**Core principle:** Let the scripts find the *repetition*; you decide which repetitions are worth a skill.

## When to Use

- "What skills should we write for this repo?"
- Auditing a codebase for automatable or skill-worthy workflows
- Onboarding to an unfamiliar repo and wanting to know its recurring rituals
- Before writing skills, to ground them in real evidence instead of guesses

**Not for:** writing the skill itself (use `superpowers:writing-skills` once you've picked a candidate) or one-off tasks with no repetition.

## Inputs

| Input | Default | How to set |
| :---- | :------ | :--------- |
| **Repo** | current directory | `--repo <path>` on every script |
| **Lookback days** | 30 | `--days N` on both mining scripts. Larger windows find slower rituals (quarterly releases); smaller ones show what the team is doing *now*. |
| **Source** | both | `git` = repo evidence only; `sessions` = transcripts only; `both` = run everything and corroborate |
| Rows per section | 20 | `--top N` |

Take these from the user's request; don't interrogate them for defaults. Pick `sessions` only when the repo's history is irrelevant or absent, and `git` when transcripts are unavailable (someone else's machine, a repo you just cloned). **Always state the window and sources you used in the report** — a candidate list means little without knowing what was looked at.

## Workflow

All scripts are read-only and deterministic. Run the ones the chosen source calls for, then synthesize.

1. **Mine git history** (source `git` or `both`):
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/git-signals.sh" --repo <path> --days 30 --top 20
   # or an absolute cutoff / free-form date: --since "1 year ago"
   ```

2. **Inventory existing workflow encodings** (source `git` or `both`; lowest-hanging fruit — the steps already exist):
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/scan-workflows.sh" --repo <path>
   ```

3. **Mine session transcripts** (source `sessions` or `both`):
   ```bash
   uv run python "${CLAUDE_SKILL_DIR}/scripts/session-signals.py" --repo <path> --days 30 --top 20
   # widen beyond this repo's sessions: --scope all
   ```
   Reads `~/.claude/projects/*/*.jsonl`. Defaults to sessions whose working directory is the repo or below it. If it reports 0 sessions in scope, the work happened elsewhere — retry with `--scope all` before concluding there's nothing there.

   Invoke Python as `uv run python` on this user's machine (bare `python` hits the Windows Store stub); the script is pure standard library, so `python3 …` works anywhere else.

   **Privacy:** transcripts are the user's own prompts and can quote client material. The script only reads them, but its output can include prompt snippets — pass `--no-examples` whenever the report will be shared or committed.

4. **Cross-reference and synthesize.** A signal is strong when it shows up in *more than one* output — release keywords in commit subjects AND a `release` package.json script AND a `CHANGELOG` co-change cluster all describe one release procedure. Session hot files print repo-relative so they line up directly with the git hot-file rows.

   Disagreement is itself a finding: something heavy in sessions but absent from git is work that never lands in a commit (often the most skill-worthy kind), while something heavy in git but absent from sessions is probably already automated or done outside Claude.

5. **Rank candidates** against the criteria below and write the report (see Output).

6. **Hand each chosen candidate to `superpowers:writing-skills`** to author the actual SKILL.md. This skill finds opportunities; it does not write the skills.

## Signal Interpretation

Every ranked section means something specific, and the meanings differ by source. Read `references/signal-interpretation.md` once the outputs are in front of you — it maps each section of each script to the kind of opportunity it implies, including which sections are volume-only and which name a candidate outright.

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
Evidence:   <which signals, with counts, each tagged by source — e.g.
            "git: 52 'release' subjects, CHANGELOG.md+package.json co-change x62;
            sessions: 9 'release ...' request clusters, Bash->gh->Bash x14">
Procedure:  <the repeated steps, as far as the evidence reveals them>
Why a skill: <which criteria it hits>
Next step:  hand to superpowers:writing-skills
```

Open the report with the scope line: sources mined, lookback window, and volume (commits and/or sessions analyzed).

End with a short list of signals you considered and **rejected**, so the audit is auditable (e.g. "lockfile churn — mechanical, no skill needed").

## Common Mistakes

- **Proposing skills for fully-mechanical tasks.** If a script already does it with no decisions, recommend the script, not a skill.
- **Ignoring co-change pairs.** They're the highest-signal section — they reveal the steps humans forget.
- **Duplicating existing skills.** Always read the existing-skills section of `scan-workflows.sh` first.
- **Trusting one signal.** Confidence comes from corroboration across sources.
- **Reporting a narrow window as the whole story.** Sessions cover only this machine's transcripts and git only committed work; name both limits instead of implying full coverage.
- **Leaking prompt snippets.** Use `--no-examples` for any report that leaves the machine.
- **Writing the skill here.** This skill stops at a ranked candidate list; authoring is `superpowers:writing-skills`.

## Scripts

- `scripts/git-signals.sh` — deterministic git-history analysis (prefixes, keywords, hot files, co-change pairs, busy dirs). `--repo`, `--days`, `--since`, `--top`. Run `--help` for details.
- `scripts/scan-workflows.sh` — inventories Makefiles, package.json scripts, task runners, CI, `scripts/`, runbook docs, and existing skills. `--repo`. Run `--help` for details.
- `scripts/session-signals.py` — deterministic session-transcript analysis (funnel, request clusters, keywords, tool-sequence n-grams, hot files, co-edited pairs, skills used, friction). `--repo`, `--days`, `--since`, `--top`, `--scope`, `--transcripts-dir`, `--no-examples`. Run `--help` for details.

All three default to the current directory and emit sorted output with no wall-clock timestamps, so reruns over the same window and unchanged inputs are byte-identical.

**If a script can't run here** (missing `bash`, no Python, no transcript directory, or a different OS): don't abandon the task — run the sources that do work, say which one you skipped and why, and reproduce what you can with the tools this environment has.
