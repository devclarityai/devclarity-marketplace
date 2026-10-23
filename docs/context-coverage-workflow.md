# Context coverage workflow

`.github/workflows/context-coverage.yml` runs the deterministic half of the `context-coverage` skill (`plugins/training/skills/context-coverage`) in GitHub Actions: `collect.py --org` scans an org through the `gh` CLI without cloning, `render.py` builds the self-contained HTML report, and both files are uploaded as one artifact named `context-coverage`. No LLM is involved, so the "things to check" prose summary the skill gives in chat is not produced; the report's own findings list is.

## Running it

Actions tab, "Context coverage", "Run workflow". Inputs:

| Input | Meaning |
|---|---|
| `org` | Org or user to scan. Blank means the owner of the repo running the workflow. |
| `repos` | Comma-separated repo names. When set, only these are scanned and the activity window is ignored. Keep the list fixed if you want week-over-week comparisons. |
| `active_days` | Activity window when `repos` is blank (default 90, `0` = every repo). |
| `compare_to` | Run ID of an earlier run of this workflow (the number in its URL). Its `coverage-data.json` is downloaded and the report gains a "Since <date>" section. |

The run summary shows repo counts and a per-repo table; the full report is `context-coverage-report.html` inside the artifact. Artifacts are kept 90 days, so `compare_to` can reach back that far.

For a nightly run, uncomment the `schedule:` block. Scheduled runs take no inputs, so they scan the repo owner's org with the 90-day window.

## Token

The workflow reads `GH_TOKEN` from the `CONTEXT_COVERAGE_TOKEN` repository secret and falls back to `github.token`. The fallback can only see public repos outside the repo running the workflow, so private repos need the secret.

The scanner only reads: `gh repo list`, the git trees, commits and contents APIs. Grant no write access.

- **Fine-grained PAT** (simplest): resource owner = the target org, repository access = the repos to scan (or all), repository permissions **Contents: Read-only** and **Metadata: Read-only**. The org may need to approve fine-grained tokens first.
- **GitHub App** (better for a long-lived org setup): install it on the target org with **Contents: Read** and **Metadata: Read**, then mint a token in the job with `actions/create-github-app-token` (pass `owner:` the target org) and use that step's output as `GH_TOKEN` instead of the secret.
- A classic PAT works too but needs the broad `repo` scope (plus `read:org`), so prefer one of the above.

## Adapting it in a client's org

1. Copy `plugins/training/skills/context-coverage/scripts/` (`collect.py`, `render.py`) into the client repo, along with `.github/scripts/context_coverage_summary.py` and this workflow.
2. Point `SKILL_DIR` in the workflow at wherever the scripts landed.
3. Create the token as above, scoped to the client's org, and save it as the `CONTEXT_COVERAGE_TOKEN` secret.
4. Optionally set a default `repos` list in the workflow so every run covers the same set, and enable the nightly schedule.

The scripts are Python standard library only and need nothing installed beyond the `gh` CLI, which GitHub-hosted runners already have. A self-hosted runner needs `gh` and Python 3 on PATH.

## Limits

Org mode estimates LOC from blob bytes (flagged `*` in the report) and does not support `--scope` monorepo splitting, which needs a clone. For exact numbers add `--clone` to the collect step; that needs the same token and is slower, so pair it with `repos`.
