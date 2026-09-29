# E2E Testing Reference

Fill in this template with your project's conventions. Replace each
`[...]` placeholder.

## Application Under Test
- App: [name and short purpose]
- Base URL: [env var name, e.g., `BASE_URL`, set as `baseURL` in the config]
- Key pages: [path - purpose]

## Commands
- Run all tests: [e.g., `npx playwright test`]
- Run headed: [e.g., `npx playwright test --headed`]
- View report: [e.g., `npx playwright show-report`]

## Structure
- Tests: [e.g., `e2e/tests/<feature>/*.spec.ts`]
- Page Object Models: [e.g., `e2e/pages/`]
- Data factories: [e.g., `e2e/datafactory/`]
- Auth setup: [e.g., a setup project that signs in with env var credentials and saves state]

## Page Object Pattern

```typescript
import { Page } from "@playwright/test";

export class ExamplePage {
  constructor(readonly page: Page) {}

  readonly heading = this.page.getByRole("heading", { name: "Example" });
  readonly newButton = this.page.getByRole("button", { name: "New" });

  async goto(): Promise<void> {
    await this.page.goto("/example");
  }
}
```

- Locators as class fields; flows as methods
- Single-step actions (click, fill) stay in tests
- Class-field locators need `"useDefineForClassFields": false` in `tsconfig.json`
- [Team-specific POM rules]

## Assertions
- Use web-first assertions: `await expect(page).toHaveURL(...)`,
  `await expect(locator).toBeVisible()`
- Do not use `expect(await locator.isVisible()).toBeTruthy()`

## Project Gotchas
- [e.g., "Wait for a specific element after form submit, not network idle"]
