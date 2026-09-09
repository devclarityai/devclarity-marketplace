# DevClarity Marketplace

A [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) for DevClarity's plugins.

## Plugins

| Plugin | Description |
| :----- | :---------- |
| [`training`](./plugins/training) | Skills for building skills — finding what to write, improving and evaluating what you have — plus `context-coverage`, which audits how well your agent context (CLAUDE.md / AGENTS.md / rules / skills) actually covers your code. |

### What's in `training`

| Skill | Does |
| :---- | :--- |
| `context-coverage` | Audits agent-context coverage across your repos — or across one monorepo, scoped to just the areas your team owns — and renders a self-contained HTML report: things worth checking, per-repo metrics, and a folder tree colored by whether a context file governs it. |
| `finding-skill-opportunities` | Mines git history, existing automation and session transcripts for recurring procedures worth turning into a skill. |
| `skill-improver` | Reviews an existing skill for scope, description, structure and leanness. |
| `skill-eval-builder` | Scaffolds an `evals/` folder and scorecard for a skill. |

## Install

```shell
/plugin marketplace add devclarityai/devclarity-marketplace
/plugin install training@devclarity-marketplace
```

Then run a skill by name, e.g.:

```shell
/training:context-coverage
```

Refresh later with `/plugin marketplace update`.

## Requirements & portability

- **macOS / Linux / WSL:** works out of the box.
- **Windows:** bundled **bash** scripts need **[Git for Windows](https://gitforwindows.org/)**
  so Claude Code can run them via Git Bash (not bare PowerShell/cmd). `.sh` files are
  pinned to LF line endings (see `.gitattributes`) so shebangs survive Windows clones.
- **Tooling varies:** some skills use bash + POSIX utilities; some use **Python 3** and
  the **`claude`** CLI. These scripts may not run on every setup — and that's fine: each
  skill is written to **fall back** to performing the same steps with whatever tools your
  environment provides, so a missing interpreter degrades gracefully rather than blocking.

## Develop

Test a plugin directly without installing:

```shell
claude --plugin-dir ./plugins/training
```

After editing plugin files, run `/reload-plugins` to pick up changes.

## Structure

```
devclarity-marketplace/
├── .claude-plugin/
│   └── marketplace.json     # marketplace catalog
├── .gitattributes           # LF line endings for *.sh (Windows safety)
└── plugins/
    └── training/
        ├── .claude-plugin/plugin.json
        └── skills/<skill>/{SKILL.md, scripts/, references/}
```
