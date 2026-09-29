# API Testing Reference

Fill in this template with your project's conventions. Replace each
`[...]` placeholder.

## Project Structure
- Tests: [e.g., `tests/<resource>/<resource>.<method>.spec.ts`]
- Data factories: [e.g., `lib/datafactory/`, one file per resource]
- Helpers: [e.g., `lib/helpers/`]
- Config: [e.g., `playwright.config.ts`]

## Environment
- Base URL: [env var name, e.g., `BASE_URL`, set as `baseURL` in the config]
- Credentials: [env var names only, e.g., `API_USER`, `API_PASSWORD`]
- Env file: [e.g., `.env`, gitignored]

## Data Conventions
- Randomization library: [e.g., `@faker-js/faker`]
- Resource dependencies: [e.g., "an order requires a customer"]
- Cleanup: [how tests remove the data they create, if needed]

## Test Template

```
[Paste one representative test from your codebase. It shows Claude
your team's setup, assertion, and data factory style.]
```

## Project Gotchas
- [e.g., "DELETE returns 204 with an empty body - do not call response.json()"]
