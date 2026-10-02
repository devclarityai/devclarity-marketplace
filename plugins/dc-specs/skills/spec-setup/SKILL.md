---
name: spec-setup
description: Use when setting up, changing or checking dc-specs in a repo - "set up specs in this repo", "set up dc-specs", "switch specs to Jira", "change which status approves specs", "is dc-specs set up right", or when another dc-specs skill finds no specs/config.yaml. Walks through installing the tools it needs, picks the spec source (markdown, GitHub Issues, Jira, Linear or Azure DevOps) and the status that approves a spec, checks the connection and status names, writes and commits specs/config.yaml.
---

# spec-setup

Get a repo ready for dc-specs, change its setup, or check it. The result is a committed `specs/config.yaml` and a passing check.

Read `${CLAUDE_PLUGIN_ROOT}/references/config.md` for the keys and `${CLAUDE_PLUGIN_ROOT}/references/framework.md` for `H`. Run everything from inside the repo.

## 1. Dependencies

Find `<python>` for `H` (`framework.md`, Helper). If no candidate is 3.9 or later, walk the human through installing Python before anything else, then check again:

| OS | Install |
|---|---|
| macOS | `xcode-select --install`, or `brew install python` |
| Linux | The package manager: `sudo apt install python3` or `sudo dnf install python3` |
| Windows | `winget install --id Python.Python.3.13 -e`, then open a new terminal. A `python3` that opens the Microsoft Store is a placeholder, not Python. |

Run `H deps`. For each check that is not `ok`, show its `install` step, wait for the human to run it, and run `H deps` again until it is `ok`.

## 2. Which job

Run `H config`. No config: set up from step 3. A check: run `H deps` (it reads the source from the config), then go to step 5. A change, or an invalid config: show the current one and ask what changes, then go to step 3 keeping everything else.

## 3. Source and details

Ask which the team uses to track work: **Jira**, **Linear** or **Azure DevOps** (stories are refined there), **GitHub Issues** (the repo's issues are the backlog) or **Markdown** (no tracker; specs are files in the repo). Pick where the team already writes stories.

Look up the details before asking, and confirm them:

| Source | Detail | Where to look |
|---|---|---|
| markdown | folder, id prefix | Default `specs` and `SPEC` |
| github | `owner/repo` | `gh repo view --json nameWithOwner -q .nameWithOwner` |
| jira | site, project key, issue type | `getAccessibleAtlassianResources`; ask the key; default `Story` |
| linear | team key | The Linear MCP's team list. With no Linear MCP, stop and ask the human to connect it |
| ado | organization, project, work item type | `az devops configure --list`; `az devops project list --org https://dev.azure.com/<org>`; the process's backlog type (`User Story`, `Product Backlog Item` or `Issue`). Needs `az login` |

Once the source is picked, run `H deps --source <source>` and repeat the install loop from step 1 for its tools (`gh` for GitHub, `az` and its `azure-devops` extension for Azure DevOps). Do each `agent_checks` item: Jira and Linear need their MCP server connected.

## 4. Approval status

List the statuses that exist: Jira, the distinct statuses of the project's recent issues and one issue's transitions; Linear, the team's workflow states; Azure DevOps, `az devops invoke --area wit --resource workItemTypeStates --route-parameters project="<project>" type="<type>" --org https://dev.azure.com/<org>`; GitHub, `gh label list --repo <repo> --limit 1000` (a label such as `spec:approved` is best); markdown, default `approved`.

Ask for the **approval** status, one an issue is moved into and never created in. Optionally ask for **in progress**, **done** and any **also frozen** statuses after it; all of them count as frozen.

## 5. Write and check

```
H init --source <source> --approval "<status>" [--in-progress "<s>"] [--done "<s>"] [--also-frozen "<s>" ...] \
  [--repo <owner/repo>] [--site <site>] [--project <KEY or name>] [--issue-type <type>] [--team <KEY>] \
  [--org <org>] [--work-item-type <type>] \
  [--dir <folder>] [--id-prefix <prefix>] --dry-run
```

Show the config, its `changes` and `warnings`, and confirm. When the source or location changes, list the specs in flight in the old place and say they stay there. Then run it without `--dry-run`, adding `--force` if it says `needs_force`.

Run `H setup-check`. Fix every `error` (a missing GitHub label comes with its `gh label create` command), report every `warning`, and do each `agent_checks` item with the MCP tools. Setup is done when it is `ok` and every agent check passed.

## 6. Commit

Stage only `specs/config.yaml` and commit on a branch, `dc-specs-setup` unless the human wants it in their current branch. Offer to push and open a PR; until it merges, dc-specs works only on branches that have the config.

Tell the human the source, the approval status and that the check passed, and that `spec-template` makes the team's own templates. Do not mention dc-specs in the repo's `CLAUDE.md`; the plugin's session hook does that. If another skill sent you here, return to it.
