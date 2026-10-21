---
name: context-management
description: "Sorts the lines in your agent context (CLAUDE.md, .claude/rules/, docs/, skill files) with five questions and moves each one to where it belongs: lint or CI, a ticket, CLAUDE.md, a path-scoped rule, a doc, or nowhere. Use when auditing or trimming a CLAUDE.md, when context files have grown long and noisy, when deciding where a new convention should live, or when promoting recurring review feedback into standing context. Trigger terms: context cleanup, audit CLAUDE.md, prune context, where does this line go, what belongs in CLAUDE.md, context is too long, /context-management."
---

# Context Management

Sorts context lines with five questions and applies the moves you approve. One run audits the files you name. Nothing changes without your approval.

## The five questions

Ask them in order for each line. **The first yes wins.**

| # | Question | Yes means |
|---|---|---|
| 1 | Can a linter or CI check it? | **Lint backlog.** Out of context entirely. |
| 2 | Is it only true for this change? | **Ticket.** It stops being true when the ticket closes. |
| 3 | Does every session in this repo need it? | **CLAUDE.md.** |
| 4 | Only some files or folders? | **`.claude/rules/<topic>.md`** with a `paths` glob, or a nested `CLAUDE.md` in that folder. |
| 5 | Only some tasks? | **`docs/`** for facts, with a one-line pointer from CLAUDE.md or the skill that needs it. **A skill** for steps. |
| - | No yes? | **Delete it.** |

Three checks run before the questions, because they are cheap and remove the most:

- **Generic advice** ("write clean code", "add tests") is true everywhere and informs nothing. Delete it.
- **A duplicate** of a line that already lives higher up. Delete the copy, keep the higher one.
- **Contradicted by the current code**, or the problem it warns about is fixed. Delete it.

Two rules keep the moves honest:

- **A rule needs a `paths` glob.** Without one it loads every session, the same as CLAUDE.md.
- **A doc needs a pointer.** Nothing loads `docs/` on its own. Every line moved there leaves a one-line pointer behind.

**Evidence gate on moves into CLAUDE.md.** Moving a line *up* into CLAUDE.md from somewhere narrower needs corroboration: two or more independent occurrences, or a team statement that it is a standing convention. Otherwise it stays where it is and is recorded as waiting on evidence. This keeps the skill from stuffing CLAUDE.md.

## Workflow

```
- [ ] Step 1: Pick the files and the mode
- [ ] Step 2: Split the files into lines
- [ ] Step 3: Route, then stop for approval
- [ ] Step 4: Apply and record
```

### Step 1: Pick the files and the mode

**If the user named the files** (`/context-management CLAUDE.md`), use them and skip discovery. Otherwise glob for what exists, without reading it yet: `CLAUDE.md` at the root and nested, `.claude/rules/`, `.claude/skills/*/SKILL.md`, `docs/`. Ask in one question which to review, offering only what exists, each with a count.

**Mode** is interactive unless the user says auto.

- **Interactive:** route in batches and approve each batch before it is applied.
- **Auto:** route everything, write one proposal file, apply nothing until it is approved.

**-> STOP only if** the selection resolved to more than one file. Show the list and confirm the scope.

### Step 2: Split the files into lines

For each file, extract items: one item is one claim that could move, stay, or be deleted on its own. Read `references/input-shapes.md` for how to split each kind of file.

Then read CLAUDE.md, `.claude/rules/` and `docs/` once, only to answer the duplicate check. Do not edit them unless they were selected.

If `context-audit.md` exists from an earlier run, read it. **Do not re-propose a move the user declined.**

Nothing is edited in this step.

### Step 3: Route, then stop for approval

Apply the checks and the five questions to every item. **Show only the items that move.** A line routed to where it already lives is not a decision. Use `references/routing-table.md` for the table.

- **Interactive:** batches of up to 8 moves. **-> STOP** after each batch. The user approves, edits, or rejects rows. Apply the approved rows, then show the next batch. One approval per batch, never one for the whole run.
- **Auto:** write every table to `context-routing-proposal.md`. **-> STOP.** Report its path. Apply only after the user approves it. If they edited it, re-read it first. Their version wins.

### Step 4: Apply and record

Apply the approved moves:

- **CLAUDE.md:** edit in place. Keep its headings.
- **Rule:** create or extend `.claude/rules/<topic>.md` with `paths` frontmatter, one short topic per file. Claude Code asks before writing in `.claude/`.
- **Doc:** create or extend `docs/<topic>.md` and add the pointer line.
- **Lint backlog and tickets:** do not create issues or lint config. List them in the record below. The team decides.

Then write or append `context-audit.md` at the repo root, one dated section per run:

- the mode, and each file's line count before and after
- moves applied, with source, destination, and the question that fired
- the lint backlog, with the tool and rule that would enforce each line
- ticket candidates
- moves the user declined, so a later run does not propose them again
- lines held by the evidence gate, with what they are waiting on

In auto mode, delete `context-routing-proposal.md` once the record is written.
