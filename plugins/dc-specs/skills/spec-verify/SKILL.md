---
name: spec-verify
description: Use when checking a finished implementation against its dc-specs spec before review, in a repo that has specs/config.yaml - "verify OPS-412", "verify the spec", "check this PR against the acceptance criteria", or after spec-implement hands off. Audits the PR's evidence against the frozen spec, read from its source, and posts a verdict per criterion as a new PR comment. Runs in a fresh session and never edits the evidence.
---

# spec-verify

Audit the PR's evidence, criterion by criterion, and post a verdict. You do not write evidence or fix code.

Read `${CLAUDE_PLUGIN_ROOT}/references/framework.md` and `${CLAUDE_PLUGIN_ROOT}/references/evidence.md` first, then the adapter for the configured source.

If this conversation wrote the code or the evidence, stop and tell the human to run spec-verify in a new session.

## 1. Load

- Run Status. Continue only at `frozen`, noting `frozen_fingerprint`. Save the spec as read from the source to a temp file.
- Find the PR and read it (the framework's PR operations). Save the body as the evidence, note `headRefOid`, and check that commit out with a clean tree.
- Run `H evidence check --spec <spec> --evidence <evidence> --frozen <frozen_fingerprint> [--repo-tag <this repo>]`. Its errors are findings. With no evidence at all, stop and tell the human to run spec-implement's hand-off.
- Run `H verdict render --spec <spec> --evidence <evidence> --head <headRefOid> --frozen <frozen_fingerprint> --out <verdict>`.

## 2. Audit every criterion

1. **Read** the test the row names. Does it prove the Then clause, as amended?
2. **Run** it now.
3. **Break it:** change the implementation so the behavior is wrong, see the test fail, then `git checkout -- <file>`. For a reproduction, run the test on `<head>~1` in a worktree. For a refactor, run the suite at the base and head commits.
4. **Fill the row** with a verdict from `evidence.md`: a confirmed row says what you broke; any other row says why.

Never leave the tree modified, commit or push. A row is `waived` only when a human says so now; record the waiver.

For mockup slides with a deterministic renderer, render each still at the head commit and compare its sha256 with the PR's image.

## 3. Check the diff

From `git diff <base>...<head>`, fill **Unrequested changes** (every changed file no criterion needs, or None) and **Test helpers, fixtures and skips** (none touched, or each edit and the rows it weakens).

## 4. Check and post

Run `H verdict check --spec <spec> --verdict <verdict> --evidence <evidence> --head <headRefOid> --frozen <frozen_fingerprint> [--repo-tag <this repo>]`, fix every error, and use its `result_line`. If the PR's head moved, start again.

Show the human the verdict, then post it as a new comment. Tell them the Result and what a reviewer should look at first.
