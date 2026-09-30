# E2E Testing Reference

Template for the project config file. Step 0 of the e2e-testing skill copies it to `.claude/testing/e2e-config.md` in the project and fills it in.

> The config is complete when no bracketed ALL-CAPS placeholders remain. Never write credential values in this file; use env var names only.

---

## Application Under Test

**[APP_NAME]** — [APP_DESCRIPTION]

- **Base URL**: `[BASE_URL]` (set via `[BASE_URL_ENV_VAR]` or config file)
- **Config file**: `[PLAYWRIGHT_CONFIG_PATH]`
- **Tests location**: `[TESTS_GLOB]`

---

## Tech Stack

- **Framework / language**: [FRAMEWORK_AND_VERSION]
- **Database**: [DATABASE]
- **Styling**: [CSS_APPROACH]
- **Frontend layer**: [SPA_OR_REACTIVITY_LAYER]
- **API/Backend**: [API_OR_BACKEND_TECH]

### Authentication

[AUTH_MECHANISM_DESCRIPTION]

- **Sign in**: `[SIGN_IN_METHOD_AND_ENDPOINT]`
- **Sign out**: `[SIGN_OUT_METHOD_AND_ENDPOINT]`
- **Test credentials source**: `[TEST_CREDENTIALS_LOCATION]`  <!-- env var names only, never values -->
- **Rate limits / lockouts**: [AUTH_RATE_LIMITS_OR_NONE]
- **MFA / SSO notes**: [MFA_SSO_NOTES_OR_NONE]

### Key Routes

| Route | Purpose |
|-------|---------|
| `[ROUTE_LOGIN]` | Login page |
| `[ROUTE_HOME]` | Main landing page after auth |
| `[ROUTE_RESOURCE]` | [PURPOSE] |

### Framework-Specific Patterns

[FRAMEWORK_QUIRKS_THAT_AFFECT_TESTS]

- **Navigation**: [HOW_TO_WAIT_AFTER_NAVIGATION]
- **Forms**: [FORM_SUBMISSION_QUIRKS_CSRF_VALIDATION]
- **Dynamic content**: [HOW_DOM_UPDATES_AFFECT_TIMING]

---

## Commands

```bash
[CMD_RUN_TESTS]          # Run all tests (headless)
[CMD_RUN_HEADED]         # Run with visible browser (user only)
[CMD_RUN_UI]             # Playwright UI mode (user only)
[CMD_RUN_DEBUG]          # Step-through debug mode (user only)
[CMD_OPEN_REPORT]        # View last report (user only)
```

The agent runs only `[CMD_RUN_TESTS]`. The commands marked "user only" open a browser, debugger, or report outside the Playwright MCP; the user runs them.

---

## Structure

```
[E2E_ROOT]/
├── tests/               ← Test specs
│   ├── [auth/]          ← Auth flow tests
│   └── [feature/]       ← Feature tests
├── lib/
│   ├── pages/           ← Page Object Models
│   ├── fixtures/        ← Test data
│   ├── datafactory/     ← Data factories for seeding, if any
│   └── helpers/         ← Shared utilities
└── .auth/               ← Saved auth state (gitignored; the agent never reads it)
```

Import aliases (if configured in `tsconfig.json`):
- `@pages/*` → `[E2E_ROOT]/lib/pages/*`
- `@fixtures/*` → `[E2E_ROOT]/lib/fixtures/*`
- `@helpers/*` → `[E2E_ROOT]/lib/helpers/*`

---

## Authentication (Playwright Setup)

[AUTH_SETUP_STRATEGY]  <!-- setup project / global setup / storageState file / per-test login -->

Tests that need no auth:
```typescript
test.use({ storageState: { cookies: [], origins: [] } });
```

---

## Page Object Pattern

Every page object follows this exact structure:

```typescript
import { Page } from "@playwright/test";

export class ExamplePage {
  constructor(readonly page: Page) {}

  // -- Locators --
  readonly heading = this.page.getByRole("heading", { name: "Example" });
  readonly table = this.page.getByRole("table");
  readonly newButton = this.page.getByRole("link", { name: "New Example" });
  readonly rows = this.page.locator("tbody").getByRole("row");

  // -- Actions (only when dynamic — requires a parameter) --
  getRowByIndex(index: number) {
    return this.rows.nth(index);
  }

  // -- Flows (multi-step sequences used across tests) --
  async goto(): Promise<void> {
    await this.page.goto("/example");
  }
}
```

