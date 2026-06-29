# DevClarity Marketplace

A [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) for DevClarity's plugins.

## Plugins

| Plugin | Description |
| :----- | :---------- |
| [`training`](./plugins/training) | Skills for building skills (finding opportunities, improving skills). |

## Install

**From a hosted git repo** (recommended for sharing — push this repo to GitHub/GitLab first):

```shell
/plugin marketplace add <owner>/<repo>
/plugin install training@devclarity-marketplace
```

**From a local clone:**

```shell
/plugin marketplace add /path/to/devclarity-marketplace
/plugin install training@devclarity-marketplace
```

Refresh after the marketplace is updated upstream: `/plugin marketplace update`.

## Requirements

- **macOS / Linux / WSL:** works out of the box.
- **Windows:** the `training` skills run bundled **bash** scripts (using `git`, `awk`,
  `sed`, `grep`, `find`). Install **[Git for Windows](https://gitforwindows.org/)** so
  Claude Code can use Git Bash for these — they will not run under bare PowerShell/cmd.
  `.sh` files are pinned to LF line endings (see `.gitattributes`) so shebangs survive
  Windows clones.

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
        └── skills/<skill>/{SKILL.md, scripts/}
```
