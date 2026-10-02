---
name: spec-implement
description: Use when building an approved dc-specs spec in a repo that has specs/config.yaml - "build OPS-412", "implement the spec", "build it" after a spec is approved, "start on this spec". Confirms the spec is frozen and records the version it builds against, plans against the numbered acceptance criteria, writes tests first, and stops to ask when the spec is unclear, recording every answer on the spec as a dated amendment, fills the evidence as tests pass, and opens the PR with the evidence as its description. Never edits the frozen spec.
---

# spec-implement

Build what an approved spec says, and nothing it does not.

Read `${CLAUDE_PLUGIN_ROOT}/references/framework.md` and `${CLAUDE_PLUGIN_ROOT}/references/evidence.md` first, then the adapter for the configured source.

## 1. Confirm it is frozen

Run Status and act on the state as the framework says. Continue only at `frozen`. Run `H lint` on the spec; errors in a frozen spec are the human's to fix.

Tell the human in one line: the spec id, `frozen_fingerprint`, and the criteria and amendment counts.

## 2. Branch

Work on a branch named with the adapter's convention, from the default branch. If `specs/config.yaml` is not there yet, branch from the one that has it and say so. For markdown, the branch must contain the approving commit; do the adapter's Status moves.

## 3. Plan

In the session, not a file: one step per unit of work naming the criteria it satisfies, the test each criterion gets, and every criterion covered. Anything no criterion asks for is a question for the human. Show the plan before writing code.

## 4. Build, tests first

For each step, write the test from the criterion, see it fail for the right reason, then write the code until it passes. Run the wider suite before moving on. Stay inside the spec's scope.

Render the evidence once, after the plan, outside the repo:

```
H evidence render --spec <spec> --frozen <frozen_fingerprint> [--id <spec id>] [--url <link>] [--repo-tag <this repo>] --out <evidence>
```

Fill a criterion's row when its test passes. After an amendment or a new template version, render again with `--merge <evidence>`.

- **Reproduction:** commit the failing test on its own before the fix, so the verifier can run it on the fix's parent.
- **Mockup slides:** render each still at the slide's keys, rung and width, beside the approved mockup.

## 5. Stop and ask

Stop at anything the framework's consult loop names, or when a criterion needs something out of scope. Ask one question citing the criterion, and record the answer with the adapter's Amend before continuing.

## 6. Hand off

1. Finish every row and section, and the CI line. A criterion without a passing test is `not verified`.
2. Run `H evidence check --spec <spec> --evidence <evidence> --frozen <frozen_fingerprint> [--repo-tag <this repo>]` and fix every error.
3. Show the human the description, then open the PR with it, or update it (the framework's PR operations).
4. Tell the human to run `spec-verify` in a new session.

On every later push, update the rows it changed, check again, update the description, and tell the human to verify again.
