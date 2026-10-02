# Source: Azure DevOps

The spec is the Description of a work item in `ado.project` of the Azure DevOps Services organization `ado.org`, through the `az` CLI and its `azure-devops` extension. The State in `approval.status` approves it. A comment holds the freeze record.

Descriptions are Markdown. `az boards` writes only HTML, so every Description and comment write goes through `H ado`, never `az boards work-item update`. `H ado` escapes `<`, `>` and `&` on write, because Azure DevOps strips anything shaped like an HTML tag from Markdown. Setting a Markdown Description on a work item whose Description is HTML converts that field for good: say so when confirming the write.

| Operation | How |
|---|---|
| **Create** | `H render --template <name> --title "<title>" > <tmp>`, fill it, then `H ado create --title "<title>" --body-file <tmp>` (type `ado.work_item_type`, or `--type`), or `H ado describe --item <n> --body-file <tmp>` for an existing work item. The spec id is `AB#<n>`. `round_trip` must be true. |
| **Read** | `az boards work-item show --id <n> --org https://dev.azure.com/<org> -o json`; `.fields["System.Description"]` is the spec. |
| **Status** | `H status <n>`. It reads the State history, the Description edits and the comments. When changed, it includes the diff from the frozen Description. |
| **Approve** | A human moves the work item to the approval State. Re-approval is moving it out and back. |
| **Freeze record** | Write `record_to_post` to a file, then `H ado comment --item <n> --body-file <file>`. |
| **Amend** | `H amend --item <n> --criterion AC2 --text "..." --by "<name>"`. It refuses if the spec changed since freeze, or if the work item changed while amending, and reads back. |
| **Find related specs** | `az boards query --org https://dev.azure.com/<org> --project "<project>" --wiql "SELECT [System.Id], [System.Title] FROM WorkItems WHERE [System.TeamProject] = @project AND [System.State] = '<approval.done>' AND [System.Description] CONTAINS WORDS '<area>'"` |
| **Find the PR** | `gh pr list --state all --search "AB#<n> in:body" --json number,title,state,url` in the code repo |
| **Close note** | `H ado comment --item <n> --body-file <note>`. Leave the State to the team. |

Branch names start with the work item number: `<n>-<slug>`. PR bodies include `AB#<n>`, which the Azure Boards GitHub app links; not `Fixes AB#<n>`, which would move the State.
