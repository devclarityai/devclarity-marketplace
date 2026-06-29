---
name: skill-improver
description: Use when reviewing, grading, critiquing, or improving an existing Claude Code skill or SKILL.md — checks name/scope, invocation description, structure, leanness, and surfaces concrete opportunities to add references, scripts, and determinism.
---

# Skill Improver

## Overview

Make an existing skill better. The goal is **helpful improvement, not a grade** — produce concrete, prioritized changes the author can apply, not a score. You review five dimensions, lean on the bundled linter for mechanical facts, and apply judgment to the rest.

**Core principle:** Every observation comes with a suggested fix.

## Inputs

- **Required:** path to a skill directory (with `SKILL.md`) or to a `SKILL.md` file.
- **Optional:** the skill's intended purpose, if stated — used to judge whether name and scope match intent.

## Steps

1. **Gather mechanical facts deterministically:**
   ```bash
   bash "${CLAUDE_SKILL_DIR}/scripts/skill-lint.sh" <skill-dir-or-SKILL.md>
   ```
   Reports frontmatter validity, name format, description shape, SKILL.md size, preferred sections, and referenced vs orphaned files. Treat `[FLAG]`s as leads, not verdicts.
2. **Read the SKILL.md and bundled files yourself** — the linter can't judge clarity, scope, or correctness.
3. **Review the five dimensions** (Guidelines), turning each finding into a concrete fix.
4. **Prioritize** high -> low impact. Lead with anything that breaks discovery (weak description) or correctness.
5. **Write the report** (Output). Offer to apply changes; if asked, hand authoring to `superpowers:writing-skills`.

## Guidelines

| Dimension | What good looks like |
| :-------- | :------------------- |
| **Name & scope** | Verb-first, active, single clear purpose. Flag vague or multi-purpose skills (suggest a split). |
| **Description** | Says **when to invoke** (triggers/symptoms/situations), not just what it does — `"Use when the user asks about slow queries or indexes"`, not `"Analyze and optimize queries"`. Third person; lead with "Use when". A summary of the steps makes agents skip the body — flag it. |
| **Structure** | Prefer **overview, inputs, steps, guidelines, output format**. Note missing sections; suggest where content should move. |
| **Lean SKILL.md** | Body holds workflow + judgment; heavy detail (APIs, long tables, big examples) belongs in `references/`. Flag bloat and name what to extract. |
| **References / scripts / assets** | Mechanical actions -> a deterministic **script**. Reusable context -> a **reference**. Templates -> **assets**. Flag orphaned files and non-deterministic scripts. |

Look explicitly for the two highest-value opportunities: **extraction** (inline content that belongs in a `references/` file, leaning out the always-loaded body) and **determinism** (prose steps an agent does inconsistently that a small script would make reproducible).

## Output format

```
## Skill review: <name>

Strengths: <1-2 lines>

### Suggested improvements (highest impact first)
1. [<dimension>] <observation> -> <concrete fix>
2. ...

### Extraction & determinism opportunities
- <inline content -> references/file.md>, <prose step -> scripts/x.sh>

Overall: <1-2 sentences, specific and encouraging. No score.>
```

## Common mistakes

- **Grading instead of helping** — no scores; every point needs an actionable fix.
- **Parroting the linter** — its flags are inputs; add the judgment it can't.
- **Extraction with nowhere to go** — name the target file and what moves into it.

## Scripts

- `scripts/skill-lint.sh` — deterministic mechanical checks (frontmatter, name, description, size, sections, orphaned/non-deterministic files). Read-only; pass a skill dir or `SKILL.md` path.
