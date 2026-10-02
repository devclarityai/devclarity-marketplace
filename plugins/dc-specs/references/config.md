# specs/config.yaml

One file per repo, at `specs/config.yaml` from the repo root. It names where specs live and what freezes them. `spec-setup` writes it with `dcspecs.py init` and checks it with `dcspecs.py setup-check`.

It is a small YAML subset: keys indented with spaces, scalars, quoted strings, `[a, b]` and `- item` lists. Status and label names match case-insensitively.

## Keys

| Key | Required | Meaning |
|---|---|---|
| `source` | yes | `markdown`, `github`, `jira`, `linear` or `ado` |
| `approval.status` | yes | The value that approves and freezes a spec: a frontmatter status, a GitHub label, a Jira/Linear status name, or an Azure DevOps State |
| `approval.in_progress` | no | The status when building starts. Counts as frozen |
| `approval.done` | no | The status at close. Counts as frozen |
| `approval.also_frozen` | no | Any other statuses that still count as frozen, such as `In Review` |
| `markdown.dir` | no | Where markdown specs live. Default `specs` |
| `markdown.id_prefix` | no | Prefix for new spec ids. Default `SPEC` |
| `github.repo` | github | `owner/name` of the repo whose issues hold specs |
| `jira.site` | jira | The Atlassian site, such as `acme.atlassian.net` |
| `jira.project` | jira | Project key, such as `OPS` |
| `jira.issue_type` | no | Issue type for new specs. Default `Story` |
| `linear.team` | linear | Team key, such as `OPS` |
| `ado.org` | ado | The Azure DevOps Services organization, the part after `dev.azure.com/` |
| `ado.project` | ado | Project name, such as `Ops Platform` |
| `ado.work_item_type` | no | Work item type for new specs. Default `User Story` (Scrum: `Product Backlog Item`, Basic: `Issue`) |
| `templates` | no | Folder of the repo's own templates. Default `specs/templates` |

## Examples

```yaml
# markdown
source: markdown
approval:
  status: approved
  in_progress: in-progress
  done: done
markdown:
  dir: specs
  id_prefix: SPEC
```

```yaml
# github
source: github
approval:
  status: spec:approved     # a label
github:
  repo: devclarityai/devclarity-ops
```

```yaml
# jira
source: jira
approval:
  status: Ready for Dev
  in_progress: In Progress
  done: Done
  also_frozen: [In Review]
jira:
  site: devclarity.atlassian.net
  project: OPS
```

```yaml
# linear
source: linear
approval:
  status: Ready     # a state issues are moved into, never created in
  in_progress: In Progress
  done: Done
  also_frozen: [In Review]
linear:
  team: OPS
```

```yaml
# ado
source: ado
approval:
  status: Approved     # a State items are moved into, never created in
  in_progress: Committed
  done: Done
ado:
  org: devclarity
  project: Ops Platform
  work_item_type: Product Backlog Item
```
