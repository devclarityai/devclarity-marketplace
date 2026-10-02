---
name: spec-close
description: Use after a dc-specs spec's PR has merged - "close out OPS-412", "close the spec", "wrap up this spec", "what from this spec should we keep". Sorts what should outlive the change, promotes the rare lasting rule to the right CLAUDE.md through a reviewed PR, leaves everything else on the spec where search finds it, and posts a closing note with links.
---

# spec-close

Finish a merged spec. Most of what it decided stays on the spec; only a rule future work must follow moves.

Read `${CLAUDE_PLUGIN_ROOT}/references/framework.md` first, then the adapter for the configured source.

## 1. Confirm it is ready

- Read the spec and run Status. Find the PR and confirm it merged; if not, stop.
- Read the PR (the framework's PR operations) and save its body and comments. Run `H verdict latest --comments <file> --head <headRefOid> --spec <spec> --evidence <body>`.
- No current verdict (exit 1): show why each is stale. The human runs `spec-verify` again, or says to close without one, which you record as a `general` amendment.
- If the verdict's `frozen_fingerprint` differs from the spec's (`H fingerprint`), or Status is `changed`, the spec on record is not the one verified: tell the human.
- If the Result is not `confirmed`, ask whether to close anyway, and record the answer as a `general` amendment.

## 2. Sort what was decided

List every decision from the amendments, the evidence, the review thread and the verdict, one line each. Promote one only if a future change by someone who never saw this spec would go wrong without it (the framework's What outlives the change). Read the target `CLAUDE.md` first; do not duplicate or contradict it. One line per rule, citing the spec: `Reminders use the owner's time zone (OPS-412).`

Show the sorted list and get agreement. Expect most specs to promote nothing.

## 3. Promote

On a branch `<spec id>-close` from the default branch, edit the `CLAUDE.md` files and add any missing tests, commit, and open a PR titled `<spec id>: promote rules from spec`. Do not merge it.

## 4. Closing note

Post with the adapter's Close note:

```
Closed by spec-close.
PR: <merged PR link>
Verdict: <verdict link> - <its Result line>
Promoted: <CLAUDE.md PR link, with the rules> | nothing
```

For markdown, commit it on the `<spec id>-close` branch, even when nothing was promoted.

Then tell the human what was promoted, the note's link, and anything left open.
