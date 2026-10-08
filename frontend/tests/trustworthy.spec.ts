import { test, expect } from '@playwright/test';

test.describe('Task 3 — Frontend-Backend Agreement & Trustworthiness Guards', () => {
  test('Case completion result card shows a valid date and non-empty transaction ID', async ({ page }) => {
    await page.goto('/investigate');
    await expect(page.locator('.app-container')).toBeVisible();

    // Select CASE-001 (Recurring Double Billing)
    const card001 = page.locator('.scenario-card', { hasText: 'CASE-001' });
    if (await card001.isVisible()) {
      await card001.click();
    }

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Wait for decision / approval gate
    const approveBtn = page.locator('#btn-approve-action');
    await expect(approveBtn).toBeVisible({ timeout: 20000 });

    // Approve the action
    await approveBtn.click();

    // Wait for the ExecutionOutcome card to appear
    const outcomeCard = page.locator('text=Sorted and finished — Action Executed');
    await expect(outcomeCard).toBeVisible({ timeout: 15000 });

    // 1. Assert non-empty transaction ID
    const txnIdElement = page.locator('text=Transaction ID:').locator('..').locator('.hash-pill');
    await expect(txnIdElement).toBeVisible();
    const txnId = (await txnIdElement.innerText()).trim();
    expect(txnId.length).toBeGreaterThan(0);
    expect(txnId).not.toBe('—');
    expect(txnId).toMatch(/^TXN-/);

    // 2. Assert valid date (NEVER "Invalid Date" or empty or dash)
    const timeElement = page.locator('text=Time Completed:').locator('..');
    const timeText = (await timeElement.innerText()).replace('Time Completed:', '').trim();
    expect(timeText).not.toContain('Invalid Date');
    expect(timeText.length).toBeGreaterThan(0);
    expect(timeText).not.toBe('—');

    // 3. Assert connector name is present
    const connectorElement = page.locator('text=Target System:').locator('..');
    const connectorText = (await connectorElement.innerText()).replace('Target System:', '').trim();
    expect(connectorText.length).toBeGreaterThan(0);

    // 4. Assert "Why" line is populated with rationale
    const whyElement = page.locator('text=Why:');
    if (await whyElement.isVisible()) {
      const whyText = (await whyElement.locator('..').innerText()).replace('Why:', '').trim();
      expect(whyText.length).toBeGreaterThan(0);
    }
  });

  test('Guard: staff-facing screens must never show raw codes outside expanded technical details', async ({ page }) => {
    // Matches raw snake_case or SCREAMING_SNAKE_CASE enum codes like PENDING_APPROVAL, AUTO_EXECUTED
    const rawCodeRegex = /\b[A-Z]{3,}_[A-Z_]{2,}\b/g;

    const pagesToCheck = ['/home', '/investigate', '/cases', '/guides'];

    for (const path of pagesToCheck) {
      await page.goto(path);
      await page.waitForLoadState('domcontentloaded');

      // Extract all text content excluding <details>, <pre>, and <code> technical blocks
      const visibleTexts = await page.evaluate(() => {
        const clone = document.body.cloneNode(true) as HTMLElement;
        clone.querySelectorAll('details, pre, code').forEach((el) => el.remove());
        return clone.innerText;
      });

      const matches = visibleTexts.match(rawCodeRegex) || [];
      expect(
        matches,
        `Page ${path} contains unformatted raw backend codes visible to support staff: ${matches.join(', ')}`
      ).toEqual([]);
    }
  });
});
