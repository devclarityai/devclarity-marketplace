---
name: managing-locators
description: Explores features to discover stable locators and fixes broken locators in Playwright tests. Two modes — explore (proactive discovery) and fix (reactive repair) — both using Playwright MCP for live browser interaction.
---

# Managing Locators

Discover or repair Playwright locators using live browser interaction via
Playwright MCP. Determine the mode from the user's request:

- **Explore mode**: User wants to investigate a feature/page for locators
- **Fix mode**: User has a failing test or broken locator to repair

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
  browser window and tell you when they are done. Do not take a snapshot
  or use any other tool until the user says sign-in is done. If no
  browser window is visible (headless or isolated MCP), stop and ask the
  user to set up a headed Playwright MCP.
- Never read or print env files, cookies, local storage, session
  storage, or saved auth state. Do not run commands that print env
  values (`printenv`, `echo $VAR`), and do not open traces, reports, or
  `test-results/` files.
- Use only these Playwright MCP tools: `browser_navigate`,
  `browser_navigate_back`, `browser_snapshot`, `browser_click`,
  `browser_hover`, `browser_type`, `browser_fill_form`,
  `browser_select_option`, `browser_press_key`, `browser_wait_for`,
  `browser_handle_dialog`, `browser_tabs`, `browser_close`, and
  `browser_generate_locator`. Do not use any other MCP tool (for
  example, evaluate, run code, network, console, cookie, storage,
  screenshot, or file tools) or any other browser tool. Do not install
  packages.
- Before you open any project file (test, POM, config, or fixture),
  check it for hardcoded secrets with this match-only search. Files that
  only read `process.env` do not match.

  ```bash
  grep -lEi -e "(password|passwd|secret|token|api[_-]?key|cookie|credential)[a-z_]*[\"']?[[:space:]]*[:=][[:space:]]*[\"'\`][^\"'\`\$]" -e "(bearer|basic)[[:space:]]+[A-Za-z0-9._~+/=-]{8,}" <file>
  ```

  If the file matches, do not open it. Tell the user that it has a
  hardcoded secret and ask them to move it to an env var.
- When you run tests, you may quote test names, pass or fail, and
  assertion or locator error messages. Before you quote output, remove
  any value that looks like a secret. If output shows a credential or
  token, do not repeat it, and tell the user to rotate it.

## Locator priority (both modes)

1. `getByRole` with accessible name
2. `getByLabel`
3. `getByTestId` / data attributes
4. CSS selectors — last resort only

Never use auto-generated classes (e.g., `css-1x2y3z`), positional
selectors (`nth-child`), or exact text matches on dynamic content.

## Explore mode

Read [references/explore.md](references/explore.md) for detailed steps.

1. Navigate to the target page/feature via Playwright MCP
2. Snapshot before and after key interactions (dialogs, dropdowns, forms)
3. Catalog discovered locators organized by element purpose
4. Test reliability — verify each locator across multiple attempts

**-> STOP. Present discovered locators and recommended strategies.
Confirm with the user before documenting or using them.**

## Fix mode

Read [references/fix.md](references/fix.md) for detailed steps.

1. Analyze the error — identify the broken locator and its intent
2. Navigate to the affected page via Playwright MCP and snapshot
3. Find a replacement locator following the priority above
4. Verify the replacement selects exactly one element and works across states

**-> STOP. Present the diagnosis and proposed fix. Confirm with the
user before updating test files.**

5. Update the locator in the test/POM file and run the test to confirm

## Critical rules

- Always use Playwright MCP for live verification — never guess from source code
- Snapshot before AND after interactions to capture state changes
- For dialogs: wait for inner form fields, not the dialog wrapper
- For repeated elements (tables, lists): use parent context + child selector
- Verify new locators work in different states (empty, populated, loading)
- Check downstream effects — other tests may use the same locator

## Anti-patterns

- Typing credentials into login forms
- Reading application source code to guess locators instead of using MCP
- Using auto-generated CSS classes or positional selectors
- Fixing one locator without checking if similar ones are also broken
- Skipping verification across different page states
