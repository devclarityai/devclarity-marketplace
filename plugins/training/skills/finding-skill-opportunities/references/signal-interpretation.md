# Signal interpretation

What each section of each script's output tends to mean. Read this during synthesis (Workflow step 4), not before running the scripts.

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

| Signal (from `session-signals.py`) | Likely skill opportunity |
| :--------------------------------- | :----------------------- |
| **Session funnel** (`no skill (pool)`) | The size of the opportunity. A large no-skill pool means real work is running uncovered; a small one means the leverage is in improving existing skills instead. |
| **Recurring request clusters** | The same ask, phrased differently, across sessions — the most direct skill candidate there is, because the trigger phrasing is handed to you |
| **Recurring task keywords** | Cross-check against the same section in the git output; a keyword high in both is corroborated |
| **Repeated tool sequences** | A procedure with a fixed shape. Generic edit-loops are filtered out, so what remains (MCP call chains, subagent fan-outs) is the automatable part |
| **Hot files / co-edited pairs** | Same reading as their git counterparts, but includes edits that were never committed |
| **Skills already used** | Do NOT propose these; a heavily-used skill with high friction is a *revision* candidate for `skill-improver` |
| **Friction count** | Volume only. High friction says guidance is missing; use the `pattern-audit` skill to find out which guidance |

