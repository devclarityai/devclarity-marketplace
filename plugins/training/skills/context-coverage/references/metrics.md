# Metrics & JSON reference

`collect.py` emits one JSON document. **No composite scores**: every field is a raw count, a real ratio, a date-derived number, or a simple boolean.

## Top-level keys

| Key | What |
|-----|------|
| `generated_at` | UTC timestamp string |
| `source` | `{mode:"local", path}`, `{mode:"org", org}`, or `{mode:"repo", path, repo, scopes[]}` (monorepo) |
| `model` | the `MODEL` dict (thresholds), echoed for transparency |
| `selection` | the `--repos` list, if a hand-selected run (else `[]`) |
| `overrides` | `{include, exclude, opt_in_only}` applied |
| `repos` | array of per-repo objects (below) |
| `previous` | added by `render.py --compare`, not by the collector: `{generated_at, repos: {name: {total_context_lines, loc_per_context_line, commits_since_context, freshness, has_context}}}` from the earlier run |

## Per-repo fields

### Size / activity (directly measured)
| Field | Meaning |
|-------|---------|
| `name`, `mode` | repo name, and `local` or `org`. In monorepo mode `name` is `<repo>/<scope>` |
| `scope`, `repo` | monorepo mode only: the subpath analyzed, and the repo it belongs to |
| `loc` | lines of code (code files only) |
| `loc_is_estimate` | true in org mode (blob-bytes ÷ `BYTES_PER_LINE`) |
| `code_file_count` | code files counted |
| `commits_recent` | commits in the last `active_window_days` (90) |
| `last_commit_days` | days since last commit |
| `is_active` | committed within `MODEL["active_days"]` |
| `in_scope` | `is_active` and not throwaway (or forced by `--repos`/overrides) |

### Context inventory

Context kinds (`LINE_KINDS` in `collect.py`): `claude` (CLAUDE.md), `agents` (AGENTS.md), `gemini` (GEMINI.md), `copilot` (`.github/copilot-instructions.md`), `instructions` (Copilot `*.instructions.md`), `rules` (files in a `rules/` dir), `cursorrules`, `windsurfrules`. Every file of these kinds is line-counted and becomes an anchor.

| Field | Meaning |
|-------|---------|
| `has_claude_md` / `claude_md_lines` | root CLAUDE.md (or `.claude/CLAUDE.md`) presence + line count |
| `has_agents_md` | root AGENTS.md present |
| `nested_claude_count` | CLAUDE.md files below the root |
| `nested_context_count` | context files governing a subfolder rather than the root: nested CLAUDE.md/AGENTS.md, a subfolder's `.github/copilot-instructions.md`, a path-scoped `*.instructions.md` |
| `has_rules` | a `rules/` directory with rule files exists |
| `extra_context` | fixed-path kinds present (`copilot`, `cursorrules`, `windsurfrules`) |
| `has_context` | any context file at all |
| `copilot_outside_default` | Copilot files (`copilot`, `instructions`) outside `.github/copilot-instructions.md` and `.github/instructions/**` at the repo root, which Copilot cloud agent and Copilot code review do not read. In monorepo mode, every file the area owns |
| `has_nested_or_rules` | some context governs a subfolder, or there are rule files, i.e. context is *layered* |
| `context_file_count` | number of line-counted context files |
| `context_lines_by_kind` | `{kind: lines}` for each kind present. Sums to `total_context_lines` |
| `total_context_lines` | total lines across all context files |
| `loc_per_context_line` | `loc ÷ total_context_lines`, a plain ratio, `null` if no context |
| `skills_count` | `SKILL.md` files (vendored dirs excluded) |
| `context_anchors` | `[{dir, lines, kind, path, inherited?}]`: every context file and the folder it governs (`dir`). Drives folder governance and the tree |
| `inherited_context_lines` | monorepo mode: lines of context living *outside* the scope that still govern it (already included in `total_context_lines`) |
| `inherited_skills_count` | monorepo mode: skills defined above the scope (already included in `skills_count`) |
| `own_context_lines`, `own_skills_count`, `own_rules` | what the unit itself holds, with inherited context subtracted. Equal to the totals for an unscoped run |
| `own_area_context` | the unit holds context for one of its subfolders, or its own rules |
| `has_front_door` | a CLAUDE.md, AGENTS.md, GEMINI.md or `.github/copilot-instructions.md` governs the unit's root, whether its own or inherited |
| `owns_no_context` | governed only from outside: it has anchors, but none of its own |

