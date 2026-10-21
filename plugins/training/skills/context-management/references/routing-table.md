# Routing Table

The shape of every batch at the Step 3 stop, and of each file's table in an auto-mode proposal. Use it exactly, so every batch reads the same way.

## Format

```
Batch {n} of {total}: {file}, {section or line range}

| # | Line | Now | Fired | Goes to | Why |
|---|------|-----|-------|---------|-----|
| 1 | {claim, trimmed to one line} | {current file} | {Q1-Q5, or the check} | {destination} | {one clause, with the evidence} |

Unchanged: {n} lines stay where they are.
Held by the evidence gate: {line}: {what it is waiting on}.

Sizes: {file} {before} -> {after} lines if all approved.
Approve all, or reply with row numbers to change or reject.
```

## Filling it in

- **Only lines that move get a row.** A line staying put is a count, not a decision. A table of no-ops trains the reviewer to skim past the one real deletion.
- **One row per item.** If a line splits (part to lint, part stays), give each half a row and say so in Why.
- **Trim the line to one line.** The reviewer judges the routing, not the wording.
- **Fired** is the question number (Q1 to Q5) or the check (generic, duplicate, contradicted). Every row names what authorized it.
- **Why** is one clause and carries the evidence: "RuboCop Style/StringLiterals enforces it" beats "this is lintable". With no evidence, say so: "no cited origin".
- **Name each evidence-gate hold.** Never fold them into the count. They are the lines a later run may move.

## Worked example

```
Batch 1 of 1: CLAUDE.md, whole file

| # | Line | Now | Fired | Goes to | Why |
|---|------|-----|-------|---------|-----|
| 1 | Use single quotes and no semicolons | CLAUDE.md | Q1 | lint backlog | Prettier config already enforces it |
| 2 | Refund e2e test is flaky until PAY-511 lands; rerun once | CLAUDE.md | Q2 | ticket | true until PAY-511 closes |
| 3 | Handlers stay thin; validate input with the zod schemas in src/api/schemas/ | CLAUDE.md | Q4 | .claude/rules/api-handlers.md, paths src/api/** | only matters in handler files |
| 4 | Rounding is banker's, once per invoice, never per line | CLAUDE.md | Q5 | docs/money.md + pointer | refunds, invoicing and reporting tasks need it |
| 5 | Write clean, well-tested code | CLAUDE.md | generic | delete | true everywhere, informs nothing |

Unchanged: 11 lines stay where they are.
Held by the evidence gate: none.

Sizes: CLAUDE.md 48 -> 41 lines if all approved.
Approve all, or reply with row numbers to change or reject.
```

"Never edit src/generated/; it is rebuilt from openapi.yaml" stays (Q3: any session can touch generated code by accident), so it has no row. It is one of the 11.
