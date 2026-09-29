---
name: managing-locators
description: Explores features to discover stable locators and fixes broken locators in Playwright tests. Two modes — explore (proactive discovery) and fix (reactive repair) — both using Playwright MCP for live browser interaction.
---

# Managing Locators

Discover or repair Playwright locators using a live browser through
Playwright MCP. Determine the mode from the user's request:

- **Explore mode**: The user wants locators for a feature or page
- **Fix mode**: The user has a failing test or broken locator

Before starting, read `REFERENCE.md` in this skill's folder for the
team's locator conventions.

## Pre-flight check

Confirm that the Playwright MCP tools (for example, `browser_navigate`
and `browser_snapshot`) are available. If they are not, ask the user to
enable the Playwright MCP server and stop.

## Credentials

Never put passwords, tokens, or session cookies into the conversation.

- Do not ask the user for credentials, and never type them into a form.
  If the user pastes one, do not use or repeat it, and tell them to
  rotate it.
- If a page needs a login, ask the user to sign in in the Playwright MCP
  browser window and tell you when they are done.
- Never read or print cookies, local storage, session storage, or saved
  auth state.

## Locator priority (both modes)

1. `getByRole` with accessible name
2. `getByLabel`
3. `getByTestId`
4. CSS selectors — last resort only

Never use auto-generated classes, positional selectors (`nth-child`), or
exact text on dynamic content.

To get a locator, use `browser_generate_locator` if it is available.
If not, build it from the role and accessible name in the snapshot.

## Explore mode

1. Open the page with `browser_navigate` and take a `browser_snapshot`.
2. Interact to reveal hidden elements (dialogs, dropdowns, forms) with
   `browser_click` or `browser_type`. Use test data only. Take a snapshot
   after each interaction.
3. Catalog the locators by element purpose. Note any wait conditions.
4. Repeat key interactions 2-3 times to confirm each locator is stable
   and selects exactly one element.

Present the findings:

    ## [Feature] Locators
    - [Element]: `[locator]`
      Wait condition: [if any]

**-> STOP. Present the locators. Confirm with the user before using them.**

## Fix mode

1. Read the failing test, its error, and the POM that holds the locator.
2. Open the failing page with `browser_navigate` and take a snapshot.
3. Classify the root cause before writing any code:

   | Category | Symptom | Fix direction |
   |---|---|---|
   | Stale locator | Element not found, or timeout | Replace the locator from the live page |
   | Text change | `toHaveText` fails with a new value | Update the expected value, or use a regex |
   | Timing | Intermittent failure | Add a web-first assertion before the interaction |
   | Session | Redirected to the login page | Ask the user to check the test's auth setup |
   | Test data | Record not found, or wrong count | Fix the test setup |
   | App change | Feature behavior changed | Update the test, or flag a regression |

**-> STOP. State the root cause and the file and line to change. Confirm with the user before writing code.**

4. Find a replacement locator that follows the priority above.
5. Update the test or POM. Check nearby locators for the same problem.
6. Run the failing test, then related tests that use the same locator.

## Anti-patterns

- Typing credentials into login forms
- Guessing locators from application source code instead of the live page
- Fixing one locator without checking similar ones
- Classifying the root cause after writing code
