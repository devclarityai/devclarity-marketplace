---
name: api-playwright-testing
description: Guides the creation of Playwright API tests from exploration through implementation. Covers API discovery, test plan creation, helper/data factory development, and test writing with human checkpoints at each stage.
---

# Writing API Tests

Create Playwright API tests for an endpoint or resource, from exploration
through passing tests. Follow this workflow step by step. **Stop after
each step and check in with the user before proceeding.**

Before starting, read `REFERENCE.md` in this skill's folder for the
team's project conventions.

## Credentials

Never put passwords, tokens, or API keys into the conversation.

- Do not ask the user for credentials. If the user pastes one, do not
  use or repeat it, and tell them to rotate it.
- Code reads credentials from environment variables. Refer to them by
  name only.
- Never read, print, or log env files, tokens, or auth responses.

## Workflow checklist

```
API Test Progress:
- [ ] Step 1: Explore the API
- [ ] Step 2: Create the test plan
- [ ] Step 3: Create/update helpers & data factories
- [ ] Step 4: Write the tests
```

## Step 1: Explore the API

Gather information through one or more of these methods:

1. **OpenAPI / Swagger spec** - Ask the user if a spec is available. If
   yes, read it for endpoints, schemas, required fields, and status codes.
2. **Exploratory requests** - If no spec is available, send requests
   with Playwright's `request` context and record the observed behavior.
3. **Existing test code** - Read existing tests, helpers, and data
   factories to find what is covered and which patterns to follow.

Document the findings:

    # API Exploration: [Resource]
    ## Endpoints
    - [METHOD] [path] - [description]
      - Request body: [shape or "none"]
      - Response: [status code] [shape]
    ## Data Models
    - [Model]: [key fields, types, required vs optional]
    ## Dependencies
    - [e.g., "An order requires a customer to exist first"]

**-> STOP. Present the findings. Confirm endpoints and data models with the user.**

## Step 2: Create the test plan

Plan which endpoints and scenarios to test. If the user provides
specific scenarios, use ONLY those. Present the plan in chat, not in a
file:

    # Test Plan for [Resource]
    ## Setup Required
    - [What must exist before tests run]
    ## Data Factories Needed
    - [Factory]: [What it creates]
    ## Test Files
    - [resource].[method].spec.ts
      - **[Test case]**: Arrange / Act / Assert

Consider these categories for each endpoint:

- **Happy path** - Valid request with all required fields
- **Validation** - Missing fields, invalid types, boundary values
- **Not found** - Non-existent resource IDs
- **Integration** - Create-then-read, update-then-verify

**-> STOP. Present the plan. Confirm scope and test cases with the user.**

## Step 3: Create/update helpers & data factories

1. Read existing helpers and factories to find what can be reused.
2. Create factory functions that return a complete, valid request body
   with randomized data (for example, Faker.js) and accept overrides.
3. Handle resource dependencies in the factory or in test setup.

Example factory:

    export function createResourceBody(overrides = {}) {
      return {
        name: faker.person.firstName(),
        email: faker.internet.exampleEmail(),
        ...overrides,
      };
    }

**-> STOP. Present the helpers and factories. Review signatures and data shapes with the user.**

## Step 4: Write the tests

1. Write test files by resource and HTTP method:
   `tests/[resource]/[resource].[method].spec.ts`
2. Assert the status code first, then the body.
3. Use `test.step()` for multi-step integration tests.
4. Run the tests and confirm they pass.

Example test:

    import { test, expect } from "@playwright/test";

    test.describe("resource GET", () => {
      test("returns all resources", async ({ request }) => {
        const response = await request.get("resource/");
        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.length).toBeGreaterThan(0);
      });
    });

**-> STOP. Share the test results. Confirm the tests cover the intended scenarios.**

## Anti-patterns

- Hardcoding credentials or test data
- Testing only happy paths
- Putting request-building logic in test files instead of helpers
- Inventing scenarios when the user provided specific ones
- Using `test.fixme()` or `test.skip()` to hide failures
