# API Testing Reference

Template for the project config file. Step 0 of the api-playwright-testing skill copies it to `.claude/testing/api-config.md` in the project and fills it in.

> The config is complete when no bracketed ALL-CAPS placeholders remain. Never write credential values in this file; use env var names only.

---

## Application Under Test

**[APP_NAME]** — [APP_DESCRIPTION]

- **Base URL**: `[BASE_URL]` (set via `[BASE_URL_ENV_VAR]` or config file)
- **Config file**: `[PLAYWRIGHT_CONFIG_PATH]`
- **Tests location**: `[TESTS_GLOB]`
- **API style**: [API_STYLE]  <!-- e.g., REST, GraphQL, RPC -->
- **Spec / docs source**: [API_SPEC_SOURCE]  <!-- e.g., OpenAPI URL, Postman collection, none -->

---

## Tech Stack

- **Backend framework / language**: [BACKEND_FRAMEWORK_AND_VERSION]
- **Database**: [DATABASE]
- **Content type**: [DEFAULT_CONTENT_TYPE]  <!-- e.g., application/json -->
- **Response envelope**: [RESPONSE_ENVELOPE_OR_NONE]  <!-- e.g., { data, errors } or "raw object" -->

### Authentication

[AUTH_MECHANISM_DESCRIPTION]

- **Auth type**: [AUTH_TYPE]  <!-- cookie session, bearer JWT, API key, OAuth2, basic auth -->
- **Sign in / token endpoint**: `[SIGN_IN_METHOD_AND_ENDPOINT]`
- **Sign out / revoke endpoint**: `[SIGN_OUT_METHOD_AND_ENDPOINT]`
- **Header construction**: `[AUTH_HEADER_SHAPE]`  <!-- e.g., { Authorization: "Bearer <token>" } -->
- **Test credentials source**: `[TEST_CREDENTIALS_LOCATION]`  <!-- env var names only, never values -->
- **Token lifetime / refresh**: [TOKEN_LIFETIME_AND_REFRESH]
- **Invalid auth strategy**: [INVALID_AUTH_STRATEGY]  <!-- how negative-auth tests get an invalid token -->
- **Rate limits / lockouts**: [AUTH_RATE_LIMITS_OR_NONE]

### Key Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `[METHOD_AUTH]` | `[ROUTE_AUTH]` | Auth / token issue |
| `[METHOD_HEALTH]` | `[ROUTE_HEALTH]` | Health check |
| `[METHOD_RESOURCE]` | `[ROUTE_RESOURCE]` | [PURPOSE] |

### Backend-Specific Patterns

[BACKEND_QUIRKS_THAT_AFFECT_TESTS]

- **Validation errors**: [VALIDATION_ERROR_SHAPE_AND_STATUS]  <!-- e.g., 400 with { errors: [...] }, 422 with field map -->
- **Empty bodies**: [WHICH_ENDPOINTS_RETURN_EMPTY_BODIES]
- **Status code conventions**: [STATUS_CODE_QUIRKS]  <!-- e.g., 403 vs 401, 204 vs 200 on delete -->
- **Pagination**: [PAGINATION_STYLE]  <!-- offset, cursor, link header, none -->
- **ID format**: [ID_FORMAT]  <!-- integer auto-increment, UUID, slug -->

---

## Commands

```bash
[CMD_RUN_TESTS]          # Run all API tests
[CMD_RUN_FILE]           # Run a single spec file
[CMD_RUN_GREP]           # Run by test name pattern
[CMD_RUN_DEBUG]          # Step-through debug mode (user only)
[CMD_OPEN_REPORT]        # View last report (user only)
```

The agent runs only the test commands. The commands marked "user only" open a debugger or report, which can show headers and tokens; the user runs them.

---

## Structure

```
[API_TEST_ROOT]/
├── tests/                  ← Test specs (one file per resource + method)
│   ├── [resource].get.spec.ts
│   ├── [resource].post.spec.ts
│   └── [resource].put.spec.ts
├── lib/
│   ├── datafactory/        ← Faker-driven request body factories, one per resource
│   ├── helpers/            ← Auth, date, and shared utilities
│   └── fixtures/           ← Static test data, if any
└── .env                    ← Credentials and base URL (gitignored; the agent never reads it)
```

Import aliases (if configured in `tsconfig.json`):
- `@datafactory/*` → `[API_TEST_ROOT]/lib/datafactory/*`
- `@helpers/*` → `[API_TEST_ROOT]/lib/helpers/*`
- `@fixtures/*` → `[API_TEST_ROOT]/lib/fixtures/*`

---

## Authentication (Playwright Setup)

[AUTH_SETUP_STRATEGY]  <!-- e.g., createHeaders() helper called in beforeAll, or storageState for cookie-based APIs -->

Helper signatures expected by the suite:

```typescript
// Returns headers ready to attach to a request
export async function createHeaders(): Promise<Record<string, string>>;

// Returns headers that should be rejected by the API (for negative tests)
export async function createInvalidHeaders(): Promise<Record<string, string>>;
```

