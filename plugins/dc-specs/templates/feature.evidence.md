---
name: feature
version: 2
description: Evidence for a feature spec - one row per criterion, and the rendered still beside every approved mockup slide
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

## Constraints

<!-- Only when the spec has a Constraints section. How each was kept, and how you checked. -->

- <constraint>: <how it was kept>

## Deviations from the Technical approach

<!-- Only when the spec has a Technical approach section. Every place the diff departs from it, or "None". -->

- <decision>: <what was built instead, and why>

## Outside the spec's scope

<!-- Every changed file no criterion needs, or "None". -->

- <file>: <why it changed>
