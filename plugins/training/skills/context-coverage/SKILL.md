---
name: context-coverage
description: Audit how agent context (CLAUDE.md / AGENTS.md / rules / skills) lines up with the code across a set of repositories and generate a self-contained HTML report — a short list of specific "things to check" (context behind the code, thin coverage for the codebase, oversized files, no per-area context), plus per-repo raw metrics and a folder tree comparing folder LOC to context coverage. Use when the user wants to audit context coverage across repos, "which repos are missing CLAUDE.md", "where is our agent context thin or stale", "context coverage across my org / projects folder", or "/context-coverage". Works on a local folder of clones, a whole GitHub org via the gh CLI, or a single monorepo scoped to just the areas one team owns.
---

# context-coverage — audit agent-context coverage across repos

Answers one question: **across the repos being worked on, where does agent context (CLAUDE.md, AGENTS.md, /rules/, skills) line up with the code — and where is it missing, thin, stale, or oversized?**

**No invented composite scores.** The report shows only directly-measured numbers — LOC, commit dates, context line counts, LOC-per-context-line, and commits-since-context (from real git history in both modes) — and turns them into signal you can act on:
- **Things to check** — a short (≈3–10) ranked list of specific, number-backed observations, each framed as *worth a look, not a verdict*: context that lags the code (N commits since it was last edited), thin coverage (LOC per context line), an oversized (>300-line) CLAUDE.md, a large repo with no per-area context, skills with no root file.
- **Per-repo detail** — for each repo: the raw metric strip, where its context files live, and a **folder tree** — every directory sized by its LOC, colored by whether a context file governs it and how thinly.
- **The numbers** — a plain table of everything measured, side by side.

**Only active repos are analyzed** — a commit within the last 90 days (`--active-days`, `0` = all), matching the AI-SDLC maturity model's "active repos" denominator. Use **`--repos "a,b,c"`** to analyze only specific repos (fast iteration; forces them in scope). The whole skill folder is self-contained and portable — runs on an org in a few minutes.

## When to use

Trigger on: "audit context coverage", "which repos are missing CLAUDE.md", "how good is our context across the org", "where is our agent context thin/stale/missing", "/context-coverage". Also good as a periodic org health check.

## Two ways to run

Both produce the same JSON shape, so the same renderer works on either.

### Mode A — a local folder of clones (full fidelity, recommended)
Real LOC, full commit history, nested context, context freshness vs code churn. Needs `git` on PATH.

```bash
uv run python scripts/collect.py --dir <folder-of-repos> --out coverage-data.json
uv run python scripts/render.py coverage-data.json --out coverage-report.html
```
`--dir` scans every git repo that is an **immediate subdirectory** of the folder.

### Mode B — a whole GitHub org, no clone (fast, needs `gh`)
Enumerates the org with `gh repo list`, then inspects each repo through the GitHub trees/commits/contents API — no clone. Requires an authenticated `gh` (`gh auth status`; scope `repo` + `read:org`). LOC is **estimated** from blob bytes (flagged with `*` in the report).

```bash
uv run python scripts/collect.py --org <org-or-user> --out coverage-data.json
uv run python scripts/render.py coverage-data.json --out coverage-report.html
```

### Mode C — one monorepo, scoped to the areas a team owns
In a monorepo, auditing the whole tree buries a team in code they don't touch. `--repo`
takes a single repo and `--scope` splits it into the subpaths you care about — each one
analyzed as its own unit, everything else ignored.

```bash
uv run python scripts/collect.py --repo <path-to-repo> --scope "apps/web,libs/ui" --out coverage-data.json
uv run python scripts/render.py coverage-data.json --out coverage-report.html
```
- Each scope becomes one row named `<repo>/<scope>` (e.g. `platform/apps/web`).
- **Every number is restricted to that subtree** — LOC, code files, the folder tree, and
  (the one that matters most in a monorepo) **git activity and freshness**, filtered by git
  pathspec. Another team's churn can never make your area look stale.
- **Context above your scope still counts, and is labelled.** A root `CLAUDE.md` genuinely
  governs `apps/web`, so it is included as *inherited* context — counted in the coverage
  numbers, but shown on its own line so an area is never credited with owning it.
- `--repo` with no `--scope` analyzes the whole repo as one unit (identical numbers to
  running `--dir` on its parent, filtered to that repo).
- Named scopes are always analyzed — the 90-day activity cutoff and the throwaway-name
  filter don't apply, so a scope like `packages/test-utils` is not silently dropped.

**Ask which areas the user owns** rather than guessing. Good sources: the monorepo's
workspace config (`pnpm-workspace.yaml`, `nx.json`, `go.work`, `Cargo.toml` members),
a `CODEOWNERS` file, or just the top-level `apps/` and `packages/` directories.

> On this user's machine, always invoke Python as `uv run python` (bare `python` hits the Windows Store stub). The scripts are **pure standard library**, so on any other machine `python3 scripts/collect.py …` works with no install.

## How to run it (the recipe)

1. **Pick the target.** Ask the user (or infer): a local folder of clones, a GitHub org/user login, or a single monorepo plus the subpaths one team owns. Local mode is richer; org mode needs no clones. If the target is one big repo shared by several teams, use Mode C and scope it — do not dump the whole tree on one team.
2. **Collect.** Run `collect.py` with `--dir` or `--org`. Progress prints to stderr, one line per repo. Org mode scans repos **in parallel** (`--jobs`, default 8) — a ~37-repo org takes ~20s (the heaviest repo is the long pole); `--jobs 1` forces sequential. Local mode is seconds.
3. **Render.** Run `render.py` on the JSON to get the HTML.
4. **Show it.** Open the HTML, or publish it with the **Artifact tool** for a shareable link (self-contained and CSP-safe — inline CSS/JS, no external assets). Then give the user the top 2–3 **things to check** in chat, with their numbers.

