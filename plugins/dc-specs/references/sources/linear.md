# Source: Linear

The spec is the description of a Linear issue, through the Linear MCP server: its get-issue, create-issue, update-issue, list-comments and create-comment tools. If no Linear MCP is connected, stop and tell the human to connect it. The workflow state in `approval.status` approves it. A comment holds the freeze record.

| Operation | How |
|---|---|
| **Create** | `H render --template <name> --title "<title>"`, fill it, then create an issue in team `linear.team` with that description, or update the human's existing issue. The spec id is the identifier (`OPS-123`). |
| **Read** | Get the issue (identifier, description, state) and its comments. |
| **Status** | Write an events file, then `H status <file>`: `{"id": "OPS-123", "body": "<description>", "status": "<state>", "comments": [{"body": "...", "at": "<createdAt>"}], "approvals": ["<time it entered the approval state>"], "body_edits": [{"at": "...", "by": "..."}], "history_complete": true}`. If the MCP exposes no history, leave `approvals` and `body_edits` empty, set `history_complete` to false, and tell the human re-approval and early edits cannot be checked. |
| **Approve** | A human moves the issue to the approval state. Without history, re-approval is the human deleting the old freeze record. |
| **Freeze record** | Post `record_to_post` as a comment. |
| **Amend** | Save the description to a file, `H amend --spec <file> --frozen <frozen_fingerprint> --criterion AC2 --text "..." --by "<name>"`, then update the description with the file exactly. Read back and pipe it to `H fingerprint --frozen <the fingerprint before the write>`: `changed_since_freeze` must be false. |
| **Find related specs** | Search the team's completed issues for the area name. |
| **Find the PR** | `gh pr list --state all --search "<identifier>" --json number,title,state,url` in the code repo |
| **Close note** | Comment with the note. Leave the state to the team. |

Branch names use Linear's suggested branch name, or `<identifier>-<slug>`.
