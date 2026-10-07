# dc-specs framework

The rules every dc-specs skill shares. Skills link here instead of repeating them.

## One spec, one source of truth

A spec lives in one place: the source named in `specs/config.yaml`, which is a Jira issue, a Linear issue, an Azure DevOps work item, a GitHub issue or a markdown file. There is no second copy. Every decision, clarification and correction is recorded on the spec as a dated amendment, not in chat, plans or PR threads.

Every skill starts with `H config`. With no valid config, `spec-author` runs `spec-setup` first and continues; the other skills stop and tell the human to run `spec-setup`. `report-issue` is the exception: it files an issue about dc-specs itself and needs no config.

Source-specific steps live in `references/sources/<source>.md`, the adapter. Skills name its operations: Create, Read, Status, Approve, Freeze record, Amend, Find related specs, Find the PR, Close note.

## Helper

`H` is `<python> ${CLAUDE_PLUGIN_ROOT}/scripts/dcspecs.py`, where `<python>` is the first of `python3`, `python` and `py -3` whose `--version` is 3.9 or later. Windows often has only `python` or `py`. If none is, the skill stops and tells the human to run `spec-setup`, which installs it. Run `H` inside the repo that owns the spec, or pass `--config <path>`. Anything countable goes through it, never by eye. Output is JSON. Exit 1 means a check failed, exit 2 an error.

| Command | Use |
|---|---|
| `deps [--source S]` | Check Python, git and the tools the source needs. Each missing one comes with its install step for this OS. Used by `spec-setup`. |
| `config` | Validate and print `specs/config.yaml`. |
| `init --source S --approval A [...] [--dry-run] [--force]` | Write the config. Used by `spec-setup`. |
| `setup-check` | Check the config, connection, labels and repo templates. |
| `templates` | The templates this repo can use, each with its evidence template. |
| `render --template N --title T [--id ID]` | A new spec from a template, with the header for this source. |
| `lint [--spec F] [--approved] [--published]` | Check sections, criteria, amendments and placeholders, plus the slide-image, placeholder and published-image checks. `--approved` reports those three as warnings. `--published` checks that tracker images are uploaded and markdown image files exist. Prints the criteria, amendment count and fingerprint. |
| `fingerprint [--spec F] [--frozen FP]` | The fingerprint, and whether it differs from `--frozen`. |
| `amend --criterion AC2 --text "..." --by Name [--frozen FP] [--spec F \| --issue N \| --item N]` | Add a dated amendment. Refuses if the spec no longer matches `--frozen`, or if the write would change the frozen text. `--spec` edits the file, stdin prints the new body, `--issue` edits a GitHub issue, `--item` an Azure DevOps work item. |
| `status <target>` | The freeze state. The adapter's Status says what the target is. |
| `ado create\|describe\|comment [--item N] [--title T] --body-file F` | Azure DevOps writes in Markdown (`sources/ado.md`). |
| `evidence render\|check`, `verdict render\|check\|latest` | The PR description and the verdict comment (`evidence.md`). |
| `report-env` | The dc-specs, OS, Python and tool versions for an issue, and the source type. No paths or config values. Works without a config. Used by `report-issue`. |
| `report-link --title T --label bug\|enhancement --body-file F` | A prefilled new-issue link on the dc-specs repo. The body is in it only while the link fits 8000 characters; otherwise it comes back to paste. Used by `report-issue`. |

Without `--spec`, a command reads the spec from stdin.

## Spec shape

A spec starts from a template, always through `H render`. The plugin ships `feature`, `bugfix` and `refactor`. A repo adds its own in `specs/templates/`, and one with a default's name replaces it. Each spec template pairs with an evidence template (`evidence.md`).

Every spec has **Acceptance criteria** and **Amendments**, with Amendments last (only a Closing note may follow it). The template supplies the rest. A markdown spec's frontmatter holds `id`, `title`, `template` and `status`.

Acceptance criteria are one bullet each, numbered, Given/When/Then on one line, and checkable by a test, a command or a screenshot. A criterion proved in another repo's PR carries that repo in brackets. Numbers are never reused or renumbered after freeze.

