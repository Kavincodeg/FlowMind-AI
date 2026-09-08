import { test, expect } from '@playwright/test';

test.describe('FlowMind AI — End-to-End Enterprise Governance Suite', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/');
    // Wait for the app container to render
    await expect(page.locator('.app-container')).toBeVisible();
  });

  test('1. Initial Load & Anti-Slop Visual Rules (SKILL.md Compliance)', async ({ page }) => {
    // Check page title & metadata
    await expect(page).toHaveTitle(/FlowMind AI/);

    // Verify brand header
    const brandTitle = page.locator('.brand-title');
    await expect(brandTitle).toHaveText('FlowMind AI');

    const brandSubtitle = page.locator('.brand-subtitle');
    await expect(brandSubtitle).toContainText('Evidence-Grounded Enterprise Governance & Workflow Agent');

    // Verify FastAPI connection status
    const statusBadge = page.locator('.api-status-badge');
    await expect(statusBadge).toContainText('FastAPI Connected');

    // Verify default active persona is Marcus Vance (Team Lead)
    const personaSelect = page.locator('header select');
    await expect(personaSelect).toHaveValue('USR-002');

    // Check pre-configured benchmark scenarios
    const scenarioCards = page.locator('.scenario-card');
    await expect(scenarioCards).toHaveCount(4);
    await expect(page.locator('text=CASE-001')).toBeVisible();
    await expect(page.locator('text=CASE-003')).toBeVisible();
    await expect(page.locator('text=CASE-005')).toBeVisible();
    await expect(page.locator('text=CASE-013')).toBeVisible();

    // Verify anti-slop rules: zero decorative emojis in UI text/headings
    const headerText = await page.locator('.app-header').innerText();
    expect(headerText).not.toMatch(/[\u{1F300}-\u{1F6FF}]/u); // No emoji block
  });

  test('2. Preset Scenario Selection & Reactive Form Inputs', async ({ page }) => {
    // 1. Select CASE-003 (Checkout 500 Server Error)
    await page.locator('.scenario-card', { hasText: 'CASE-003' }).click();
    await expect(page.locator('#customer-id')).toHaveValue('CUST-1044');
    await expect(page.locator('#customer-name')).toHaveValue('David Kim');
    await expect(page.locator('#issue-summary')).toContainText('500');

    // 2. Select CASE-013 (Adversarial Prompt Injection)
    await page.locator('.scenario-card', { hasText: 'CASE-013' }).click();
    await expect(page.locator('#customer-id')).toHaveValue('CUST-9999');
    await expect(page.locator('#customer-name')).toHaveValue('Mallory Thorne');
    await expect(page.locator('#issue-summary')).toContainText('SYSTEM OVERRIDE');

    // 3. Re-select CASE-001
    await page.locator('.scenario-card', { hasText: 'CASE-001' }).click();
    await expect(page.locator('#customer-id')).toHaveValue('CUST-4091');
    await expect(page.locator('#customer-name')).toHaveValue('Sarah Lin');
  });

  test('3. Closed-Loop Investigation Pipeline Execution', async ({ page }) => {
    // Ensure CASE-001 is active
    await page.locator('.scenario-card', { hasText: 'CASE-001' }).click();

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Wait for the investigation to complete
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Verify reasoning timeline steps
    await expect(page.locator('text=1. Evidence Retrieval')).toBeVisible();
    await expect(page.locator('text=2. Contextual Root Cause')).toBeVisible();
    await expect(page.locator('text=3. Security & Indirect Injection Guardrail')).toBeVisible();

    // Verify evidence drawer or abstention status badge
    const evidenceDrawer = page.locator('.citation-card, .badge-warning, .alert-warning');
    await expect(evidenceDrawer.first()).toBeVisible();
  });

  test('4. Persona Switching & Role-Based Access Control (RBAC)', async ({ page }) => {
    const personaSelect = page.locator('header select');

    // Switch to Sarah Jenkins (Support Agent)
    await personaSelect.selectOption('USR-001');
    await expect(page.locator('header .badge')).toHaveText(/support_agent/i);

    // Switch to Elena Rostova (Manager)
    await personaSelect.selectOption('USR-003');
    await expect(page.locator('header .badge')).toHaveText(/manager/i);

    // Switch to Alex Chen (Admin)
    await personaSelect.selectOption('USR-004');
    await expect(page.locator('header .badge')).toHaveText(/admin/i);

    // Switch back to Marcus Vance (Team Lead)
    await personaSelect.selectOption('USR-002');
    await expect(page.locator('header .badge')).toHaveText(/team_lead/i);
  });

  test('5. Cryptographic SHA-256 Audit Trail Explorer', async ({ page }) => {
    // Navigate to Audit tab
    await page.locator('nav button', { hasText: 'Cryptographic Audit Trail' }).click();

    // Verify panel header
    await expect(page.locator('text=Workflow Audit Logs')).toBeVisible();
    await expect(page.locator('text=Cryptographic SHA-256 Hash Chain Inspector')).toBeVisible();

    // Confirm that the audit run selector contains items
    const auditButtons = page.locator('.scenario-card');
    const count = await auditButtons.count();
    expect(count).toBeGreaterThan(0);

    // Select the first audit log
    await auditButtons.first().click();

    // Verify cryptographic integrity check
    await expect(page.locator('text=Cryptographic Chain Verified (Intact)')).toBeVisible();

    // Verify sequential block linkage
    await expect(page.locator('text=Sequenced Audit Blocks (SHA-256 Parent Hash Linkage)')).toBeVisible();
    await expect(page.locator('text=BLOCK #1')).toBeVisible();
  });

  test('6. Phase 4 Comparative Empirical Benchmarks Dashboard', async ({ page }) => {
    // Navigate to Benchmarks tab
    await page.locator('nav button', { hasText: 'Empirical Benchmarks' }).click();

    // Verify Table 1 header
    await expect(page.locator('text=Phase 4 Comparative Empirical Benchmark')).toBeVisible();
    await expect(page.locator('text=Table 1: FlowMind AI vs Plain-RAG Baseline')).toBeVisible();

    // Verify metrics in Table 1
    await expect(page.locator('text=Workflow Task Success Rate')).toBeVisible();
    await expect(page.locator('text=100.0%').first()).toBeVisible();

    await expect(page.locator('text=Citation & Grounding Integrity (Option A)')).toBeVisible();
    await expect(page.locator('text=Hallucination / Ungrounded Claim Rate')).toBeVisible();
    await expect(page.locator('text=Prompt Injection Defense Rate')).toBeVisible();

    // Verify methodology disclosure cards
    await expect(page.locator('text=Primary Benchmark LLM Provider')).toBeVisible();
    await expect(page.locator('text=MockLLMProvider')).toBeVisible();

    await expect(page.locator('text=Production-Realistic Latency (Cloud LLM Reference)')).toBeVisible();
    await expect(page.locator('text=Claude 3.5 Sonnet')).toBeVisible();
    await expect(page.locator('text=~1,200ms – 2,500ms')).toBeVisible();

    // Verify IR quality card
    await expect(page.locator('text=Information Retrieval Quality (Knowledge Backbone Evaluation)')).toBeVisible();
    await expect(page.locator('text=Precision@5')).toBeVisible();
    await expect(page.locator('text=Recall@5')).toBeVisible();
    await expect(page.locator('text=Mean Reciprocal Rank (MRR)')).toBeVisible();
  });
});
