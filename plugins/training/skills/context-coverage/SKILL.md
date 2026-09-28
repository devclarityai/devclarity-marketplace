---
name: context-coverage
description: Audit how agent context (CLAUDE.md, AGENTS.md, GitHub Copilot instructions, Cursor/Windsurf rules, rules directories, skills) lines up with the code across a set of repositories and generate a self-contained HTML report. The report leads with a short list of specific "things to check" (context behind the code, thin coverage for the codebase, oversized files, no per-area context), then per-repo raw metrics and a folder tree comparing folder LOC to context coverage, and can show what changed since an earlier run. Use when the user wants to audit context coverage across repos, "which repos are missing CLAUDE.md", "which repos have no Copilot instructions", "where is our agent context thin or stale", "context coverage across my org / projects folder", "track context coverage week over week", or "/context-coverage". Works on a local folder of clones, a whole GitHub org via the gh CLI, or a single monorepo scoped to just the areas one team owns.
---

# context-coverage: audit agent-context coverage across repos

Shows where agent context lines up with the code across a set of repos, and where it is missing, thin, stale, or oversized.

Agent context means any of: `CLAUDE.md` (including `.claude/CLAUDE.md`), `AGENTS.md`, `GEMINI.md`, `.github/copilot-instructions.md`, Copilot `*.instructions.md` files, `.cursorrules`, `.windsurfrules`, files in a `rules/` directory (including `.cursor/rules/` and `.claude/rules/`), and skills (`SKILL.md`).

The report uses only directly measured numbers (LOC, commit dates, context line counts, LOC per context line, commits since context was last edited). It has four parts:
- **Things to check**: a short ranked list of specific, number-backed observations, each framed as worth a look rather than a verdict. Context that lags the code, thin coverage, an oversized context file, a large repo with no per-area context, skills with no root file to point at them, Copilot files in places Copilot may not read.
- **The numbers**: one table of everything measured. The Sources column names every kind of context file a repo has, and hovering it gives the lines per kind, so every context line is accounted for.
- **Per-repo detail**: for each repo, the raw metric strip, where its context files live, and a **folder tree** where every directory is sized by its LOC and colored by whether a context file governs it and how thinly.
- **Since the last run** (with `--compare`): which repos gained or lost context lines, gained context, or changed freshness.

**Only active repos are analyzed by default**: a commit within the last 90 days (`--active-days`, `0` = all), matching the AI-SDLC maturity model's "active repos" denominator. Use **`--repos "a,b,c"`** to analyze exactly the repos you name. The skill folder is self-contained and portable.

## When to use

Trigger on: "audit context coverage", "which repos are missing CLAUDE.md", "which repos have Copilot instructions", "how good is our context across the org", "where is our agent context thin/stale/missing", "track context coverage over time", "/context-coverage". Also good as a periodic org health check.

## Three ways to run

All three produce the same JSON shape, so the same renderer works on each. The script paths below are relative to this skill's own directory. Run them from that directory, not from the repo being scanned, and give `--dir`, `--repo` and `--out` absolute paths.

### Mode A: a local folder of clones (full fidelity, recommended)
Real LOC, full commit history, nested context, context freshness against code churn. Needs `git` on PATH.

```bash
python3 scripts/collect.py --dir <folder-of-repos> --out coverage-data.json
python3 scripts/render.py coverage-data.json --out coverage-report.html
```
`--dir` scans every repo that is an **immediate subdirectory** of the folder.

### Mode B: a whole GitHub org, no clone (fast, needs `gh`)
Enumerates the org with `gh repo list`, then inspects each repo through the GitHub trees/commits/contents API without cloning. Requires an authenticated `gh` (`gh auth status`, scope `repo` + `read:org`). LOC is **estimated** from blob bytes and flagged with `*` in the report.

```bash
python3 scripts/collect.py --org <org-or-user> --out coverage-data.json
python3 scripts/render.py coverage-data.json --out coverage-report.html
```

### Mode C: one monorepo, scoped to the areas a team owns
In a monorepo, auditing the whole tree buries a team in code they don't touch. `--repo` takes a single repo and `--scope` splits it into the subpaths you care about. Each one is analyzed as its own unit and everything else is ignored.

