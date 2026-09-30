---
name: api-playwright-testing
description: Guides the creation of Playwright API tests from exploration through implementation. Covers API discovery, test plan creation, helper/data factory development, and test writing with human checkpoints at each stage.
---

# Writing API Tests

> Before starting, read the project config file `.claude/testing/api-config.md` for project-specific patterns, auth strategy, data factory rules, and assertion conventions. If it does not exist, create it in Step 0 from the `REFERENCE.md` template in this skill's folder.

## Pre-flight checks

Do these before starting any test work:

1. Confirm that the project's `package.json` lists `@playwright/test`.
2. Confirm that the project has a Playwright config file (for example,
   `playwright.config.ts`, or the path in the config file if Step 0 is
   done).

If either is missing, stop and ask the user to set up Playwright. Do not install packages yourself.

## Credentials

Never put passwords, tokens, API keys, or session cookies into the conversation.

- Do not ask the user for credentials. If the user pastes one, do not
  use or repeat it, and tell them to rotate it.
- Code reads credentials from environment variables. Refer to them by
  name only.
- Authenticate requests only through Playwright config or helpers that
  read those variables (for example, `extraHTTPHeaders` in
  `playwright.config.ts`). Do not call sign-in or token endpoints
  yourself.
- Never read, print, or log env files, saved auth state, tokens, auth
  headers, helper output, or auth responses. Do not run commands that
  print env values (`printenv`, `echo $VAR`), and do not open traces,
  reports, or `test-results/` files.
- Before you open any project file (config, spec, helper, fixture, or
  setup file), check it for hardcoded secrets with this match-only
  search. Files that only read `process.env` do not match.

  ```bash
  grep -lEi -e "(password|passwd|secret|token|api[_-]?key|cookie|credential)[a-z_]*[\"']?[[:space:]]*[:=][[:space:]]*[\"'\`][^\"'\`\$]" -e "(bearer|basic)[[:space:]]+[A-Za-z0-9._~+/=-]{8,}" <file>
  ```

  If the file matches, do not open it. Tell the user that it has a
  hardcoded secret and ask them to move it to an env var.
- When you run tests, you may quote test names, pass or fail, and
  assertion error messages. Before you quote output, remove any value
  that looks like a secret. If output shows a credential or token, do
  not repeat it, and tell the user to rotate it.
- Tests on auth responses assert only presence or type (for example,
  `expect(typeof body.token).toBe("string")`), never the value, so a
  failed assertion cannot print a token.

---

## Step 0: Project Configuration Q&A (run once per project)

Look for `.claude/testing/api-config.md` in the project.

- If it exists and has no placeholder of the form `[UPPER_SNAKE_CASE]`, skip this step.
- If it does not exist, copy `REFERENCE.md` from this skill's folder to that path. Then enter **Q&A mode** before doing anything else.
- If it exists but placeholders remain, enter **Q&A mode** for the remaining placeholders.

**Before Q&A: offer to explore existing tests first.**

Ask the user a single yes/no question:

> "I can explore the existing test directory and `playwright.config.ts` first to pre-fill answers from what already exists, then only ask you about anything I can't determine. Want me to do that, or would you rather answer every question manually?"

- If **yes** (recommended): locate the Playwright config and API test root (try common paths: `playwright.config.ts`, `api/`, `tests/api/`, `playwright/`, `tests/`). Read the config, a sampling of existing specs, auth helpers, data factories, fixtures, and `package.json` scripts. Do not open `.env` files or saved auth state. When a helper or fixture holds credentials, record only the env var names; never copy credential values. If an OpenAPI / Swagger spec or Postman collection is referenced in the repo, scan it to draft endpoint and auth answers. Build a draft answer for each placeholder below. Then run Q&A in **review mode**: present each pre-filled answer and ask the user to confirm, correct, or fill in `TBD`. Skip questions that are fully answered and confirmed.
- If **no**: run Q&A in **manual mode** using the rules below.

**Q&A mode rules:**

1. Ask the questions below **one at a time**, in order. Wait for the user's answer before asking the next.
2. If the user says "skip", "n/a", or "I don't know", record `TBD` for that placeholder and move on.
3. Do NOT guess values by reading the application source. Only fill in what the user provides, OR what you discovered from the existing test directory / API spec in the explore step above (and only after the user confirms it).
4. After all questions are answered, show the user a summary of the values and get confirmation.
5. Then write the values into `.claude/testing/api-config.md`, replacing every matching `[PLACEHOLDER]` token. Suggest that the user commits the file with the tests.

**Questions to ask (each maps to placeholders in the config file):**

