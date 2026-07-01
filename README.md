# DevClarity Marketplace

A [Claude Code plugin marketplace](https://code.claude.com/docs/en/plugin-marketplaces) for DevClarity's plugins.

## Plugins

| Plugin | Description |
| :----- | :---------- |
| [`training`](./plugins/training) | Skills for building skills (finding opportunities, improving skills). |

## Install

```shell
/plugin marketplace add devclarityai/devclarity-marketplace
/plugin install training@devclarity-marketplace
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
        └── skills/<skill>/{SKILL.md, scripts/}
```
