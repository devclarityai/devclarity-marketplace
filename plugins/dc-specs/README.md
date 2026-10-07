# dc-specs

Spec-driven development for Claude Code: spec templates and six skills that take a spec from draft to close. The spec lives in the tracker the team already uses (Jira, Linear, Azure DevOps, GitHub Issues or a markdown file), with no copy kept anywhere else.

`spec-implement` writes the PR description as evidence that each acceptance criterion is met. `spec-verify`, run in a fresh session, checks that evidence against the spec and posts its verdict as a PR comment, and `spec-implement` can start that fresh session as a subagent after asking.

## The flow

| Step | Skill | Use it when | It does |
|---|---|---|---|
| 1 | `spec-setup` | A repo has no `specs/config.yaml`, or its setup needs changing or checking | Picks the source and approval status, checks them, commits the config. |
| 2 | `spec-template` | The team wants its own spec or evidence shape (optional) | Writes a spec template and its evidence template to `specs/templates/`. |
| 3 | `spec-author` | A ticket or idea needs a spec | Writes numbered Given/When/Then criteria onto the source for a human to approve. |
| 4 | `spec-implement` | The spec is approved | Builds it test first, records every answer as an amendment, and opens the PR with the evidence. |
| 5 | `spec-verify` | The PR is open, in a fresh session. `spec-implement` can start that fresh session as a subagent after asking | Audits the evidence against the frozen spec and posts a verdict per criterion. |
| 6 | `spec-close` | The PR has merged | Adds any rule worth keeping to `CLAUDE.md` through a reviewed PR and posts a closing note. |

The skills call the helper script, `scripts/dcspecs.py`. You don't need to run it yourself.

## Install

```
/plugin marketplace add devclarityai/devclarity-marketplace
/plugin install dc-specs@devclarity-marketplace
```

The plugin needs Python 3.9 or later and git, on macOS, Linux or Windows, plus the tool for your tracker (`gh`, `az`, or the Atlassian or Linear MCP server). `spec-setup` checks for each one and walks you through installing what's missing.

## Getting started

In the repo you want to use specs in, ask Claude to "set up dc-specs". `spec-setup` checks the tools, asks where your team tracks work and which status approves a spec, and commits `specs/config.yaml`. Then ask it to "spec this ticket" to write your first spec.

## Reporting a problem

Ask Claude to "report a dc-specs bug" or "report issue". `report-issue` searches the existing issues for a duplicate, drafts a bug report or feature request with your dc-specs, OS and tool versions, and files it on [devclarityai/devclarity-marketplace](https://github.com/devclarityai/devclarity-marketplace/issues) once you say yes. It leaves out your specs, file paths, repo names and tracker details unless you typed them into the report. Without a working `gh`, it gives you a prefilled link to submit in the browser.

## Session note

At session start in a repo whose git root has `specs/config.yaml`, the plugin's one hook adds a short note: which tracker holds the specs, the spec id the branch is named for, and that approved specs only change below Amendments. It never repeats text the repo controls, so a cloned repo cannot put instructions into it. Elsewhere it prints nothing. It reads only the config and git, and never fails a session.

Turn it off with `DC_SPECS_SESSION_NOTE=off` (also `0`, `false`, `no`), in the shell or the `env` block of your Claude Code settings.

## Layout

| Path | Holds |
|---|---|
| `skills/` | The six spec skills, and `report-issue` |
| `hooks/hooks.json` | The session note (`dcspecs.py session-context`) |
| `templates/` | The default spec templates, their evidence templates (`<name>.evidence.md`), and the verdict template |
| `references/framework.md` | The rules every skill shares, and the helper's commands |
| `references/evidence.md` | The evidence and verdict formats |
| `references/config.md` | `specs/config.yaml` keys and examples |
| `references/sources/` | One adapter per source |
| `scripts/dcspecs.py` | The helper |
| `tests/` | `python3 -m unittest discover -s tests` |