1. **App name and one-line description?** -> `[APP_NAME]`, `[APP_DESCRIPTION]`
2. **Base URL for the API and the env var that sets it?** -> `[BASE_URL]`, `[BASE_URL_ENV_VAR]`
3. **Path to `playwright.config.ts` and the test files glob?** -> `[PLAYWRIGHT_CONFIG_PATH]`, `[TESTS_GLOB]`
4. **API style and where the spec / docs live?** (REST, GraphQL, RPC; OpenAPI URL, Postman collection, none) -> `[API_STYLE]`, `[API_SPEC_SOURCE]`
5. **Backend tech stack: framework + version, database, default content type, response envelope shape?** -> `[BACKEND_FRAMEWORK_AND_VERSION]`, `[DATABASE]`, `[DEFAULT_CONTENT_TYPE]`, `[RESPONSE_ENVELOPE_OR_NONE]`
6. **Authentication mechanism?** (cookie session, bearer JWT, API key, OAuth2, basic auth, other) -> `[AUTH_MECHANISM_DESCRIPTION]`, `[AUTH_TYPE]`
7. **Sign in / token issue endpoint and sign out / revoke endpoint?** -> `[SIGN_IN_METHOD_AND_ENDPOINT]`, `[SIGN_OUT_METHOD_AND_ENDPOINT]`
8. **Auth header construction, and the names of the env vars that hold test credentials?** (names only, never values) -> `[AUTH_HEADER_SHAPE]`, `[TEST_CREDENTIALS_LOCATION]`
9. **Token lifetime, refresh strategy, and how negative-auth tests get an invalid token?** -> `[TOKEN_LIFETIME_AND_REFRESH]`, `[INVALID_AUTH_STRATEGY]`, `[AUTH_RATE_LIMITS_OR_NONE]`
10. **Auth setup strategy in Playwright?** (helper called in beforeAll, global setup, storageState for cookie auth, per-test login) -> `[AUTH_SETUP_STRATEGY]`
11. **Three to five key endpoints** (auth, health, primary resource) with method, path, purpose -> `[METHOD_AUTH]`, `[ROUTE_AUTH]`, `[METHOD_HEALTH]`, `[ROUTE_HEALTH]`, `[METHOD_RESOURCE]`, `[ROUTE_RESOURCE]`, `[PURPOSE]`
12. **Backend quirks that affect tests?** (validation error shape and status, endpoints that return empty bodies, status code conventions like 403 vs 401, pagination style, ID format) -> `[BACKEND_QUIRKS_THAT_AFFECT_TESTS]`, `[VALIDATION_ERROR_SHAPE_AND_STATUS]`, `[WHICH_ENDPOINTS_RETURN_EMPTY_BODIES]`, `[STATUS_CODE_QUIRKS]`, `[PAGINATION_STYLE]`, `[ID_FORMAT]`
13. **npm/pnpm/yarn scripts for running tests** (all, single file, grep, debug, report) -> `[CMD_RUN_TESTS]`, `[CMD_RUN_FILE]`, `[CMD_RUN_GREP]`, `[CMD_RUN_DEBUG]`, `[CMD_OPEN_REPORT]`
14. **API test folder root path?** (e.g. `api`, `tests/api`, `playwright`) -> `[API_TEST_ROOT]`
15. **Randomization library used by data factories?** (e.g. `@faker-js/faker`) -> `[RANDOMIZATION_LIBRARY]`
16. **Anything else future tests should know?** (feature flags, seed scripts, env toggles, known flaky endpoints, CI specifics, project-specific anti-patterns or gotchas) -> `[ANYTHING_ELSE_FUTURE_TESTS_SHOULD_KNOW]`, `[PROJECT_SPECIFIC_ANTI_PATTERNS]`, `[PROJECT_SPECIFIC_GOTCHAS]`

After saving, continue with the workflow below.

---

Create Playwright API tests for an endpoint or resource, from
exploration through passing tests. Follow this workflow step by step.
**Stop after each step and check in with the user before proceeding.**

In the steps below, a placeholder such as `[API_TEST_ROOT]` or
`[API_SPEC_SOURCE]` means the value saved in `.claude/testing/api-config.md`.

## Workflow checklist

```
API Test Progress:
- [ ] Step 0: Project Configuration Q&A (skip if the config file has no placeholders)
- [ ] Step 1: Explore the API
- [ ] Step 2: Create the test plan
- [ ] Step 3: Create/update helpers & data factories
- [ ] Step 4: Write the tests
```

## Step 1: Explore the API

Understand the API before writing any tests. Gather information through
one or more of these methods:

1. **OpenAPI / Swagger spec or Postman collection** — if `[API_SPEC_SOURCE]`
   points to one, fetch and analyze it to extract endpoints,
   request/response schemas, required fields, auth mechanisms, and
   status codes.
2. **Exploratory API calls** — if no spec is available, make requests
   against the API using Playwright's `request` context. Skip sign-in and
   token endpoints. For endpoints that need auth, use the config or
   helpers that read env vars. Print
   only status codes and field names, never header or body values.
   Document endpoints, methods, auth requirements, request shapes,
   and response shapes by observing actual behavior.
3. **Existing test code** — read existing test files, helpers, and
   data factories under `[API_TEST_ROOT]` to understand what's already
   covered and what patterns are established.