```
- AC1 Given a check-in due tomorrow, when the daily job runs, then the owner gets one reminder.
- AC2 [billing-api] Given ..., when ..., then ...
```

Amendments are one bullet each, oldest first, always added with `H amend`:

```
- 2026-10-01 AC2: completed means marked done, not dismissed (answered by Parker)
- 2026-10-02 general: root cause is the job reading server time (answered by Parker)
```

## Does it need a spec?

A change that fits in one sentence and one session needs no spec: use plan mode, or just do it. Anything bigger, anything several people or sessions will touch, and anything that crosses an invariant gets one. When unsure, ask.

## Freeze

A human approving the spec freezes it:

| Source | Approved when | Frozen version |
|---|---|---|
| markdown | frontmatter `status:` is an approved value, committed | the commit that made it so |
| github | the issue carries the approval label | the freeze record |
| jira, linear, ado | the issue is in the approval status, or a later one in `approval.also_frozen` | the freeze record |

A **freeze record** is a comment on a tracker spec naming the fingerprint and the approval it covers. `spec-implement` posts it the first time it runs against an approved spec. It counts only for the approval it names.

The **fingerprint** covers everything above the Amendments heading, at the level of wording: tracker formatting noise does not change it, and a changed word, number, operator or checkbox does. Amendments never change it.

Status reports one state. Act on it exactly:

| State | Meaning | What to do |
|---|---|---|
| `not-approved` | Nothing is frozen | Do not build or verify. Say what approves it. |
| `needs-freeze` | Approved, but no freeze record (trackers) or the approval is not committed (markdown) | Tracker: post `record_to_post` (the adapter's Freeze record). Markdown: the human commits the approval. |
| `needs-confirmation` | The body was edited after approval and before the first freeze record | Show `edits_after_approval`. The human re-approves, or confirms the current text: add a `general` amendment containing `confirmed as approved` (the one amendment written without `--frozen`), run Status again, and post `record_to_post`. |
| `frozen` | Unchanged since freeze | Continue. |
| `changed` | The frozen text was edited | Stop and show what changed. An amendment cannot fix this. The human reverts the edit or re-approves, which freezes the edited text. |

Show every `warning` to the human. After freeze, never edit anything above the Amendments heading, not even a typo.

## Consult loop

When the spec is ambiguous, contradicts the code or a `CLAUDE.md` rule, is wrong, or cannot be tested as written, stop and ask one question that cites the criterion. Record the answer as an amendment before continuing, even when it changes nothing.

## Evidence and verdict

The spec is the claim; the PR is the proof.

- **Evidence** is the PR description. `spec-implement` writes it while building and updates it on every push.
- **The verdict** is a new PR comment. `spec-verify` writes it in a fresh session, never the implementing one, re-runs every test and trusts none of the PR's claims. It never edits the evidence or an old verdict. A subagent started by `spec-implement` after the human agrees counts as the fresh session. The implementing conversation still does not write the verdict.
- The helper checks structure only. Whether evidence proves its criterion is the verifier's judgment.
- Only a human grants a waiver. The verifier records it.

`evidence.md` has the formats and commands.

## PR operations

The code repo is on GitHub, whatever the spec source.

| Operation | How |
|---|---|
| **Open** | `gh pr create --title "<title>" --body-file <evidence>`, with the adapter's link line (such as `Closes #6`) above the evidence. |
| **Update the evidence** | `gh pr edit <n> --body-file <evidence>` |
| **Read** | `gh pr view <n> --json body,headRefOid,comments,url`, saved to a file. `.body` is the evidence, `.headRefOid` the head commit. |
| **Post the verdict** | `gh pr comment <n> --body-file <verdict>`. Never `--edit-last`. |

## Confirm before writing outside the repo

A comment, an issue edit, a status move or a PR is visible to the team. Show the exact text and get a yes before each one. One yes covers one write, unless the human says otherwise.

## What outlives the change

At close, most of what the work decided stays on the spec. Only a rule future work must follow is promoted: a repo-wide rule to the root `CLAUDE.md`, a rule for one area to that folder's `CLAUDE.md`, a behavior guarantee to a test. Each cites the spec id and lands through a PR a human reviews.
