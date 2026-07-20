# Metrics & JSON reference

`collect.py` emits one JSON document. **No composite scores** — every field is a
raw count, a real ratio, a date-derived number, or a simple boolean.

## Top-level keys

| Key | What |
|-----|------|
| `generated_at` | UTC timestamp string |
| `source` | `{mode:"local", path}` or `{mode:"org", org}` |
| `model` | the `MODEL` dict (thresholds), echoed for transparency |
| `selection` | the `--repos` list, if a hand-selected run (else `[]`) |
| `overrides` | `{include, exclude, opt_in_only}` applied |
| `repos` | array of per-repo objects (below) |

## Per-repo fields

### Size / activity (directly measured)
| Field | Meaning |
|-------|---------|
| `name`, `mode` | repo name; `local` or `org` |
| `loc` | lines of code (code files only) |
| `loc_is_estimate` | true in org mode (blob-bytes ÷ `BYTES_PER_LINE`) |
| `code_file_count` | code files counted |
| `commits_recent` | commits in the last `active_window_days` (90) |
| `last_commit_days` | days since last commit |
| `is_active` | committed within `MODEL["active_days"]` |
| `in_scope` | `is_active` and not throwaway (or forced by `--repos`/overrides) |

### Context inventory
| Field | Meaning |
|-------|---------|
| `has_claude_md` / `claude_md_lines` | root CLAUDE.md presence + line count |
| `has_agents_md` | root AGENTS.md present (feeds `has_context`) |
| `nested_claude_count` | CLAUDE.md files below the root |
| `has_rules` | a `/rules/` directory with rule files exists |
| `has_context` | any CLAUDE.md / AGENTS.md / cursorrules / copilot / rules |
| `has_nested_or_rules` | nested CLAUDE.md or `/rules/` — i.e. context is *layered* |
| `total_context_lines` | total lines across all context files |
| `loc_per_context_line` | `loc ÷ total_context_lines` — a plain ratio; `null` if no context |
| `skills_count` | `SKILL.md` files (vendored dirs excluded) |
| `context_anchors` | `[{dir, lines, kind, path}]` — every governing context file; drives folder governance and the tree |

### Freshness (measured from git history in both modes)
| Field | Meaning |
|-------|---------|
| `context_last_updated_days` | days since the newest context file was last edited |
| `commits_since_context` | commits to the default branch since that edit |
| `freshness` | `fresh` / `stale` (≥ `stale_commits_since` commits since) / `none` / `unknown` |

### Per-folder structure
| Field | Meaning |
|-------|---------|
| `dir_tree` | pruned `{name, loc, children[]}` tree — LOC per folder, for the drill-down |

## The `MODEL` thresholds (only knobs)

- `active_days` (90) — the in-scope commit cutoff.
- `stale_commits_since` (25), `stale_max_age_days` (240) — freshness.
- `problem` — folder-governance thresholds: `dense_loc`, `loc_per_ctxline_warn`, `loc_per_ctxline_bad`, `oversized_claude_lines`.
- `throwaway.name_markers` / `stale_markers` — repo-name markers that auto-drop a repo from scope.

## How the report uses these

- **Things to check** (findings) fire on transparent rules: `commits_since_context ≥ 25` (stale), `loc_per_context_line > loc_per_ctxline_bad` on a large repo (thin), any context file `> oversized_claude_lines`, a large repo with big folders and no nested/rules context.
- **Folder governance** (per-repo tree): each folder's nearest ancestor `context_anchor`; a folder's `loc ÷ that anchor's lines` colors it. `loc_per_context_line`-style density is shown **only when `has_nested_or_rules`** — with a single root file the ratio is just `loc ÷ root length`, so it's suppressed as noise.
- Vendored dirs (`node_modules`, `.venv`, `site-packages`, `dist`, …) are pruned everywhere, so context that ships inside a dependency never counts.

## Extending

Add a signal by measuring it in `scan_local_repo` / `scan_org_repo` (or the shared inventory pass), threading it through `classify()`, and consuming it in `render.py` (a finding rule, a stat, a table column). Thresholds go in `MODEL`.
