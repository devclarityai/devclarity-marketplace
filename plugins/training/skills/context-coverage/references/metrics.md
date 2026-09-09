# Metrics & JSON reference

`collect.py` emits one JSON document. **No composite scores** — every field is a
raw count, a real ratio, a date-derived number, or a simple boolean.

## Top-level keys

| Key | What |
|-----|------|
| `generated_at` | UTC timestamp string |
| `source` | `{mode:"local", path}`, `{mode:"org", org}`, or `{mode:"repo", path, repo, scopes[]}` (monorepo) |
| `model` | the `MODEL` dict (thresholds), echoed for transparency |
| `selection` | the `--repos` list, if a hand-selected run (else `[]`) |
| `overrides` | `{include, exclude, opt_in_only}` applied |
| `repos` | array of per-repo objects (below) |

## Per-repo fields

### Size / activity (directly measured)
| Field | Meaning |
|-------|---------|
| `name`, `mode` | repo name; `local` or `org`. In monorepo mode `name` is `<repo>/<scope>` |
| `scope`, `repo` | monorepo mode only: the subpath analyzed, and the repo it belongs to |
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
| `context_anchors` | `[{dir, lines, kind, path, inherited?}]` — every governing context file; drives folder governance and the tree |
| `inherited_context_lines` | monorepo mode: lines of context living *above* the scope that still govern it (already included in `total_context_lines`) |
| `inherited_skills_count` | monorepo mode: skills defined above the scope (already included in `skills_count`) |
| `own_context_lines`, `own_skills_count`, `own_rules` | what the unit itself holds, with inherited context subtracted; equal to the totals for an unscoped run |
| `has_front_door` | a `CLAUDE.md`/`AGENTS.md` governs the unit, whether its own or inherited |
| `owns_no_context` | governed only from above: it has anchors, but none of its own |

### Freshness (measured from git history in both modes)
| Field | Meaning |
|-------|---------|
| `context_last_updated_days` | days since the newest context file was last edited |
| `commits_since_context` | commits to the default branch since that edit. Under a scope, only commits touching that subtree count — another team’s churn never ages your context |
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

- **Findings are own-vs-inherited aware.** "Skills without a front door" counts `own_skills_count` and accepts an inherited `CLAUDE.md` as the front door; "no per-area context" keys off `own_rules`, so inherited rules do not suppress it; "long context file" skips inherited anchors so one oversized root file is reported once, not once per area; and a scoped area that owns nothing gets its own finding. For an unscoped run every one of these reduces to the previous rule.
- **Things to check** (findings) fire on transparent rules: `commits_since_context ≥ 25` (stale), `loc_per_context_line > loc_per_ctxline_bad` on a large repo (thin), any context file `> oversized_claude_lines`, a large repo with big folders and no nested/rules context.
- **Folder governance** (per-repo tree): each folder's nearest ancestor `context_anchor`; a folder's `loc ÷ that anchor's lines` colors it. `loc_per_context_line`-style density is shown **only when `has_nested_or_rules`** — with a single root file the ratio is just `loc ÷ root length`, so it's suppressed as noise.
- **Monorepo scoping** (`--repo` + `--scope`): each scope is measured as its own unit — LOC, folder tree, git activity and freshness are all restricted to that subtree by a git pathspec. Context in an ancestor directory is not ignored (it does govern the area): it is added as an anchor at the scope root with `inherited: true`, counted in `total_context_lines`, and shown separately in the report so an area is never credited with owning it. `context_governing_dir()` decides what an artifact governs — a `CLAUDE.md`/`AGENTS.md` governs its own directory, a rule file governs the directory holding its `rules/` dir (stepping over a tool surface, so `.cursor/rules/` and `.claude/rules/` govern the root like a bare `rules/` does), a skill governs the directory holding its surface, and fixed-path files (`.cursorrules`, `.github/copilot-instructions.md`) govern the root. A file inside the scope is the area's own and is never inherited. Scoped and unscoped runs of the same repo therefore report the same total context.
- Vendored dirs (`node_modules`, `.venv`, `site-packages`, `dist`, …) are pruned everywhere, so context that ships inside a dependency never counts.

## Extending

Add a signal by measuring it in `scan_local_repo` / `scan_org_repo` (or the shared inventory pass), threading it through `classify()`, and consuming it in `render.py` (a finding rule, a stat, a table column). Thresholds go in `MODEL`.
