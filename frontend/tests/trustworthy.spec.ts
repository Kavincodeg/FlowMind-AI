import { test, expect } from '@playwright/test';

test.describe('Task 3 — Frontend-Backend Agreement & Trustworthiness Guards', () => {
  test('Case completion result card shows a valid date and non-empty transaction ID', async ({ page }) => {
    // Intercept investigate and approve to assert result card and evidence display
    await page.route('**/api/workflow/investigate', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-test-1234',
          status: 'PENDING_APPROVAL',
          started_at: '2026-10-08T10:00:00Z',
          completed_at: null,
          request: {
            customer_id: 'CUST-4091',
            customer_name: 'Sarah Lin',
            issue_summary: 'Recurring Double Billing',
          },
          reasoning: {
            status: 'RECOMMENDATION_READY',
            root_cause: 'Duplicate subscription renewal charge detected',
            rationale: 'Customer was billed twice in violation of Billing Policy Section 3.1. Refund approved.',
            confidence_score: 0.94,
            requires_human_approval: true,
            recommendation: {
              action_type: 'ISSUE_REFUND_RECOMMENDATION',
              target_team: 'Finance & Compliance Team',
              rationale: 'Customer was billed twice in violation of Billing Policy Section 3.1. Refund approved.',
              requires_human_approval: true,
              parameters: { amount: 499, reason: 'Duplicate billing' },
            },
            citations: [
              {
                source_type: 'ticket',
                source_id: 'TKT-0014',
                chunk_index: 0,
                snippet: 'Customer reports double charge. This is the second time they contacted support.',
                score: 0.912,
              },
              {
                source_type: 'policy',
                source_id: 'refund_policy.md',
                chunk_index: 0,
                snippet: 'Full refund shall be issued immediately upon verification of duplicate billing transaction.',
                score: 0.845,
              },
            ],
            retrieval_summary: { total_found: 2 },
          },
          approval_record: null,
          execution_record: null,
          error_message: null,
        }),
      });
    });

    await page.route('**/api/workflow/*/decision', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          workflow_id: 'wf-test-1234',
          status: 'COMPLETED',
          started_at: '2026-10-08T10:00:00Z',
          completed_at: '2026-10-08T10:00:15Z',
          request: {
            customer_id: 'CUST-4091',
            customer_name: 'Sarah Lin',
            issue_summary: 'Recurring Double Billing',
          },
          reasoning: {
            status: 'RECOMMENDATION_READY',
            root_cause: 'Duplicate subscription renewal charge detected',
            rationale: 'Customer was billed twice in violation of Billing Policy Section 3.1. Refund approved.',
            confidence_score: 0.94,
            requires_human_approval: true,
            recommendation: {
              action_type: 'ISSUE_REFUND_RECOMMENDATION',
              target_team: 'Finance & Compliance Team',
              rationale: 'Customer was billed twice in violation of Billing Policy Section 3.1. Refund approved.',
              requires_human_approval: true,
              parameters: { amount: 499, reason: 'Duplicate billing' },
            },
            citations: [
              {
                source_type: 'ticket',
                source_id: 'TKT-0014',
                chunk_index: 0,
                snippet: 'Customer reports double charge. This is the second time they contacted support.',
                score: 0.912,
              },
              {
                source_type: 'policy',
                source_id: 'refund_policy.md',
                chunk_index: 0,
                snippet: 'Full refund shall be issued immediately upon verification of duplicate billing transaction.',
                score: 0.845,
              },
            ],
            retrieval_summary: { total_found: 2 },
          },
          approval_record: {
            approver_id: 'USR-002',
            approver_name: 'Marcus Vance',
            approver_role: 'team_lead',
            decision: 'APPROVE',
            timestamp: '2026-10-08T10:00:10Z',
          },
          execution_record: {
            workflow_id: 'wf-test-1234',
            transaction_id: 'TXN-90248-REFUND-OK',
            connector_name: 'Billing API Connector',
            action_type: 'ISSUE_REFUND_RECOMMENDATION',
            status: 'SUCCESS',
            details: { refund_amount: 499, currency: 'USD' },
            executed_at: '2026-10-08T10:00:12Z',
            latency_ms: 12.5,
            is_idempotent_replay: false,
          },
          error_message: null,
        }),
      });
    });

    await page.goto('/investigate');
    await expect(page.locator('.app-container')).toBeVisible();

    // Wait for initial connection/loading spinner to resolve
    await expect(page.locator('text=Connecting to customer support system...')).not.toBeVisible({ timeout: 15000 });

    // Select CASE-001 (Recurring Double Billing)
    const card001 = page.locator('.scenario-card', { hasText: 'CASE-001' });
    await expect(card001).toBeVisible({ timeout: 10000 });
    await card001.click();

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Capture screenshot (a): Investigation where evidence scores differ and excerpts show real text
    const evidenceSection = page.locator('text=WHAT WE FOUND').first();
    await expect(evidenceSection).toBeVisible({ timeout: 10000 });
    await page.screenshot({ path: 'screenshots/screenshot_a_investigation_evidence.png', fullPage: true });

    // Wait for decision / approval gate
    const approveBtn = page.locator('#btn-approve-action');
    await expect(approveBtn).toBeVisible({ timeout: 20000 });

    // Approve the action
    await approveBtn.click();

    // Wait for the ExecutionOutcome card to appear
    const outcomeCard = page.locator('text=Sorted and finished — Action Executed');
    await expect(outcomeCard).toBeVisible({ timeout: 15000 });

    // Capture screenshot (b): Completed case where result card shows valid date and transaction ID
    await page.screenshot({ path: 'screenshots/screenshot_b_completed_case.png', fullPage: true });

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
