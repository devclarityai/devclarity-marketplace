# Input Shapes

How to split each kind of file into items. Read the section for the file you are parsing.

## What counts as an item

One item is **one claim that could move, stay, or be deleted on its own.**

- A bullet stating a convention is one item.
- A heading with three bullets under it is three items, unless the bullets mean nothing apart.
- A paragraph making two unrelated claims is two items. Split it.
- Structure is not an item: a table of contents, a "how to read this file" preamble, headings, a router table. Leave it alone.

Too fine and nobody can review the table. Too coarse and a bad claim hides inside a good one. One subject and one rule is one item.

## CLAUDE.md (root or nested)

**Recognize it by:** the filename. Prose sections under topic headings, usually unsourced.

**Split:** one item per bullet, or per claim in a paragraph. A command block is one item per command only when commands could go to different places. Usually the whole block stays.

**Watch for:**

- **Generic advice** ("write clean code", "handle errors"). The generic-advice check deletes these. Usually the biggest source of deletions.
- **Lines a tool already enforces** (quote style, import order, formatting). Question 1, but confirm the repo's linter config really enforces it. Some lines are only partly checkable. Split those.
- **Work in progress** ("we're migrating to Vite", "skip the refund e2e test until PAY-511 lands"). Question 2: a ticket.
- **Setup and architecture description.** Usually belongs in CLAUDE.md. "No citation" does not mean "wrong".

## Rules (`.claude/rules/*.md`)

**Recognize it by:** the folder, and `paths` frontmatter.

**Split:** one item per bullet.

**Watch for:** a rule with no `paths` glob. It loads every session. Either add the glob or route its lines with the questions as if they lived in CLAUDE.md.

## SKILL.md

**Recognize it by:** YAML frontmatter with `name` and `description`.

**Split:** only the knowledge, never the machinery. Workflow steps, checklists and STOP markers are the skill itself. Split convention statements, "always/never" rules and domain facts.

**Watch for:** a rule every task in the repo needs, sitting inside one skill. That is a move up into CLAUDE.md, subject to the evidence gate.

## Docs and references (`docs/`, `references/`)

**Recognize it by:** a markdown file with no frontmatter.

**Split:** one item per bullet or claim.

**Watch for:** transient notes about one change, a migration in progress, or a temporary workaround. Question 2: a ticket. Also check that something points to the doc. A doc nothing points to never loads.

## Mined review feedback

**Recognize it by:** occurrence counts (`PRs x13`), PR links, tier headings, `[CI: ...]` tags.

**Split:** one item per numbered rule, keeping its count, PRs and any CI tag.

**Evidence:** the richest of any shape, and it feeds the evidence gate directly. Two or more independent PRs, or one PR worded as a standing convention, clears it. A `[CI: ...]` tag is a candidate for question 1, not a verdict.

## When the shape is unclear

Treat it as a doc and split per bullet. If a file mixes shapes, split each region by its own shape.
