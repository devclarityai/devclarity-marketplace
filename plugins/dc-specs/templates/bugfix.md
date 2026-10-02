---
name: bugfix
description: Something is broken and needs to work correctly again
---
## Intent

<!-- Who is affected and how badly. -->

## Scope

<!-- Where the bug lives, as far as is known. -->

## Reproduction

- R1 Given <starting state>, when <action or event>, then <what happens today, the wrong result>.

## Expected behavior

<!-- R1 again, with the correct result. The root cause is recorded later, as a 'general' amendment. -->

## Acceptance criteria

- AC1 Given the fix is in place, when <the R1 reproduction test> runs, then it passes.
- AC2 Given the fix is reverted, when <the R1 reproduction test> runs, then it fails the way R1 describes.
- AC3 Given <an adjacent case that works today>, when <action>, then <it still works>.

## Out of scope

## Amendments

<!-- Added after approval only, one line each: - YYYY-MM-DD ACn: what changed or was clarified (answered by Name) -->
