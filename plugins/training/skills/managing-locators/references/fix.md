# Fix Mode Reference

## Inputs
- Test file path with the failing test
- Error message showing the broken locator
- Optional: description of the element's purpose

## Steps

1. **Analyze the error**
   - Identify the broken locator and what element it targeted
   - Read the test file and relevant POM to see how the locator is used
2. **Navigate and snapshot**
   - Use Playwright MCP to reach the affected page/dialog/form
   - Snapshot to capture the current DOM structure
3. **Find a replacement** following locator priority:
   - `getByRole` with accessible name
   - `getByLabel`
   - `getByTestId` / data attributes
   - CSS selectors (last resort)
4. **Verify the replacement**
   - Confirm it selects exactly one element
   - Test across different states (empty, populated, loading)
   - For repeated elements: use parent context + child selector
   - For dialogs: target inner form fields, not the dialog wrapper
5. **Update and run**
   - Replace the broken locator in the test or POM file
   - Check if similar locators nearby need the same fix
   - Run the failing test, then run related tests for downstream breakage

## Tips
- Dialog timing: wait for a specific inner field to be visible after opening — the wrapper appears before contents are ready
- Repeated elements: scope with a parent locator first (e.g., `page.locator('tr', { hasText: 'Row' }).locator('button')`) then target the child
- Bulk breakage: fix one representative case first and apply the pattern to the rest