```bash
python3 scripts/collect.py --repo <path-to-repo> --scope "apps/web,libs/ui" --out coverage-data.json
python3 scripts/render.py coverage-data.json --out coverage-report.html
```
- Each scope becomes one row named `<repo>/<scope>` (e.g. `platform/apps/web`).
- **Every number is restricted to that subtree**: LOC, code files, the folder tree, and git activity and freshness, filtered by git pathspec. Another team's churn never makes your area look stale.
- **Context from outside your scope still counts, and is labeled.** A root `CLAUDE.md` governs `apps/web`, so it is included as *inherited* context: counted in the coverage numbers, but shown on its own line so an area is never credited with owning it. Every kind the unscoped scan counts is inherited, not just `CLAUDE.md`. That includes a `.github/instructions/*.instructions.md` at the repo root whose `applyTo` points into the scope, which is the usual Copilot layout in a monorepo. Scoped and unscoped runs measure each context file the same way (same line count, same governed folder). A scope's total also includes the inherited files, so scope totals don't add up to the repo total.
- **A `--scope` that matches nothing stops the run with an error.** Scopes are validated against the directories that actually hold tracked files, so `Apps/Web` resolves to `apps/web` rather than quietly measuring nothing on a case-insensitive filesystem. `.`, `..`, absolute paths and glob/pathspec characters are rejected.
- `--repo` with no `--scope` analyzes the whole repo as one unit (the same numbers as running `--dir` on its parent, filtered to that repo).
- Named scopes are always analyzed. The 90-day activity cutoff and the throwaway-name filter don't apply, so a scope like `packages/test-utils` is not dropped.

**Ask which areas the user owns** rather than guessing. Good sources: the monorepo's workspace config (`pnpm-workspace.yaml`, `nx.json`, `go.work`, `Cargo.toml` members), a `CODEOWNERS` file, or the top-level `apps/` and `packages/` directories.

> The scripts are **pure standard library**, so `python3 scripts/collect.py …` works with no install. Where `python3` is unavailable or points at a stub (e.g. the Windows Store alias), use `uv run python` instead.

## How to run it (the recipe)

1. **Pick the target.** Ask the user (or infer): a local folder of clones, a GitHub org/user login, or a single monorepo plus the subpaths one team owns. Local mode is richer. Org mode needs no clones. If the target is one big repo shared by several teams, use Mode C and scope it.
2. **Collect.** Run `collect.py` with `--dir`, `--org` or `--repo`. Progress prints to stderr, one line per repo. Org mode scans repos **in parallel** (`--jobs`, default 8), so a ~37-repo org takes about 20 seconds. `--jobs 1` forces sequential. Local mode takes seconds.
3. **Render.** Run `render.py` on the JSON to get the HTML.
4. **Show it.** Open the HTML, or publish it for a shareable link (it is self-contained, with inline CSS/JS and no external assets). Then give the user the top 2-3 **things to check** in chat, with their numbers.

Do **not** paste the raw JSON at the user. The HTML is the deliverable. Summarize the takeaways in prose.

## Tracking coverage over time

Keep each run's JSON and pass the previous one to the renderer:

```bash
python3 scripts/collect.py --org <org> --repos "a,b,c" --out coverage-$(date +%F).json
python3 scripts/render.py coverage-$(date +%F).json --compare coverage-<last-run>.json --out coverage-report.html
```

The report then opens with a **Since <date>** summary (repos that gained or lost context lines, gained context, became stale or fresh), shows the change next to each repo's total context lines, and shows a changed status next to the old one (for example `stale`, then `was fresh`). Repos are matched by name. A fixed `--repos` list keeps week-to-week runs comparable. Both scripts are non-interactive, so a scheduled job (cron, CI) can run them unattended.

## What it measures (per repo)

**Size/activity:** LOC (code files only, `.gitignore`-respecting via `git ls-files`), file count, commits in the last 90 days, days since last commit, age, contributors.

