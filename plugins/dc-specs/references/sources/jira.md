# Source: Jira

The spec is the description of a Jira issue, through the Atlassian MCP. Use `jira.site` as the `cloudId`; if a call rejects it, get the id from `getAccessibleAtlassianResources`. The status in `approval.status` approves it. A comment holds the freeze record.

Pass `contentFormat: "markdown"` on every write and `responseContentFormat: "markdown"` on every read. The fingerprint ignores the formatting Jira changes on each round trip.

| Operation | How |
|---|---|
| **Create** | `H render --template <name> --title "<title>"`, fill it, then `createJiraIssue` with `projectKey`, `issueTypeName` (`jira.issue_type` or `Story`), `summary` and the body as `description`, or `editJiraIssue` with `fields: {"description": ...}` for an existing ticket. The spec id is the issue key. |
| **Read** | `getJiraIssue` with `fields: ["summary","description","status","comment"]` |
| **Status** | `getJiraIssue` with `fields: ["description","status","comment"]` and `expand: "changelog"`. Save the whole response to a JSON file, then `H status <file>`. |
| **Approve** | A human moves the issue to the approval status. Re-approval is moving it out and back. If Status finds no approval time, re-approval is the human deleting the old freeze record. |
| **Freeze record** | `addCommentToJiraIssue` with `record_to_post` as the body. |
| **Amend** | Save the description to a file, then `H amend --spec <file> --frozen <frozen_fingerprint> --criterion AC2 --text "..." --by "<name>"`. Write the file back with `editJiraIssue`, exactly as the helper wrote it. Read back and pipe the description to `H fingerprint --frozen <the fingerprint before the write>`: `changed_since_freeze` must be false. |
| **Find related specs** | `searchJiraIssuesUsingJql` with `project = <KEY> AND statusCategory = Done AND text ~ "<area>"` |
| **Find the PR** | `gh pr list --state all --search "<KEY> in:title" --json number,title,state,url` in the code repo |
| **Close note** | `addCommentToJiraIssue` with the note. Leave the status to the team. |

Branch names start with the key: `<KEY>-<n>-<slug>`. PR titles start with the key so Jira links them.
