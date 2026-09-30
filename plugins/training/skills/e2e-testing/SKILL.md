---
name: e2e-testing
description: Guides the creation of Playwright E2E tests from planning through implementation. Covers test plan creation, data seeding, Page Object Model development, and test writing with human checkpoints at each stage.
---

# Writing E2E Tests

> Before starting, read the project config file `.claude/testing/e2e-config.md` for project-specific patterns, application context, POM rules, assertion conventions. If it does not exist, create it in Step 0 from the `REFERENCE.md` template in this skill's folder.

## Pre-flight checks

Do these before starting any test work:

1. Confirm that the Playwright MCP tools (for example, `browser_navigate`
   and `browser_snapshot`) are available. If they are not, ask the user
   to enable the Playwright MCP server and stop.
2. Confirm that the project's `package.json` lists `@playwright/test`
   (1.59 or higher). If it does not, stop and ask the user to set up
   Playwright. Do not install packages yourself.

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
- Test code reads credentials from environment variables. Refer to them
  by name only.
- Never read, print, or log env files, saved auth state, cookies, or
  tokens. Do not run commands that print env values (`printenv`,
  `echo $VAR`), and do not open traces, reports, or `test-results/` files.
- Use only these Playwright MCP tools: `browser_navigate`,
  `browser_navigate_back`, `browser_snapshot`, `browser_click`,
  `browser_hover`, `browser_type`, `browser_fill_form`,
  `browser_select_option`, `browser_press_key`, `browser_wait_for`,
  `browser_handle_dialog`, `browser_tabs`, `browser_close`, and
  `browser_generate_locator`. Do not use any other MCP tool (for
  example, evaluate, run code, network, console, cookie, storage,
  screenshot, or file tools) or any other browser tool.
- Before you open any project file (config, spec, POM, helper, fixture,
  or setup file), check it for hardcoded secrets with this match-only
  search. Files that only read `process.env` do not match.

  ```bash
  grep -lEi -e "(password|passwd|secret|token|api[_-]?key|cookie|credential)[a-z_]*[\"']?[[:space:]]*[:=][[:space:]]*[\"'\`][^\"'\`\$]" -e "(bearer|basic)[[:space:]]+[A-Za-z0-9._~+/=-]{8,}" <file>
  ```

  If the file matches, do not open it. Tell the user that it has a
  hardcoded secret and ask them to move it to an env var.
- When you run tests, you may quote test names, pass or fail, and
  assertion or locator error messages. Before you quote output, remove
  any value that looks like a secret. If output shows a credential or
  token, do not repeat it, and tell the user to rotate it.
- Tests on auth responses assert only presence or type (for example,
  `expect(typeof body.token).toBe("string")`), never the value, so a
  failed assertion cannot print a token.

---

## Step 0: Project Configuration Q&A (run once per project)

Look for `.claude/testing/e2e-config.md` in the project.

- If it exists and has no placeholder of the form `[UPPER_SNAKE_CASE]`, skip this step.
- If it does not exist, copy `REFERENCE.md` from this skill's folder to that path. Then enter **Q&A mode** before doing anything else.
- If it exists but placeholders remain, enter **Q&A mode** for the remaining placeholders.

**Before Q&A: offer to explore existing tests first.**

Ask the user a single yes/no question:

> "I can explore the existing test directory and `playwright.config.ts` first to pre-fill answers from what already exists, then only ask you about anything I can't determine. Want me to do that, or would you rather answer every question manually?"

- If **yes** (recommended): locate the Playwright config and E2E test root (try common paths: `playwright.config.ts`, `e2e/`, `tests/e2e/`, `playwright/`, `tests/`). Read the config, a sampling of existing specs, any `global-setup` / `auth.setup.ts` files, fixtures, POMs, and `package.json` scripts. Do not open `.env` files or saved auth state (for example, `.auth/`). When a setup file or fixture holds credentials, record only the env var names; never copy credential values. Build a draft answer for each placeholder below. Then run Q&A in **review mode**: present each pre-filled answer and ask the user to confirm, correct, or fill in `TBD`. Skip questions that are fully answered and confirmed.
- If **no**: run Q&A in **manual mode** using the rules below.