Rules:
- `constructor(readonly page: Page) {}` — always this shorthand
- Locators as inline class fields, not assigned inside the constructor body
- No `BasePage` — each page is self-contained
- Single-step actions (click, fill) belong in tests, not POMs
- Navigation methods named `goto()` or `gotoViewName()` (e.g., `gotoDetailView()`)

### Locator Priority

1. `getByRole` — buttons, links, headings, tables, rows, form controls
2. `getByLabel` — form fields with associated labels
3. `getByTestId` — elements with `data-testid` (add to view if needed)
4. CSS attribute selector — `[data-some-id]`
5. CSS class — last resort, never utility/generated classes

---

## Assertions

Always use web-first assertions, they auto-wait and produce better failure messages.

```typescript
// Page URL
await expect(page).toHaveURL(/\/resource/);
await expect(page).not.toHaveURL(/.*\/login/);

// Locator state
await expect(locator).toBeVisible();
await expect(locator).toHaveText("Expected");
await expect(locator).toBeEnabled();

// API responses
await expect(response).toBeOK();  // status 200-299
```

Never use synchronous assertions for page/locator state:
```typescript
// BAD
expect(page.url()).toContain("/path");
expect(await locator.isVisible()).toBeTruthy();

// GOOD
await expect(page).toHaveURL(/\/path/);
await expect(locator).toBeVisible();
```

Exception: `APIResponse.url()` has no web-first equivalent:
```typescript
expect(response.url()).toContain("/session");  // correct for APIResponse
```

---

## tsconfig.json Notes

- `"useDefineForClassFields": false`, required for inline locator fields that reference `this.page`. Without this, TypeScript emits fields before the constructor runs, causing TS error 2729 "Property used before initialization".
- If VS Code shows unresolved path alias imports, run "TypeScript: Restart TS Server".

---

## Project-Specific Notes

[ANYTHING_ELSE_FUTURE_TESTS_SHOULD_KNOW]  <!-- feature flags, seed scripts, environment toggles, known flaky areas, CI specifics -->

---

## Debugging (run by the user)

Traces, reports, and `test-results/` can hold headers, cookies, and page data. The agent does not open them. To debug a failing test, ask the user to run one of these and describe what they see:

```bash
[CMD_RUN_DEBUG]          # Step-through debug mode (Playwright Inspector)
[CMD_RUN_HEADED]         # Watch the test run in a visible browser
[CMD_OPEN_REPORT]        # Open the last report, with traces
```

For live locator checks, use Playwright MCP (see the e2e-testing skill, Step 3).

---

## Playwright 1.59, Features Useful for Testing and Debugging

### `locator.normalize()`, improve existing locators

Converts a locator to follow best practices (test IDs, aria roles):

```typescript
const better = await page.locator('input.email-field').normalize();
```

### `page.ariaSnapshot()`, capture aria tree

Useful for understanding what roles and names are available on a page when building POMs:

```typescript
const snapshot = await page.ariaSnapshot();
```

### `browserContext.setStorageState()`, reset auth mid-test

Clears existing cookies, local storage, and IndexedDB and sets new state without creating a new context:

```typescript
await context.setStorageState({ cookies: [], origins: [] });
```

### Screencast, video recording with annotations

Alternative to `recordVideo` with precise start/stop control:

```typescript
await page.screencast.start({ path: 'video.webm' });
await page.screencast.showActions({ position: 'top-right' });
// ... perform actions ...
await page.screencast.stop();
```

---

## Anti-Patterns

- `expect(page.url())` or `expect(await locator.isVisible())`, use web-first assertions
- Locators from utility/generated CSS classes, change with styling
- Generating locators by reading source code instead of browser inspection
- Single submit method for both happy path and validation cases
- Assuming checkbox or toggle default states without verifying
- Writing test plans to files, keep in chat
