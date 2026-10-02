# Source: markdown file

The spec is a file in the repo, `<markdown.dir>/<ID>-<slug>.md`, with frontmatter. Git is the history and the freeze.

| Operation | How |
|---|---|
| **Create** | `H render --template <name> --title "<title>"` prints the spec with frontmatter and the next free id. Write it to `<dir>/<ID>-<slug>.md` on the branch `<ID>-<slug>` and commit. |
| **Read** | Read the file. |
| **Status** | `H status <path>`, on the branch the work happens on. When changed, it includes the diff. |
| **Approve** | A human sets `status:` to `approval.status` and commits, on the branch the work happens on. If it was approved elsewhere, merge that in first. |
| **Freeze record** | None. The approving commit is the record. |
| **Amend** | `H amend --spec <path> --frozen <frozen_fingerprint> --criterion AC2 --text "..." --by "<name>"`, then commit naming the criterion. |
| **Status moves** | Set `status:` to `approval.in_progress` when building starts and `approval.done` at close, if configured, and commit each. |
| **Find related specs** | `grep -ril "<area>" <dir>`, and read each match's `status`. |
| **Find the PR** | `gh pr list --state all --search "<ID> in:title,body" --json number,title,state,url` |
| **Close note** | Append `## Closing note` after Amendments, set `status:` to `approval.done`, and commit. |

A squash merge makes the spec look created already approved; Status warns, and `spec-close` checks against the fingerprint in the PR's latest verdict.