**Q&A mode rules:**

1. Ask the questions below **one at a time**, in order. Wait for the user's answer before asking the next.
2. If the user says "skip", "n/a", or "I don't know", record `TBD` for that placeholder and move on.
3. Do NOT guess values by reading the application source. Only fill in what the user provides, OR what you discovered from the existing test directory in the explore step above (and only after the user confirms it).
4. After all questions are answered, show the user a summary of the values and get confirmation.
5. Then write the values into `.claude/testing/e2e-config.md`, replacing every matching `[PLACEHOLDER]` token. Suggest that the user commits the file with the tests.

**Questions to ask (each maps to placeholders in the config file):**

1. **App name and one-line description?** -> `[APP_NAME]`, `[APP_DESCRIPTION]`
2. **Base URL for local dev, and the env var that sets it?** -> `[BASE_URL]`, `[BASE_URL_ENV_VAR]`
3. **Path to `playwright.config.ts` and the test files glob?** -> `[PLAYWRIGHT_CONFIG_PATH]`, `[TESTS_GLOB]`
4. **Tech stack: framework + version, database, CSS approach, SPA/reactivity layer, API/backend?** -> `[FRAMEWORK_AND_VERSION]`, `[DATABASE]`, `[CSS_APPROACH]`, `[SPA_OR_REACTIVITY_LAYER]`, `[API_OR_BACKEND_TECH]`
5. **Authentication mechanism?** (session cookie, JWT, OAuth, SAML/SSO, magic link, basic auth, other) -> `[AUTH_MECHANISM_DESCRIPTION]`
6. **Sign in and sign out endpoints / methods?** -> `[SIGN_IN_METHOD_AND_ENDPOINT]`, `[SIGN_OUT_METHOD_AND_ENDPOINT]`
7. **Names of the env vars that hold test credentials?** (names only, never values) -> `[TEST_CREDENTIALS_LOCATION]`
8. **Any auth rate limits, lockouts, MFA, or SSO behavior tests must work around?** -> `[AUTH_RATE_LIMITS_OR_NONE]`, `[MFA_SSO_NOTES_OR_NONE]`
9. **Auth setup strategy in Playwright?** (setup project, global setup file, saved `storageState`, per-test login) -> `[AUTH_SETUP_STRATEGY]`
10. **Three to five key routes** (login, post-auth landing, primary resource pages) -> `[ROUTE_LOGIN]`, `[ROUTE_HOME]`, `[ROUTE_RESOURCE]`, `[PURPOSE]`
11. **Framework quirks that affect tests?** (SPA navigation timing, CSRF tokens, HTML5 validation, async hydration) -> `[FRAMEWORK_QUIRKS_THAT_AFFECT_TESTS]`, `[HOW_TO_WAIT_AFTER_NAVIGATION]`, `[FORM_SUBMISSION_QUIRKS_CSRF_VALIDATION]`, `[HOW_DOM_UPDATES_AFFECT_TIMING]`
12. **npm/pnpm/yarn scripts for running tests** (headless, headed, ui, debug, report) -> `[CMD_RUN_TESTS]`, `[CMD_RUN_HEADED]`, `[CMD_RUN_UI]`, `[CMD_RUN_DEBUG]`, `[CMD_OPEN_REPORT]`
13. **E2E folder root path?** (e.g. `e2e`, `tests/e2e`, `playwright`) -> `[E2E_ROOT]`
14. **Anything else future tests should know?** (feature flags, seed scripts, env toggles, known flaky areas, CI specifics) -> `[ANYTHING_ELSE_FUTURE_TESTS_SHOULD_KNOW]`

After saving, continue with the workflow below.

---

Create Playwright end-to-end tests for a feature or workflow, from plan
through passing tests. Follow this workflow step by step. **Stop after
each step and check in with the user before proceeding.**

In the steps below, a placeholder such as `[E2E_ROOT]` means the value
saved in `.claude/testing/e2e-config.md`.