Do **not** paste the raw JSON at the user. The HTML is the deliverable; summarize the takeaways in prose.

## What it measures (per repo)

**Size/activity:** LOC (code files only, `.gitignore`-respecting via `git ls-files`), file count, commits in the last 90 days, days since last commit, age, contributors.
**Context inventory:** root + **nested** `CLAUDE.md` / `AGENTS.md` (with per-file line counts), `.cursorrules` / `.github/copilot-instructions.md`, `/rules/` dirs, `.claude/skills` count (real ones only), commands, and tool "surfaces" (`.claude` / `.cursor` / `.gemini` / …).
**Per-folder structure:** a pruned directory tree with LOC per folder, plus every context file's location and size (the "anchors"), so the report can compute which folders a given CLAUDE.md actually governs and how thinly (LOC per context line) — this powers the drill-down and the folder-level problem areas.
**Freshness:** when context was last touched (git) and how many code commits landed since.

**Vendored directories are pruned everywhere** (`node_modules`, `.venv`, `site-packages`, `dist`, `build`, `vendor`, `target`, …), so a CLAUDE.md or skill that ships *inside a dependency* never inflates the numbers. This matters — without it, a repo with zero real skills can look context-rich because a dependency bundles one.

## Which repos get analyzed

Three ways to choose the set — all composable with exclusions:

1. **Self-select** — analyze exactly the repos you name (activity cutoff ignored; works in `--dir` too):
   ```bash
   uv run python scripts/collect.py --org ACME --repos "platform-core,billing,web"
   ```
2. **Commit cutoff (default)** — every repo in the org with a commit in the last N days:
   ```bash
   uv run python scripts/collect.py --org ACME                  # last 90 days (default)
   uv run python scripts/collect.py --org ACME --active-days 30
   uv run python scripts/collect.py --org ACME --active-days 0  # no cutoff, all repos
   ```
   Obvious non-projects (archived, forks, empty < 50 LOC, and scratch/demo/test-named repos) are dropped automatically; adjust with exclusions/inclusions.
3. **Exclusions & inclusions** — layer onto either mode, persistent and portable:
   ```bash
   uv run python scripts/collect.py --org ACME --exclude "*-demo,legacy-*,*sandbox*"
   uv run python scripts/collect.py --org ACME --include "keep-this-inactive-repo"  # force in, ignores cutoff
   uv run python scripts/collect.py --org ACME --overrides overrides.json           # reuse a saved file
   ```
   `overrides.json` = `{"include": ["core"], "exclude": ["*-demo","legacy-*"]}`. Name globs, case-insensitive; **exclude wins over include**.

**In the report:** a **"Which repos to analyze"** panel at the top lets the reader re-dial scope live — commit-cutoff presets (30d/90d/6mo/1yr/any), per-repo checkboxes, and **Export selection** (writes the `--repos` command + an overrides file for the next run). Choices persist in the browser.

**Exact LOC (`--clone`):** org mode estimates LOC from blob bytes (flagged `*`). Add `--clone` to clone each selected repo and measure LOC, nested context, and freshness *exactly* (reuses the local scanner). Slower, so pair it with `--repos` or a tight cutoff — for a focused set where the numbers need to be right.

## What it flags — direct signals, no composite scores

Everything shown is a directly-measured count or a plain ratio; there is **no invented 0–100 score**. The only thresholds live in `collect.py`'s `MODEL`:

- **LOC per context line** = total code LOC ÷ total CLAUDE.md/AGENTS.md lines. Shown **only when context is layered** (a nested CLAUDE.md or a `/rules/` dir) — with a single root file it's just LOC ÷ root length, so it's suppressed as noise.
- **Commits since context** = commits to the default branch since the newest context file was last edited (from git history, in **both** modes). ≥ 25 → **stale**.
- **Folder governance** (per-repo tree) = a folder's LOC ÷ the lines of its nearest governing context file; a folder over ~450 LOC/line (or with none) is flagged.
- **Oversized file** = any single CLAUDE.md / AGENTS.md over 300 lines.

The report leads with a **Things to check** list (≈3–10 findings, worst-first, framed as *worth a look, not a verdict*), then per-repo raw metrics and a folder tree, then a grouped table of every number. Tune the `MODEL` thresholds and re-run.

## Files

| Path | Role |
|------|------|
| `scripts/collect.py` | Scanner → `coverage-data.json`. Stdlib only. `--dir` (local) or `--org` (gh). |
| `scripts/render.py` | `coverage-data.json` → self-contained HTML report. Stdlib only. |
| `references/metrics.md` | Full metric + JSON-field reference, and how to extend the model. |

## Notes & limits

- **Monorepo scoping is local-mode only** — `--scope` needs real git history, so pair it with `--repo` on a clone (org mode cannot pathspec-filter).
- **Org mode LOC is an estimate** (blob bytes ÷ ~38), flagged with `*`. For exact LOC, clone and use `--dir`.
- Org mode skips total-commit and contributor counts (too many API calls); it uses `pushedAt` for recency and a 90-day commit window.
- A repo the scanner can't read (no default branch, empty, API error) still appears, with an `errors` note in the JSON.
- Everything is local/offline except the `gh` calls in org mode. No data leaves the machine.