### What an anchor governs (`dir`)
- `CLAUDE.md` / `AGENTS.md` / `GEMINI.md`: its own folder. `.claude/CLAUDE.md` governs the folder holding `.claude/`.
- `.github/copilot-instructions.md`: the folder holding that `.github/` (the root, or a subfolder with its own `.github/`).
- `*.instructions.md`: the folder its `applyTo:` globs point at, i.e. the literal path before the first wildcard (`packages/web/**/*.tsx` → `packages/web`, `**/*.ts` → root). Several globs → the deepest folder they share. No `applyTo` → the folder holding its `.github/`, or else its own folder.
- Rule files: the root. Grouped into one anchor per rules dir. (In monorepo mode, `context_governing_dir()` decides whether an ancestor `rules/` dir governs a scope: the folder holding the `rules/` dir, stepping over a tool surface such as `.cursor/rules/`.)
- `.cursorrules`, `.windsurfrules`: the root.

### Freshness (measured from git history in every mode)
| Field | Meaning |
|-------|---------|
| `context_last_updated_days` | days since the newest context file (any kind above) was last edited. Skills never move it, in any mode |
| `commits_since_context` | commits to the default branch since that edit. Under a scope, only commits touching that subtree count, so another team's churn never ages your context |
| `freshness` | `fresh` / `stale` / `none` / `unknown`. `stale` = at least `stale_commits_since` commits since the edit, or the edit is older than `stale_max_age_days` while the repo had commits in the active window |

### Per-folder structure
| Field | Meaning |
|-------|---------|
| `dir_tree` | pruned `{name, loc, children[]}` tree, LOC per folder, for the drill-down |

## The `MODEL` thresholds (the only knobs)

- `active_days` (90): the in-scope commit cutoff.
- `stale_commits_since` (25), `stale_max_age_days` (180): freshness.
- `problem`: folder-governance thresholds `dense_loc`, `loc_per_ctxline_warn`, `loc_per_ctxline_bad`, `oversized_claude_lines` (applies to any single context file).
- `throwaway.name_markers` / `stale_markers`: repo-name markers that auto-drop a repo from scope.

## How the report uses these

- **Things to check** (findings) fire on transparent rules: `freshness == stale` by either rule, `loc_per_context_line > loc_per_ctxline_bad` on a large repo (thin), any context file over `oversized_claude_lines`, a large repo with big folders and no `own_area_context`, three or more skills with no `has_front_door`, any `copilot_outside_default` files, and (monorepo) a large area that owns no context.
- **Findings are own-vs-inherited aware.** "Skills with no root context file" counts `own_skills_count` and accepts an inherited root file. "No folder-level context" keys off `own_area_context`, so inherited context does not suppress it. "Long context file" skips inherited anchors per area and instead reports an oversized shared file once, against the repo.
- **Sources column**: the kinds in `context_lines_by_kind`, with lines per kind on hover.
- **Folder governance** (per-repo tree): each folder's nearest governing `dir`. When several anchors govern that same folder (say a root CLAUDE.md, AGENTS.md and copilot file), their lines are summed. A folder's `loc ÷ those lines` colors it.
- **Monorepo scoping** (`--repo` + `--scope`): each scope is measured as its own unit. LOC, folder tree, git activity and freshness are all restricted to that subtree by a git pathspec. Context outside the scope that governs it is added as an anchor with `inherited: true`: a file governing a folder above the scope anchors at the scope root, and an instructions file whose `applyTo` points inside the scope anchors at that folder. It is counted in `total_context_lines` and shown separately in the report. `context_governing_dir()` decides what an artifact governs. A file inside the scope is the area's own and is never inherited. Scoped and unscoped runs measure each context file the same way (same line count, same governed folder). A scope's total also includes the inherited files, so scope totals don't add up to the repo total.
- **`--compare`**: `render.py` matches repos by `name` against `previous` and shows changes in total context lines and freshness.
- Vendored dirs (`node_modules`, `.venv`, `site-packages`, `dist` and others) are pruned everywhere, so context that ships inside a dependency never counts.

## Extending

Add a context kind by teaching `context_kind()` to recognize it, adding it to `LINE_KINDS`, and saying what it governs in `context_governing_dir()`. It is then line-counted, anchored, and freshness-tracked in every mode. Add a signal by measuring it in `scan_local_repo` / `scan_org_repo` (or the shared inventory pass), threading it through `classify()`, and consuming it in `render.py` (a finding rule, a stat, a table column). Thresholds go in `MODEL`.