Tests that need no auth call the endpoint without the `headers` option.

---

## Data Factory Pattern

Every data factory follows this structure:

```typescript
import { faker } from "@faker-js/faker";

export interface CreateResourceBody {
  parentId: number;
  name: string;
  email: string;
  active: boolean;
}

export function createRandomResourceBody(
  parentId: number,
  overrides: Partial<CreateResourceBody> = {},
): CreateResourceBody {
  return {
    parentId,
    name: faker.person.firstName(),
    email: faker.internet.email(),
    active: faker.datatype.boolean(),
    ...overrides,
  };
}
```

Rules:
- One factory file per resource, colocated under `lib/datafactory/`
- Default return is a complete, valid request body
- Accept an `overrides` object so tests can pin specific fields
- Resolve dependencies (e.g., create a parent resource) by composing factories or accepting parent IDs as arguments
- Never hardcode test data, always randomize via [RANDOMIZATION_LIBRARY]

---

## Common Test Patterns

### Happy Path CRUD
```typescript
test("POST resource with valid data", async ({ request }) => {
  const response = await request.post("resource/", {
    headers: headers,
    data: requestBody,
  });

  expect(response.status()).toBe(201);
  const body = await response.json();
  expect(body.id).toBeGreaterThan(0);
  expect(body.name).toBe(requestBody.name);
});
```

### Missing Auth
```typescript
test("GET resource without auth", async ({ request }) => {
  const response = await request.get("resource/");
  expect(response.status()).toBe(403);
});
```

### Invalid Auth
```typescript
test("PUT resource with invalid auth", async ({ request }) => {
  const invalidHeaders = await createInvalidHeaders();
  const response = await request.put(`resource/${id}`, {
    headers: invalidHeaders,
    data: requestBody,
  });
  expect(response.status()).toBe(403);
});
```

### Missing Required Field
```typescript
test("POST resource without required field", async ({ request }) => {
  const invalidBody = { ...requestBody };
  delete invalidBody.name;

  const response = await request.post("resource/", {
    headers: headers,
    data: invalidBody,
  });

  expect(response.status()).toBe(400);
});
```

### Multi-Step Integration (Create then Verify)
```typescript
test("POST then GET resource", async ({ request }) => {
  let resourceId: number;

  await test.step("Create resource", async () => {
    const response = await request.post("resource/", {
      headers: headers,
      data: requestBody,
    });
    expect(response.status()).toBe(201);
    const body = await response.json();
    resourceId = body.id;
  });

  await test.step("Verify resource exists", async () => {
    const response = await request.get(`resource/${resourceId}`, {
      headers: headers,
    });
    expect(response.status()).toBe(200);
    const body = await response.json();
    expect(body.name).toBe(requestBody.name);
  });
});
```

### Non-Existent Resource
```typescript
test("GET non-existent resource returns 404", async ({ request }) => {
  const response = await request.get("resource/999999", {
    headers: headers,
  });
  expect(response.status()).toBe(404);
});
```

---

## Assertions

Always assert status code first, then body shape, then specific values.

```typescript
// Status
expect(response.status()).toBe(200);
expect(response.ok()).toBeTruthy();

// Body shape
const body = await response.json();
expect(body).toMatchObject({ id: expect.any(Number), name: expect.any(String) });

// Specific values
expect(body.name).toBe(requestBody.name);
```

Web-first response assertion (auto-retries pending responses):
```typescript
await expect(response).toBeOK();  // status 200-299
```

Never call `response.json()` without first checking the body is non-empty for endpoints that may return 204 / empty bodies — use `response.text()` and parse defensively.

---

## tsconfig.json Notes

- `"strict": true` recommended so factory `Partial<>` overrides are type-checked
- If VS Code shows unresolved path alias imports, run "TypeScript: Restart TS Server"

---

## Project-Specific Notes

[ANYTHING_ELSE_FUTURE_TESTS_SHOULD_KNOW]  <!-- feature flags, seed scripts, environment toggles, known flaky endpoints, CI specifics -->

---

## Functions & Patterns to Avoid

- Never hardcode test data, use the project's randomization library
- Never share mutable state between tests without `beforeEach` reset
- Don't assert on auto-incrementing IDs beyond existence checks
- Don't rely on database state from prior test runs, create what you need
- Avoid sleeping or polling, use `expect().toPass()` with retry intervals for eventual consistency
- Don't reuse a single `request` context across tests that need isolated cookie state, call `request.newContext()`
- [PROJECT_SPECIFIC_ANTI_PATTERNS]

---

## Framework-Specific Gotchas

- `response.json()` throws if the body is empty, check `response.text()` first for endpoints that return empty bodies (login, delete, 204)
- `request.newContext()` is needed when tests require isolated cookie jars
- PUT/PATCH may require the full object, not just changed fields, check API behavior
- Some APIs return different status codes for the same error depending on auth state (403 vs 401)
- Date fields may be timezone-sensitive, use UTC helpers for consistency
- [PROJECT_SPECIFIC_GOTCHAS]
