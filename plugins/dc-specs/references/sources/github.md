# Source: GitHub Issues

The spec is the body of an issue in `github.repo`. The approval label (`approval.status`) approves it. A comment holds the freeze record.

| Operation | How |
|---|---|
| **Create** | `H render --template <name> --title "<title>" > <tmp>`, fill it, then `gh issue create --repo <repo> --title "<title>" --body-file <tmp>`, or `gh issue edit <n> --repo <repo> --body-file <tmp>` for an existing issue. The spec id is `#<n>`. |
| **Read** | `gh issue view <n> --repo <repo> --json title,body,labels,state,url` |
| **Status** | `H status <n>`. It reads the labels and their history, the comments and the body's edit history. |
| **Approve** | A human adds the approval label. Re-approval is removing and re-adding it. |
| **Freeze record** | `gh issue comment <n> --repo <repo> --body "<record_to_post>"` |
| **Amend** | `H amend --issue <n> --criterion AC2 --text "..." --by "<name>"`. It refuses if the spec changed since freeze, or if the body changed while amending, and reads back. |
| **Find related specs** | `gh issue list --repo <repo> --state closed --search "<area> in:body" --json number,title` |
| **Find the PR** | `gh pr list --state all --search "#<n> in:body" --json number,title,state,url` in the code repo |
| **Close note** | `gh issue comment` with the note. `Closes #<n>` in the PR closes the issue. |

Branch names start with the issue number: `<n>-<slug>`. PR bodies include `Closes #<n>`.
