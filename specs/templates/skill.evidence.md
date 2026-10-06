---
name: skill
version: 1
description: Evidence for a skill spec - one row per criterion, and the release steps every skill change needs
---
## Criteria

| Criterion | Result | Proof | Why it proves the Then clause | Re-run |
|---|---|---|---|---|
| <each criterion> | <one of: pass, fail, not verified> | <test, command or sample run transcript> | <what the proof shows, and why> | `<command or prompt>` |

## Release

| Step | Done | Detail |
|---|---|---|
| plugin.json version bumped | <one of: yes, n/a> | <old to new version, or why not> |
| Root README updated | <one of: yes, n/a> | <the row added or changed, or why not> |
| Plugin README updated | <one of: yes, n/a> | <the row added or changed, or why not> |
| skill-lint.sh run | <one of: yes, n/a> | <findings and what was done about them> |

## Outside the spec's scope

<!-- Every changed file no criterion needs, or "None". -->

- <file>: <why it changed>
