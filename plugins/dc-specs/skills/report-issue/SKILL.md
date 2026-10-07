---
name: report-issue
description: Use when someone hits a problem with dc-specs itself or wants it to do something new - "report a dc-specs bug", "file an issue for dc-specs", "dc-specs did X instead of Y", "can dc-specs do X", "report issue". Files a dc-specs bug or feature request as a GitHub issue on devclarityai/devclarity-marketplace, after checking for a duplicate, with the versions filled in and nothing from the reporter's own repo. Not for bugs in the reporter's code or in other plugins.
---

# report-issue

Turn what the reporter said about dc-specs into an issue a maintainer can act on, in two or three exchanges.

Read the Helper section of `${CLAUDE_PLUGIN_ROOT}/references/framework.md` for `H`. This skill does not need specs/config.yaml and runs in any repo. The issue is a report, not a spec: a maintainer runs `spec-author` on it later.

## 1. Triage

From what the reporter already said, decide whether it is a bug (dc-specs did something wrong) or a feature request (dc-specs does not do something they want), and pick two to four search keywords from their words: the skill or command, and the symptom.

If it is about another plugin, such as training, or about the reporter's own code, say that `report-issue` files dc-specs issues only, create nothing, and stop.

## 2. Dedupe

Search open and closed issues at least twice, with different phrasings, then read the plausible matches with `gh issue view`:

```
gh issue list --repo devclarityai/devclarity-marketplace --state all --search "<keywords>" --limit 20 --json number,title,state
```

- A match the report adds nothing to: give the reporter its number and state, and stop. Write nothing.
- A match the report adds something new to (a new repro, another OS or source, a regression of a closed issue): draft a comment on it instead of a new issue, holding only what is new.
- No match: draft a new issue.

When `gh` cannot search, say so and draft a new issue.

## 3. Draft

Run `H report-env` and put its output, as a short list, under a `## Environment` heading. Fill the rest from what the reporter said:

- Bug: What happens, Expected, Repro, and the failing command and its error text in a code block.
- Feature request: What they want, and Why.

Ask only for gaps the draft cannot fill or guess, in one batch. Mark a guess as a guess and an unknown as unknown; never invent a repro.

## 4. Keep client data out

Reporters are usually in a client's repo. The draft holds only the environment, the dc-specs skill or command involved, the error text, and what the reporter wrote. It never holds spec text, file paths, repo or org names, tracker project keys, URLs or config values, unless the reporter typed it into the report themselves.

Replace any of these in error text with a placeholder: `<path>`, `<repo>`, `<org>`, `<key>`, `<url>`, `<spec text>`. Then say in the draft what was redacted, in one line under the error.

## 5. Title and label

The title is `dc-specs <version>: ` followed by a plain statement of the problem or request, with `<version>` the `dc_specs` from `H report-env`. The label is `bug` for a bug or `enhancement` for a feature request, and no other label: never `spec:approved` or a priority.

## 6. Confirm

Show the reporter the full title, label and body (or the comment), say which parts are guesses, and ask them to fix anything wrong. Until the reporter says yes, create no issue and post no comment.

## 7. File

Write the body to a temp file, then:

```
gh issue create --repo devclarityai/devclarity-marketplace --title "<title>" --label <bug|enhancement> --body-file <tmp>
```

For a match, `gh issue comment <n> --repo devclarityai/devclarity-marketplace --body-file <tmp>` instead. Read it back with `gh issue view <n> --repo devclarityai/devclarity-marketplace --json url` and give the reporter the URL it returns.

## 8. Fallback

When gh is missing, not logged in, or the create or comment fails, run `H report-link --title "<title>" --label <bug|enhancement> --body-file <tmp>` and give the reporter its `url` to open and submit. When `body_in_link` is false, the link carries the title and label only: show `body` for the reporter to paste. For a comment on a match, give the issue's URL and the comment text to paste.
