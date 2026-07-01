# Eval anatomy — what a simple eval looks like

An eval is a **folder, not a framework**. `scaffold-evals.py` drops it next to the
target skill:

```
<their-skill>/evals/
├── cases.md      # the real cases + what "good" means for each
├── run.py        # runs them, prints the scorecard (a copy of run-evals.py)
└── results.md    # the last scorecard
```

Run it with `python run.py` (add `--dry-run` to check the cases file without
spending tokens).

## cases.md format

Preamble, then one `## Case:` block per case. Fields are `key: value` lines:

```markdown
## Case: add tests for a module
prompt: add unit tests for src/parser.ts
expect: fire
fired_when: test -f src/parser.test.ts
validate: grep -q "describe(" src/parser.test.ts
budget_s: 60

## Case: rename a variable (shouldn't fire)
prompt: rename `foo` to `bar` in utils.ts
expect: quiet
```

| Field | Meaning |
| :---- | :------ |
| `prompt` | (required) the user message sent to `claude -p` |
| `expect` | `fire` or `quiet` (default `fire`) — should the skill activate? |
| `fired_when` | shell cmd; exit 0 ⇒ skill fired. `$EVAL_OUTPUT` = captured output file. Omit to fall back to grepping the skill name (weaker). |
| `validate` | shell cmd; exit 0 ⇒ output valid (fire cases only) |
| `budget_s` | duration budget, seconds |

## The observable side-effect pattern

Firing is model-side, so detect it by something you can *observe*, in priority
order: (1) a file/artifact the skill produces (`test -f ...`), (2) a known marker
line the skill prints, (3) as a last resort, a grep of the output for the skill's
name. Prefer 1 — it is the least brittle.

## The scorecard

Dimensions as columns, cases as rows — the one thing people actually read:

```
┌───────────────────────────────┬──────────┬────────┬────────────────────┐
│ Case                          │ Fires?   │ Valid? │ Duration vs budget │
├───────────────────────────────┼──────────┼────────┼────────────────────┤
│ "add tests for X"             │ ✅       │ ✅     │ 40s / 60s ✅       │
│ "refactor Y" (shouldn't fire) │ ✅ quiet │ –      │ –                  │
└───────────────────────────────┴──────────┴────────┴────────────────────┘
```

## Anti-patterns

- **Building a harness.** One script over a folder of cases — not a framework,
  runner registry, or assertion DSL. If it grows past ~a screen, cut scope.
- **Faking determinism.** A skill eval runs a model; runs vary. Measure and show
  the variance (re-run, watch the pass-rate) — don't pretend it's byte-stable.
- **Fifty synthetic cases.** 3–5 *real* prompts beat a pile of invented ones.
- **No quiet case.** Always include a should-NOT-fire prompt — over-firing is the
  most common skill defect and the easiest to miss.
- **Brittle prose matching.** Validate the artifact or its shape, not an exact
  sentence the model happened to write.
- **Evaling what a script guarantees.** If a deterministic script already pins a
  property, unit-check the script instead.

## Classification gates

Some skills open with a **classification step** — route the input (feature vs bug),
or decide whether to continue at all. Test that gate on its own with a labeled list:
`scaffold-evals.py --classify` writes `classify-cases.md`, `classify.py`, and
`classify-results.md`.

`classify-cases.md` format — a header plus one `## <label>` block per example
(heading = the correct label, body = the item):

```markdown
labels: feature, bug, question
classify: A request for new functionality is a feature; a report of broken
  behavior is a bug; a how-do-I ask is a question.

## feature
Add a dark mode toggle to the settings page

## bug
Login button does nothing on Safari 17
```

- **Get real labels for free.** Pull recent items from your tracker and reuse their
  existing labels as ground truth — e.g. `gh issue list --limit 10 --json title,body,labels`,
  or a Jira/MCP query. That's the fastest way to a real, honest test set.
- **`classify:` is the gate's own instruction.** Paste the wording the skill uses to
  decide, so you're testing the gate, not a paraphrase.
- **The scorecard is accuracy + confusion** (e.g. `bug→feature x2`) — the confusion
  line tells you *which* way it's wrong, which is where the fix goes.
- Models sometimes think out loud and self-correct ("feature… wait, it's a bug");
  the runner takes their **final** answer, so let them reason if they want.
