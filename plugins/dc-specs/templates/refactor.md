---
name: refactor
description: The structure of the code changes and its behavior does not
---
## Intent

<!-- Why the structure has to change now. -->

## Scope

<!-- Modules, tables and interfaces this moves or reshapes. -->

## Behavior preserved

<!-- "No user-visible change", and the test suites that define that. -->

## Invariants at risk

<!-- Which CLAUDE.md rules the refactor passes near. Delete if none. -->

## Migration plan

<!-- Steps, data backfill and rollback. Delete if there is no data or rollout change. -->

## Acceptance criteria

- AC1 Given the existing <suite name> suite, when it runs against the refactored code, then every test passes and no test file changed.
- AC2 Given a caller of <public interface>, when it calls the interface as before, then it gets the same result.

## Out of scope

## Amendments

<!-- Added after approval only, one line each: - YYYY-MM-DD ACn: what changed or was clarified (answered by Name) -->
