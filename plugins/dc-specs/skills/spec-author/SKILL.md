---
name: spec-author
description: Use when turning a ticket, issue or idea into a dc-specs spec before building it - "spec this ticket", "write a spec for OPS-412", "draft the acceptance criteria", "refine this story". Decides whether the change needs a spec, recommends a template and lets the human choose, asks the questions a QA lead and a tech lead would, and writes numbered Given/When/Then acceptance criteria onto the spec's source of truth (Jira, Linear, Azure DevOps, GitHub Issues or a markdown file). Not for test specs (RSpec, Jest), OpenAPI specs or other technical specifications.
---

# spec-author

Take a ticket or idea to a spec ready for a human to approve, written on its source of truth.

Read `${CLAUDE_PLUGIN_ROOT}/references/framework.md` first, then the adapter for the configured source.

## 1. Gather context

- The ticket (the adapter's Read), or the human's description. If it is already approved (Status), stop: the human sends it back to refinement first.
- The repo's `CLAUDE.md` files, including those in the folders the work touches.
- The two or three most relevant closed specs (Find related specs). Their amendments record decisions not to contradict.
- Enough code to know what exists today. Do not design the implementation.

## 2. Does it need a spec?

Apply the framework's rule and tell the human the answer in one line. If it does not, stop.

## 3. Choose the template

Run `H templates` and pick the valid one whose description fits best. Ask with AskUserQuestion (header `Template`): the recommendation first, labelled `(Recommended)` with the reason, then up to three others. Other lets the human name a template or describe a new shape; for a new shape, run `spec-template`, then return here.

Run `H render --template <name> --title "<title>"` to a temp file and keep the header it writes.

## 4. Draft, then interrogate

Fill every section. Delete template comments; write "None" for a section that is empty on purpose.

Then ask, in one batch, only where the draft is unsure:

- **QA lead:** the edges (empty, duplicate, concurrent, permission denied, time zones), what done looks like to a user, what must still work.
- **Tech lead:** the invariants it passes near, what it must not change, migration and rollback, what is out of scope.

Fold the answers into the sections. Amendments stays empty until approval.

## 5. Write the criteria

One criterion per line, in the framework's form. Split any that checks two things. Keep the template's own criteria, filled in. If the ticket had criteria, keep their intent and say which original each came from.

## 6. Lint and write

Run `H lint --spec <tmp>` and fix every error. Show the human the spec, then write it with the adapter's Create. For a tracker, read it back and lint what came back. Run Status: a new spec must be `not-approved`; if it is not, the approval status is the tracker's creation default, so run `spec-setup` to change it.

## 7. Hand off

Tell the human where the spec is, what approves it, and that `spec-implement` builds it once approved. Do not approve it yourself unless told to.
