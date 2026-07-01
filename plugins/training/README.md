# Training Plugin

DevClarity training skills and tooling for Claude Code.

## Skills

| Skill | Use when |
| :---- | :------- |
| [`finding-skill-opportunities`](./skills/finding-skill-opportunities) | Auditing a codebase to decide what skills to write — mines git history and existing automation for recurring, multi-step procedures worth capturing. `/training:finding-skill-opportunities` |
| [`skill-improver`](./skills/skill-improver) | Reviewing or improving an existing skill — checks name/scope, description, structure, and leanness, and surfaces concrete references/scripts/determinism opportunities. `/training:skill-improver` |
| [`skill-eval-builder`](./skills/skill-eval-builder) | Setting up evals for a skill — scaffolds an `evals/` folder + scorecard measuring whether it fires, output is valid, is in time budget, or (optional) whether its classification gate labels inputs correctly. `/training:skill-eval-builder` |

## Requirements & portability

Most skills here run bundled **bash** scripts (`git`/`awk`/`sed`/`grep`/`find`);
`skill-eval-builder` runs **Python 3** scripts and calls the **`claude`** CLI. On
**Windows**, install [Git for Windows](https://gitforwindows.org/) so Claude Code can
run the bash scripts via Git Bash (they won't run under bare PowerShell/cmd). macOS,
Linux, and WSL work as-is.

**These scripts may not run on every machine — and that's OK.** They only automate
ordinary commands, and each skill is written to fall back to doing the same steps with
whatever tools your environment provides. A missing interpreter degrades gracefully
instead of blocking the task.

## Adding a skill

Each skill is a folder under `skills/` containing a `SKILL.md` file. The folder
name becomes the skill name, namespaced under the plugin (e.g. a `hello/` folder
is invoked as `/training:hello`).

```
skills/
└── my-skill/
    ├── SKILL.md      # metadata + instructions
    └── scripts/      # optional: deterministic helper scripts
```

A minimal `SKILL.md`:

```markdown
---
description: One-line summary so Claude knows when to use this skill.
---

Instructions for the skill go here.
```

After adding or editing a skill, run `/reload-plugins` to load it.
