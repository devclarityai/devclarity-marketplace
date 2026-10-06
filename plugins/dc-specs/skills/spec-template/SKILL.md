---
name: spec-template
description: Use when someone wants a new or changed dc-specs spec template or evidence template - "make a spec template", "we need a template for QA test plans", "add a rollout section to our feature template", "change what the PR evidence asks for", "what spec templates do we have". Asks what the template is for and what it should contain, writes it and its paired evidence template to specs/templates/, checks both, and commits them on a branch. Also runs when spec-author finds no template that fits.
---

# spec-template

Create or change a spec template and its paired evidence template.

Read `${CLAUDE_PLUGIN_ROOT}/references/framework.md` (Spec shape) and `${CLAUDE_PLUGIN_ROOT}/references/evidence.md` (Templates) first. Run everything from inside the repo.

## 1. Which job

Run `H templates`.

- **List:** show each name, description, whether it is the repo's own, any `errors`, and its evidence template. Stop.
- **Change one:** go to step 3 with its text and its evidence template's. Changing a default makes a repo template of the same name.
- **New one:** ask with AskUserQuestion (header `Start from`): the defaults, plus "Blank", the closest first with `(Recommended)`.

## 2. Ask what it needs

In one batch, only what you cannot infer:

- **Name:** lowercase letters, digits and hyphens, like `qa-plan`.
- **When to use it:** one line describing the kind of work. spec-author matches against it.
- **Sections**, in order.
- **Criteria** every spec of this type must prove, as examples.
- **Evidence** the PR must show beyond one row per criterion.

## 3. Write

Write `specs/templates/<name>.md` (or the folder the `templates` key names):

```
---
name: <name>
description: <when to use it, one line>
---
## <Section>

<!-- A short prompt. -->

## Acceptance criteria

- AC1 Given <state>, when <action>, then <result>.

## Amendments

<!-- Added after approval only, one line each: - YYYY-MM-DD ACn: what changed or was clarified (answered by Name) -->
```

No `# ` title heading. Prompts go in `<!-- -->` comments, which are dropped on trackers.

`H lint` catches a placeholder only when it is lowercase `<...>` text of letters, digits, spaces and `,.:'-`. A template placeholder that starts with a capital letter, or contains any other punctuation, is not caught.

Then write `specs/templates/<name>.evidence.md`, starting from the plugin's `templates/<start>.evidence.md`, or `feature` for Blank. Keep it small. When changing an existing one, add 1 to `version`.

Run `H templates` and fix any `errors` on both. Then `H render --template <name> --title "Example" > <tmp>` and `H evidence render --spec <tmp> --template <name>`, and show the human both.

## 4. Commit

Stage only the two files and commit on a branch (`spec-template-<name>`, or the current branch if it is not the default). Offer to push and open a PR. Existing specs are unchanged; open PRs re-render their evidence with `--merge`.

Tell the human the name and that spec-author will offer it. If spec-author sent you here, return to it.
