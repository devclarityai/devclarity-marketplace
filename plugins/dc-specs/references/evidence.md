# Evidence and verdict

The PR description is the evidence. A PR comment is the verdict. Both are rendered from a template and checked against it and the spec. The shared rules are in `framework.md` (Evidence and verdict).

## Templates

Each spec template pairs with `<name>.evidence.md`, the plugin's in `templates/` or a repo's own in `specs/templates/`. A spec template with no evidence template of its own uses `feature`. The verdict's template is the plugin's `templates/verdict.md`.

An evidence template has `name`, `version` and `description` in its frontmatter. Bump `version` by hand on every change: a verdict for an older version is stale.

Each `## ` section of a template becomes a section of the document:

- A table row `| <each criterion> | ...` becomes one row per criterion, in spec order. `| <each slide> | ...` becomes one row per slide in the spec's mockups section, and the section is left out when there are none.
- A row whose first cell is text is a fixed row. Its text cells must stay as written, such as the `fail` in Reproduction's Before the fix row.
- A cell `<one of: a, b, c>` must hold one of those values.
- Any other `<...>` is a placeholder to fill. No cell may be blank or `-`, except in an `other repo` row.
- A section whose comment says `Only when the spec has a X section` appears only when the spec has one.
- Any other section is free text, copied as written, and must be filled or say `None`.

## Evidence

```
H evidence render --spec <spec> --frozen <fingerprint> [--id "#6"] [--url <link>] [--repo-tag <repo>] [--template <name>] [--merge <old description>] --out <file>
H evidence check --spec <spec> --evidence <file> --frozen <fingerprint> [--repo-tag <repo>]
```

`render` picks the markdown spec's `template`, or for a tracker spec the template whose sections it shares most. It writes the header and every row it can, and prefills `other repo` for a criterion tagged with another repo than `--repo-tag`. `--merge` carries an earlier description's filled rows (by criterion, slide or step) and sections across, so an amendment or a new template version needs no copying by hand.

```markdown
## Spec evidence: #6 Plan a whole day at once in the plan view

**Spec:** https://github.com/acme/app/issues/6 · frozen at fingerprint `5cf9f3fc5c3e` · 1 amendment
**Evidence template:** `feature` v2
**CI:** https://github.com/acme/app/actions/runs/36591471047

### Criteria

| Criterion | Result | Test | Why it proves the Then clause | Re-run |
|---|---|---|---|---|
| AC1 | pass | `TestPOpensBothPanes` in `tui/plan_day_test.go` | asserts both pane headers render | `go test ./tui -run TestPOpensBothPanes` |
| AC2 | not verified | none | needs a DST fixture the suite does not have | none |
| AC3 [billing-api] | other repo | - | - | - |
```

`check` checks the header pins the spec's fingerprint, amendment count and the evidence template's current version, that there is a CI line, and the template's rules above. A criterion without a passing test is `not verified`, never `pass`.

## Verdict

```
H verdict render --spec <spec> --evidence <description> --head <headRefOid> --frozen <fingerprint> --out <file>
H verdict check --spec <spec> --verdict <file> --evidence <description> --head <headRefOid> --frozen <fingerprint> [--repo-tag <repo>]
H verdict latest --comments <saved PR JSON> --head <headRefOid> [--spec <spec>] [--evidence <description>]
```

```markdown
## Spec verdict: #6 Plan a whole day at once in the plan view

**Head commit:** `b0109b572f5cc67680e91a28d0ab9eb95db98d71`
**Spec:** https://github.com/acme/app/issues/6 · frozen at fingerprint `5cf9f3fc5c3e` · 1 amendment
**Evidence template:** `feature` v2
**Result:** disputed · 1 confirmed · 1 disputed · 0 weak · 0 unverifiable · 1 waived

### Criteria

| Criterion | Verdict | Detail |
|---|---|---|
| AC1 | confirmed | returned early from the `p` handler; the test failed |
| AC2 | disputed | `k` at the first item wraps to the last; the Then clause says it stays |
| AC3 | waived | needs a failing Graph fixture |

### Waivers

- AC3: waived by Parker Kain until 2026-10-15 - the fixture writer cannot fail mid-write yet
```

| Verdict | Meaning |
|---|---|
| `confirmed` | The claimed pass holds: the test proves the Then clause, passed when re-run, and failed with the behavior broken. |
| `weak` | The test passes, but would still pass with the behavior broken, or misses part of the Then clause. |
| `disputed` | The claim is wrong: the test fails, the behavior contradicts the criterion, or the test does not test what the row says. |
| `unverifiable` | The evidence cannot be re-run here, or there is none. |
| `waived` | A named human accepted the row, with a reason and an expiry, on one line under `### Waivers`. |
| `other repo` | Tagged for another repo, whose own PR proves it. |

A spec that is approved but has no freeze record (`needs-freeze`) can still be verified when a human waives the freeze check. Only `spec-verify` writes that line, under `### Waivers`, and it needs no criterion row:

```markdown
- freeze: waived by Parker Kain until 2026-10-20 - az cannot post the freeze record on Windows
```

The Result is the worst row: `disputed`, then `weak`, then `unverifiable`, then `confirmed`. Waived and other repo rows count as confirmed. `check` prints the exact `result_line` to use, and also checks the head commit, that only a claimed pass is confirmed, and that each waiver's date has not passed.

A verdict is pinned to the head commit, the spec's fingerprint and amendment count, and the evidence template's version. It is stale once any of them changes, so any push makes it stale. `latest` finds the newest verdict that is not stale, and says why each other one is.
