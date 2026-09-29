---
name: e2e-testing
description: Guides the creation of Playwright E2E tests from planning through implementation. Covers test plan creation, data seeding, Page Object Model development, and test writing with human checkpoints at each stage.
---

# Writing E2E Tests

Create Playwright end-to-end tests for a feature or workflow, from plan
through passing tests. Follow this workflow step by step. **Stop after
each step and check in with the user before proceeding.**

Before starting, read `REFERENCE.md` in this skill's folder for the
team's project conventions.

## Pre-flight check

This skill uses Playwright MCP for live browser checks. Confirm that
its tools (for example, `browser_navigate` and `browser_snapshot`) are
available. If they are not, ask the user to enable the Playwright MCP
server and stop.

## Credentials

Never put passwords, tokens, or session cookies into the conversation.

- Do not ask the user for credentials, and never type them into a form.
  If the user pastes one, do not use or repeat it, and tell them to
  rotate it.
- If a page needs a login, ask the user to sign in in the Playwright MCP
  browser window and tell you when they are done.
- Test code reads credentials from environment variables. Refer to them
  by name only.
- Never read, print, or log env files, saved auth state, cookies, or
  tokens.

## Workflow checklist

```
E2E Test Progress:
- [ ] Step 1: Create the test plan
- [ ] Step 2: Seed test data (skip if not needed)
- [ ] Step 3: Create/update Page Object Models
- [ ] Step 4: Write the tests
```

## Step 1: Create the test plan

Analyze the feature or workflow. Identify the key interactions, test
data, page objects, and scenarios. If the user provides specific
scenarios, use ONLY those. Present the plan in chat, not in a file:

    # Test Plan for [Feature]
    ## Setup Required
    - [Entity]: [Quantity], [Attributes], [Relationships]
    ## Page Objects
    - [Page Object]: [New or changed locators and methods]
    ## Test Cases
    - **[Test case]**: [Steps] -> [Expected result]

Use timestamps in test identifiers to avoid conflicts.

**-> STOP. Present the plan. Confirm scope, test cases, and data with the user.**

## Step 2: Seed test data

_Skip if the plan needs no new data. Tell the user and go to Step 3._

1. Read the existing data factories and helpers.
2. Extend them if the needed entity type is not supported.
3. Create and run a seed that makes the data. Log only what was created,
   never credentials or tokens.

**-> STOP. Share a summary of what was seeded, or confirm the step was skipped.**

## Step 3: Create/update Page Object Models

1. Read existing Page Object Models (POMs) to find what can be reused.
2. For each page in the plan, create or update a POM. Follow the POM
   template in `REFERENCE.md`.
3. Validate each locator with Playwright MCP: open the page with
   `browser_navigate`, take a `browser_snapshot`, and confirm the
   element exists. Take a snapshot before and after key interactions.

Locator priority: `getByRole` > `getByLabel` > `getByTestId` > CSS
(last resort). Never use auto-generated classes or positional selectors.

**-> STOP. Present the POMs. Review locators and method signatures with the user.**

## Step 4: Write the tests

1. Write each test using only the locators and methods in the POMs.
2. Use web-first assertions (`await expect(locator).toBeVisible()`).
3. Run the tests and confirm they pass.

**-> STOP. Share the test results. Confirm the tests cover the intended scenarios.**

## Anti-patterns

- Typing credentials into login forms, or hardcoding them in tests
- Building locators by reading application source code instead of the live page
- Auto-generated CSS classes, positional selectors, or exact text on dynamic content
- Business logic in POMs
- Inventing scenarios when the user provided specific ones
