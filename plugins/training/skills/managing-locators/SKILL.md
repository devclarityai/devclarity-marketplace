---
name: managing-locators
description: Explores features to discover stable locators and fixes broken locators in Playwright tests. Two modes — explore (proactive discovery) and fix (reactive repair) — both using playwright-cli for live browser interaction.
---

# Managing Locators

Discover or repair Playwright locators using live browser interaction via
playwright-cli. Determine the mode from the user's request:

- **Explore mode**: User wants to investigate a feature/page for locators
- **Fix mode**: User has a failing test or broken locator to repair

## Target environment

Run playwright-cli against a local, dev, or test environment only. Never
point it at production.

Before the first `goto`, confirm the base URL with the user. If the URL
looks like production, or you are not sure, stop and ask.

## Pre-flight checks

Run these before starting any work:

```bash
# 1. Verify playwright-cli 0.1.21 is installed
playwright-cli --version

# 2. Verify Playwright version is 1.59 or higher
npx playwright --version
```

## Guided setup

Do not install packages yourself. If `playwright-cli` is not found, or
its version is not 0.1.21, stop and give the user these commands to run
once:

```bash
# Install the pinned playwright-cli version
npm install -g @playwright/cli@0.1.21

# Add Playwright's own skill files for the CLI
playwright-cli install --skills
```

Tell the user they can type `! <command>` in Claude Code to run each
command in this session. Wait for the user to confirm, then run the
pre-flight checks again.

## Locator priority (both modes)

1. `getByRole` with accessible name
2. `getByLabel`
3. `getByTestId` data attributes
4. CSS selectors — last resort only

Never use auto-generated classes (e.g., `css-1x2y3z`), positional
selectors (`nth-child`), or exact text matches on dynamic content.

## Explore mode

call View on `./references/explore.md`

1. Navigate to the target page/feature via playwright-cli
2. Snapshot before and after key interactions (dialogs, dropdowns, forms)
3. Catalog discovered locators organized by element purpose
4. Test reliability — verify each locator across multiple attempts

**-> STOP. Present discovered locators and recommended strategies. Confirm with the user before documenting or using them.**

## Fix mode

call View on `./references/fix.md`

1. Analyze the error — identify the broken locator and its intent
2. Navigate to the affected page via playwright-cli and snapshot
3. Classify the root cause before writing any code
4. Find a replacement locator following the priority above
5. Verify the replacement selects exactly one element and works across states

**-> STOP. Present the root cause classification and proposed fix. Confirm with the user before updating test files.**

6. Update the locator in the test/POM file and run the test to confirm

## Critical rules

- Never target production — confirm the base URL with the user first
- Always use playwright-cli for live verification — never guess from source code
- Snapshot before AND after interactions to capture state changes
- For dialogs: wait for inner form fields, not the dialog wrapper
- For repeated elements (tables, lists): use parent context + child selector
- Verify new locators work in different states (empty, populated, loading)
- Check downstream effects — other tests may use the same locator

## Anti-patterns

- Reading application source code to guess locators instead of using playwright-cli
- Using auto-generated CSS classes or positional selectors
- Fixing one locator without checking if similar ones are also broken
- Skipping verification across different page states
- Classifying root cause after writing code instead of before