**Context inventory:** every context file listed above, with per-file line counts, wherever it sits: root and **nested** `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`, `.github/copilot-instructions.md` (at the root, or under a subfolder's own `.github/`), `*.instructions.md` files anywhere in the repo, `.cursorrules`, `.windsurfrules`, `rules/` directories, and skills (real ones only). Lines are reported per kind (`context_lines_by_kind`).

**What each file governs:** a `CLAUDE.md` / `AGENTS.md` / `GEMINI.md` governs its own folder (`.claude/CLAUDE.md` governs the folder holding `.claude/`). A `.github/copilot-instructions.md` governs the folder holding that `.github/`. A Copilot `*.instructions.md` governs the folder its `applyTo:` frontmatter globs point at (`applyTo: "packages/web/**/*.tsx"` governs `packages/web`, `applyTo: "**/*.ts"` governs the whole repo). With no `applyTo` it governs the folder holding its `.github/`, or its own folder. Rules directories, `.cursorrules` and `.windsurfrules` govern the root.

**Where Copilot reads from:** Copilot cloud agent and Copilot code review read `.github/copilot-instructions.md` and `.github/instructions/**` at the repository root only. VS Code reads a subfolder's files only when that folder is opened as a workspace, and Copilot CLI reads more locations. Files elsewhere are still counted, since they are written context, and each repo with any gets a "Copilot may not load these" finding that lists them. The `applyTo` folder is approximate: VS Code matches a pattern like `src/**` against any `src/` folder, not only the root one.

**Per-folder structure:** a pruned directory tree with LOC per folder, plus every context file's location and size (the "anchors"), so the report can compute which folders a context file governs and how thinly (LOC per context line). This powers the drill-down and the folder-level findings.

**Freshness:** when any context file was last edited (git) and how many commits landed since.

**Vendored directories are pruned everywhere** (`node_modules`, `.venv`, `site-packages`, `dist`, `build`, `vendor`, `target` and others), so a context file or skill that ships inside a dependency never inflates the numbers.

## Which repos get analyzed

Three ways to choose the set, all composable with exclusions:

1. **Self-select**: analyze exactly the repos you name (activity cutoff ignored, works in `--dir` too):
   ```bash
   python3 scripts/collect.py --org ACME --repos "platform-core,billing,web"
   ```
2. **Commit cutoff (default)**: every repo in the org with a commit in the last N days:
   ```bash
   python3 scripts/collect.py --org ACME                  # last 90 days (default)
   python3 scripts/collect.py --org ACME --active-days 30
   python3 scripts/collect.py --org ACME --active-days 0  # no cutoff, all repos
   ```
   Obvious non-projects (archived, forks, empty repos under 50 LOC, and scratch/demo/test-named repos) are dropped automatically. Adjust with exclusions and inclusions.
3. **Exclusions and inclusions**: layer onto either mode, persistent and portable:
   ```bash
   python3 scripts/collect.py --org ACME --exclude "*-demo,legacy-*,*sandbox*"
   python3 scripts/collect.py --org ACME --include "keep-this-inactive-repo"  # force in, ignores cutoff
   python3 scripts/collect.py --org ACME --overrides overrides.json           # reuse a saved file
   ```
   `overrides.json` = `{"include": ["core"], "exclude": ["*-demo","legacy-*"]}`. Name globs, case-insensitive. **Exclude wins over include.**

**In the report:** a **"Which repos to analyze"** panel at the top lets the reader change the scope live: commit-cutoff presets (30d/90d/6mo/1yr/any), per-repo checkboxes, and **Export selection** (writes the `--repos` command and an overrides file for the next run). Choices persist in the browser.

**Exact LOC (`--clone`):** org mode estimates LOC from blob bytes (flagged `*`). Add `--clone` to clone each selected repo and measure LOC, nested context and freshness exactly (it reuses the local scanner). It is slower, so pair it with `--repos` or a tight cutoff when the numbers need to be right.

## What it flags

Everything shown is a directly measured count or a plain ratio. The only thresholds live in `collect.py`'s `MODEL`:

- **LOC per context line** = total code LOC ÷ total context lines, across every context file kind.
- **Stale** = 25 or more commits to the default branch since the newest context file was last edited, **or** no context edit in 180 days while the repo had commits in the last 90 days. Both come from git history, in every mode.
- **Folder governance** (per-repo tree) = a folder's LOC ÷ the lines of the context files at its nearest governing folder. A folder over 450 LOC per line (or with none) is flagged.
- **Oversized file** = any single context file over 300 lines.

The report leads with **Things to check** (worst first, each framed as worth a look), then per-repo raw metrics and a folder tree, then a grouped table of every number. Tune the `MODEL` thresholds and re-run.

## Files

| Path | Role |
|------|------|
| `scripts/collect.py` | Scanner → `coverage-data.json`. Stdlib only. `--dir` (local), `--org` (gh) or `--repo` (monorepo). |
| `scripts/render.py` | `coverage-data.json` → self-contained HTML report. Stdlib only. `--compare` for changes since an earlier run. |
| `references/metrics.md` | Full metric and JSON-field reference, and how to extend the model. |

## Notes and limits

- **Monorepo scoping is local-mode only.** `--scope` needs real git history, so pair it with `--repo` on a clone (org mode cannot pathspec-filter).
- **Org mode LOC is an estimate** (blob bytes ÷ ~38), flagged with `*`. For exact LOC, clone and use `--dir`, or add `--clone`.
- Org mode skips total-commit and contributor counts (too many API calls). It uses `pushedAt` for recency and a 90-day commit window.
- `applyTo` is read from each instructions file's frontmatter. When several globs are listed, the file is credited to the deepest folder they share. Org mode reads file contents for the first 60 context files per repo, so an instructions file past that cap is credited to its location instead.
- A repo the scanner can't read (no default branch, empty, API error) still appears, with an `errors` note in the JSON.
- Everything is local and offline except the `gh` calls in org mode. No data leaves the machine.
