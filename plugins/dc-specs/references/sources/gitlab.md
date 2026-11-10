# Source: GitLab Issues

The spec is the description of an issue in `gitlab.project` on `gitlab.host` (default `gitlab.com`), through the `glab` CLI. The approval label (`approval.status`) approves it. A scoped label such as `spec::approved` works well, because GitLab removes the other `spec::` labels when one is added. A comment holds the freeze record.

Every write goes through `H gitlab` or `H amend`, never `glab issue` or `glab mr`, so each call names the host and the text goes as a JSON body rather than a command-line argument. `glab` must be logged in to the host: `glab auth login --hostname <host>`.

| Operation | How |
|---|---|
| **Create** | `H render --template <name> --title "<title>" > <tmp>`, fill it, then `H gitlab create --title "<title>" --body-file <tmp>`, or `H gitlab describe --issue <n> --body-file <tmp>` for an existing issue. The spec id is `#<n>`. `round_trip` must be true. |
| **Read** | `glab api --hostname <host> projects/<url-encoded project>/issues/<n>`; `.description` is the spec. |
| **Status** | `H status <n>`. It reads the labels and their history, the comments and the description edits. |
| **Approve** | A human adds the approval label. Re-approval is removing and re-adding it. |
| **Freeze record** | Write `record_to_post` to a file, then `H gitlab comment --issue <n> --body-file <file>`. |
| **Amend** | `H amend --issue <n> --criterion AC2 --text "..." --by "<name>"`. It refuses if the spec changed since freeze, or if the description changed while amending, and reads back. |
| **Find related specs** | `glab api --hostname <host> "projects/<url-encoded project>/issues?state=closed&search=<area>&in=description"` |
| **Find the PR** | `H gitlab mr-find --issue <n>`: the merge requests whose description names `#<n>`. |
| **Close note** | `H gitlab comment --issue <n> --body-file <note>`. `Closes #<n>` in the merge request closes the issue when it merges into the default branch. |

The code repo is the same GitLab project unless `code_host` says otherwise, so the framework's PR operations use merge requests (`framework.md`, PR operations).

Branch names start with the issue number: `<n>-<slug>`, which is also what GitLab's own "Create branch" button makes. Merge request descriptions include `Closes #<n>`.
