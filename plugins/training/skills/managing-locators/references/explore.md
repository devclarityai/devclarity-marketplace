# Explore Mode Reference

## Inputs
- Feature or page to explore (e.g., a settings dialog, a data table)
- Navigation path or URL to reach the feature
- Specific interactions to test (optional)

## Steps

1. **Navigate** to the target page via Playwright MCP
2. **Snapshot before interaction** — capture the initial page state
3. **Interact systematically**
   - Click buttons/links to reveal hidden elements (dialogs, dropdowns, menus)
   - Fill form fields with test data to expose validation states (never credentials)
   - Snapshot after each significant interaction
4. **Catalog locators** for each discovered element:
   - IDs and data attributes
   - ARIA roles and labels
   - Accessible names from `getByRole`
   - Note any dynamic or timing-sensitive elements
5. **Test reliability**
   - Verify each locator selects exactly one element
   - Repeat interactions 2-3 times to confirm consistency
6. **Present findings** organized by element purpose:
   ```
   ## [Feature Name] Locators
   - [Element description]: `[recommended locator]`
   - [Element description]: `[recommended locator]`
     Wait condition: [e.g., waitForSelector after dialog open]
   ```

## Tips
- Snapshot frequency: capture state before AND after every interaction — dialogs, dropdowns, and navigation all change the DOM
- Hidden elements: some elements only exist in the DOM after a trigger — always interact first, then snapshot
- Dynamic IDs: if an ID contains a hash or timestamp, skip it and prefer role/label strategies
