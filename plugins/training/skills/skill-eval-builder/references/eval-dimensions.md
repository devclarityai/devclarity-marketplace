# Eval dimensions — the menu

Pick the few that fit the skill. **Invocation + Validation are the default two**;
add the rest only when they earn their place. A workflow/model-invoked skill leans
invocation + duration; a capability skill (produces an artifact) leans validation.

| Dimension | Measures | How `run.py` checks it | Add it when |
| :-------- | :------- | :--------------------- | :---------- |
| **Invocation** (Fires?) | Triggers on should-fire prompts; stays quiet otherwise | Per case: `expect: fire\|quiet` + `fired_when:` side-effect check | Always — over/under-firing is the #1 skill bug |
| **Validation** (Valid?) | Output is well-formed / correct shape | `validate:` shell cmd (file test, schema, regex) on `$EVAL_OUTPUT` | Always — especially skills that produce an artifact |
| **Duration** | Within a time budget | wall-clock vs `budget_s:` | Speed matters, or long agentic workflows |
| **Completeness** | Did every required step happen | Several `fired_when`-style checks, one per required side-effect | Multi-step workflows where a skipped step is silent |
| **Autonomy** | Finished without hand-holding | Not automated — record interventions needed from a real run | Agentic skills meant to run unattended |
| **Consistency** | Same input → same *shape* across N runs | Run a case N times; compare validation pass-rate | Variance is a risk (flaky output shape) |
| **Cost** | Tokens / $ per run | Not automated — read from the run's usage and record | The skill is expensive to run |

## Choosing budgets

A budget is the line between pass and fail — set it from a real baseline, not a
guess. Run the case once, see it takes ~40s, set `budget_s: 60` (headroom for
variance). For validation, "good" is the cheapest check that would catch a real
regression (the file exists AND has the expected top-level shape), not a diff of
exact bytes.

## What NOT to eval here

If a plain deterministic script already guarantees a property (byte-identical
output every run), you don't need an eval for it — a unit check on the script is
enough. Evals are for the model-driven behavior that scripts can't pin down.