For each endpoint discovered, document:

    # API Exploration: [Resource]
    [Overview of the resource and its purpose]

    ## Endpoints Discovered
    - [METHOD] [path] - [description]
      - Auth: [required | optional | none]
      - Request body: [shape or "none"]
      - Response: [status code] [shape]

    ## Authentication Mechanism
    - [cookie | token | bearer | API key | none]
    - [How credentials are obtained — env var names only, never values]

    ## Data Models
    - [Model name]: [key fields, types, required vs optional]

    ## Dependencies Between Resources
    - [e.g., "Booking requires a Room to exist first"]

**-> STOP. Present the exploration findings. Confirm endpoints, auth mechanism, and data models with the user before proceeding.**

## Step 2: Create the test plan

Based on the exploration, plan which endpoints to test and what
scenarios to cover. If the user provides specific test scenarios, use
ONLY those. Do not invent additional scenarios.

Present the plan in chat using this structure:

    # Test Plan for [Resource]
    [Overview]

    ## Setup Required
    - [Dependencies]: [What must exist before tests run]
    - [Auth]: [How auth headers/cookies will be created]

    ## Data Factories Needed
    - [Factory name]: [What it creates, with what randomization]

    ## Helper Modifications
    - [Helper]: [New methods or changes needed]

    ## Test Files to Create
    - [resource].[method].spec.ts
      - **[Test Case]**: [Description]
        - Arrange: [Setup steps]
        - Act: [Request details]
        - Assert: [Expected status, body, headers]

For each endpoint, consider these test categories:

- **Happy path** — Valid request with all required fields
- **Authentication** — Missing auth, invalid auth, expired auth
- **Validation** — Missing required fields, invalid types, boundary values
- **Not found** — Non-existent resource IDs
- **Integration** — Create-then-read, update-then-verify workflows

Include exact data requirements. Use the project's randomization
library (see `[RANDOMIZATION_LIBRARY]` in the config file) for realistic
values. Do NOT write the plan to a file.

**-> STOP. Present the plan. Confirm scope, test cases, and data requirements with the user before proceeding.**

## Step 3: Create/update helpers & data factories

1. Read existing helper and data factory files under `[API_TEST_ROOT]`
   to identify what can be reused or extended.
2. For authentication, create or update header-creation helpers that
   return ready-to-use auth headers (cookies, tokens, or API keys).
   Helpers read credentials from env vars. Include an invalid-auth
   helper for negative tests. Match the signatures documented in the
   config file.
3. For test data, create factory functions that generate randomized
   request bodies. Each factory should:
   - Return a complete, valid request body by default
   - Accept an `overrides` argument for pinning specific fields
   - Handle resource dependencies (e.g., create a parent before a child)
4. Run any unit tests for helpers to verify they work.

Follow the Data Factory Pattern in the config file for the exact factory
template and rules.

Rules:

- Factories generate randomized but valid data by default
- Auth helpers handle the full login flow internally, with credentials from env vars
- Never print or log helper output, tokens, or headers
- Keep helpers focused, one responsibility per function

**-> STOP. Present the helpers and data factories. Review signatures, data shapes, and auth flow with the user.**

## Step 4: Write the tests

1. Read the test plan to identify the test cases to implement.
2. Read the relevant helpers and factories to understand available
   methods.
3. Write test files organized by resource and HTTP method:
   `[API_TEST_ROOT]/tests/[resource]/[resource].[method].spec.ts`
4. Run the tests to confirm they pass.

Test file structure to follow:

    import { test, expect } from "@playwright/test";

    test.describe("resource/ GET requests", async () => {
      let headers;

      test.beforeAll(async () => {
        headers = await createHeaders();
      });

      test("GET all resources", async ({ request }) => {
        const response = await request.get("resource/", {
          headers: headers,
        });

        expect(response.status()).toBe(200);
        const body = await response.json();
        expect(body.length).toBeGreaterThan(0);
      });

      test("GET resource without auth", async ({ request }) => {
        const response = await request.get("resource/");
        expect(response.status()).toBe(403);
      });
    });

Rules:

- One test file per resource + HTTP method combination
- `test.describe` groups tests by endpoint and method
- `test.beforeAll` / `test.beforeEach` for shared setup
- Use `test.step()` for multi-step integration tests
- Each request should assert status code first, then body
- Use `request.newContext()` when tests need isolated cookie state

**-> STOP. Share test results. Confirm tests pass and cover the intended scenarios.**

## Critical rules

- Never put credentials into the conversation; refer to env vars by name only
- Run Step 0 Q&A before any test work if the config file is missing or still has `[PLACEHOLDER]` tokens
- Plan stays in chat, never written to a file
- If user provides test scenarios, use ONLY those, no extras
- Validate auth and data factories by running them (check pass or fail only), don't assume they work
- Run tests after writing helpers AND after writing tests
- Set realistic scope, avoid feature creep

## Anti-patterns

- Asking for, pasting, hardcoding, or printing credentials
- Generating request shapes by reading application source instead of the spec or actual responses
- Hardcoding test data instead of using the randomization library
- Sharing mutable state between tests without `beforeEach` reset
- Asserting on auto-incrementing IDs beyond existence checks
- Relying on database state from prior test runs
- Writing the test plan to a file instead of keeping it in chat
- Inventing test scenarios when the user provided specific ones
