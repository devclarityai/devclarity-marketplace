---
name: bugfix
version: 2
description: Evidence for a bugfix spec - one row per criterion, and the reproduction test failing before the fix and passing after
---
## Criteria

| Criterion | Result | Test | Why it proves the Then clause | Re-run |
|---|---|---|---|---|
| <each criterion> | <one of: pass, fail, not verified> | `<test name>` in `<path>` | <the assertion that proves the then clause, and why> | `<command>` |

## Visual evidence

<!-- One row per slide in the spec's mockups section; left out when there are none. -->

| Slide | Approved mockup | Rendered still | Keys, rung and width | Criteria |
|---|---|---|---|---|
| <each slide> | <slide mockup> | <the rendered still> | <slide detail> | <the criteria it shows> |

## Reproduction

<!-- Only when the spec has a Reproduction section. The same test failing on the parent commit (or with the fix reverted) and passing after, and a different test for the adjacent behavior. -->

| Step | Test | Ran at | Result |
|---|---|---|---|
| Before the fix | `<test name>` in `<path>` | <parent commit, or the fix reverted> | fail |
| After the fix | `<test name>` in `<path>` | <head commit> | pass |
| Adjacent behavior | `<test name>` in `<path>` | <head commit> | pass |

## Constraints

<!-- Only when the spec has a Constraints section. How each was kept, and how you checked. -->

- <constraint>: <how it was kept>

## Deviations from the Technical approach

<!-- Only when the spec has a Technical approach section. Every place the diff departs from it, or "None". -->

- <decision>: <what was built instead, and why>

## Outside the spec's scope

<!-- Every changed file no criterion needs, or "None". -->

- <file>: <why it changed>