## Workflow checklist

```
E2E Test Progress:
- [ ] Step 0: Project Configuration Q&A (skip if the config file has no placeholders)
- [ ] Step 1: Create the test plan
- [ ] Step 2: Seed test data (skip if not needed)
- [ ] Step 3: Create/update Page Object Models
- [ ] Step 4: Write the tests
```

## Step 1: Create the test plan

Read and analyze the feature or workflow to be tested. Identify key
interaction points, required test data, page objects, and test scenarios.

If the user provides specific test scenarios, use ONLY those. Do not
invent additional scenarios.

Present the plan in chat using this structure:

    # Test Plan for [Feature]
    [Overview]

    ## Setup Required
    - [Entity]: [Quantity], [Attributes], [Relationships]

    ## POM Modifications & Creations
    - [Page Object]: [Changes or new methods needed]

    ## Test Cases to Implement
    - **[Test Case]**: [Description]
      - Steps: [Numbered steps]
      - Expected Result: [Outcome]

Include exact data requirements — quantities, attributes, relationships.
Use timestamps in test identifiers to avoid conflicts. Do NOT write the
plan to a file. Document assumptions about existing system state.

**-> STOP. Present the plan. Confirm scope, test cases, and data
requirements with the user before proceeding.**

## Step 2: Seed test data

_Skip if the test plan requires no new data. Tell the user immediately
and move to Step 3._

1. Read and review the existing API helper methods and data factories
   under `[E2E_ROOT]/lib/helpers` and `[E2E_ROOT]/lib/datafactory` (or
   the folders the project uses).
2. If the needed entity type isn't supported, extend the data factory helpers
   with a TypeScript interface and creation method.
3. Create a test spec file that seeds the data with meaningful,
   varied values. Log only the IDs and names of what was created, never
   credentials or tokens.
4. Run the seed to verify data creation.

**-> STOP. Confirm data was created successfully or that this step was
skipped. Share a summary of what was seeded.**

## Step 3: Create/update Page Object Models

1. Read existing POM files to identify what can be reused or extended.
   Review current locator strategies.
2. For each page/component in the plan, create or update a POM class.
3. Use Playwright MCP to validate locators — open the page with
   `browser_navigate`, take a `browser_snapshot`, and verify elements
   exist. Use `browser_generate_locator` if it is available (it needs
   `--caps=testing`); if not, build the locator from the role and
   accessible name in the snapshot. If locators need discovery, explore
   the feature: snapshot before and after key interactions, test locator
   reliability across multiple attempts.
4. Document assumptions about page state or prerequisites.

Locator priority: `getByRole` > `getByLabel` > `getByTestId` > CSS
(last resort). Never use auto-generated classes (e.g., `css-1x2y3z`).

Follow the Page Object Pattern in the config file for the exact POM template and rules.

**-> STOP. Present the POM classes. Review locator strategies and
method signatures with the user.**

## Step 4: Write the tests

1. Read the test plan to identify the specific test case to implement.
2. Read the relevant POMs to understand available methods.
3. Write the test. Do NOT reference application source code to generate
   locators — use only what the POMs provide.
4. Run the tests to confirm they pass.

**-> STOP. Share test results. Confirm the test passes and covers the
intended scenario.**

## Critical rules

- Never put credentials into the conversation; the user signs in, and code uses env vars
- Run Step 0 Q&A before any test work if the config file is missing or still has `[PLACEHOLDER]` tokens
- Plan stays in chat, never written to a file
- If user provides test scenarios, use ONLY those, no extras
- Timestamps in test identifiers for isolation
- Validate locators via Playwright MCP, not by reading source code
- Run tests after seeding data AND after writing tests
- Set realistic scope, avoid feature creep

## Anti-patterns

- Typing credentials into login forms, or hardcoding them in tests
- Generating locators by reading application source code
- Using auto-generated CSS classes as selectors
- Using positional selectors (nth-child) or exact text matches
- Putting business logic in Page Object Models
- Writing the test plan to a file instead of keeping it in chat
- Inventing test scenarios when the user provided specific ones
