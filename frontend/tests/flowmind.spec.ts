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

    // Save screenshot of initial state
    await page.screenshot({ path: 'screenshots/1_initial_load.png', fullPage: true });
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

    // Save screenshot of scenario selection
    await page.screenshot({ path: 'screenshots/2_scenario_selected.png', fullPage: true });
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

    // Save screenshot of investigation pipeline
    await page.screenshot({ path: 'screenshots/3_investigation_result.png', fullPage: true });
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

    // Save screenshot of persona switching
    await page.screenshot({ path: 'screenshots/4_persona_switching.png', fullPage: true });
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

    // Save screenshot of audit trail explorer
    await page.screenshot({ path: 'screenshots/5_audit_trail_explorer.png', fullPage: true });
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

    // Save screenshot of benchmarks dashboard
    await page.screenshot({ path: 'screenshots/6_empirical_benchmarks.png', fullPage: true });
  });

  test('7. Human Governance — Action Approval & Mock Connector Execution Outcome', async ({ page }) => {
    // Switch to Elena Rostova (Manager, USR-003) authorized for financial refund recommendations
    const personaSelect = page.locator('header select');
    await personaSelect.selectOption('USR-003');
    await expect(page.locator('header .badge')).toHaveText(/manager/i);

    // Select CASE-001 (Recurring Double Billing)
    await page.locator('.scenario-card', { hasText: 'CASE-001' }).click();

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await submitBtn.click();
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Verify Approval Gate is in PENDING_APPROVAL state
    await expect(page.locator('#btn-approve-action')).toBeVisible();
    await expect(page.locator('#btn-reject-action')).toBeVisible();
    await expect(page.locator('text=ISSUE_REFUND_RECOMMENDATION')).toBeVisible();

    // Add reviewer rationale into decision notes
    await page.locator('#decision-notes').fill('Verified duplicate charge on billing connector; approving refund recommendation.');

    // Approve the action
    await page.locator('#btn-approve-action').click();

    // Verify workflow state transitions to APPROVED_EXECUTED
    await expect(page.locator('.badge', { hasText: 'APPROVED_EXECUTED' })).toBeVisible({ timeout: 10000 });

    // Verify Mock Connector Execution Outcome card appears with details
    await expect(page.locator('text=Action Executed via Mock Connector')).toBeVisible();
    await expect(page.locator('.badge-success', { hasText: 'SUCCESS' })).toBeVisible();
    await expect(page.locator('text=Target System:')).toBeVisible();
    await expect(page.locator('text=Generated ID:')).toBeVisible();

    // Save screenshot of successful execution
    await page.screenshot({ path: 'screenshots/7_approval_execution_success.png', fullPage: true });
  });

  test('8. Human Governance — RBAC Permission Boundary Enforcement & Role Recovery', async ({ page }) => {
    // Step 1: Switch to Sarah Jenkins (Support Agent, USR-001) who lacks financial refund authorization
    const personaSelect = page.locator('header select');
    await personaSelect.selectOption('USR-001');
    await expect(page.locator('header .badge')).toHaveText(/support_agent/i);

    // Select CASE-001 (Requires Manager or above)
    await page.locator('.scenario-card', { hasText: 'CASE-001' }).click();

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await submitBtn.click();
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Step 2: Attempt approval as Support Agent
    await expect(page.locator('#btn-approve-action')).toBeVisible();
    await page.locator('#btn-approve-action').click();

    // Step 3: Assert RBAC boundary error banner is rendered
    await expect(page.locator('.alert-banner.alert-danger')).toBeVisible();
    await expect(page.locator('text=Authorization Boundary Enforced')).toBeVisible();
    await expect(page.locator("text=Current role 'support_agent' lacks authorization")).toBeVisible();

    // Step 4: Role Elevation Recovery - Switch to Elena Rostova (Manager, USR-003)
    await personaSelect.selectOption('USR-003');
    await expect(page.locator('header .badge')).toHaveText(/manager/i);

    // Re-attempt approval with authorized role
    await page.locator('#btn-approve-action').click();

    // Assert successful approval and execution
    await expect(page.locator('.badge', { hasText: 'APPROVED_EXECUTED' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Action Executed via Mock Connector')).toBeVisible();

    // Save screenshot of RBAC boundary and recovery
    await page.screenshot({ path: 'screenshots/8_rbac_boundary_recovery.png', fullPage: true });
  });

  test('9. Human Governance — Action Rejection with Reviewer Audit Rationale', async ({ page }) => {
    // Select CASE-001 (Recurring Double Billing, pending approval)
    await page.locator('.scenario-card', { hasText: 'CASE-001' }).click();

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await submitBtn.click();
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Verify rejection button is available
    await expect(page.locator('#btn-reject-action')).toBeVisible();

    // Provide explicit audit rejection note
    const rejectionReason = 'Declined refund escalation: customer already reimbursed under prior transaction.';
    await page.locator('#decision-notes').fill(rejectionReason);

    // Reject the action
    await page.locator('#btn-reject-action').click();

    // Verify REJECTED status banner appears
    await expect(page.locator('.badge', { hasText: 'REJECTED' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Action Rejected by Human Governance')).toBeVisible();
    await expect(page.locator(`text=${rejectionReason}`)).toBeVisible();

    // Verify approve/reject buttons are no longer rendered
    await expect(page.locator('#btn-approve-action')).not.toBeVisible();

    // Save screenshot of rejected state
    await page.screenshot({ path: 'screenshots/9_action_rejection.png', fullPage: true });
  });

  test('10. Human Governance — Parameter Modification and Custom Override', async ({ page }) => {
    // Switch to Elena Rostova (Manager, USR-003) authorized for financial refund recommendations
    const personaSelect = page.locator('header select');
    await personaSelect.selectOption('USR-003');
    await expect(page.locator('header .badge')).toHaveText(/manager/i);

    // Select CASE-001
    await page.locator('.scenario-card', { hasText: 'CASE-001' }).click();

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await submitBtn.click();
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Click 'Modify Parameters'
    const modifyBtn = page.locator('#btn-modify-action');
    await expect(modifyBtn).toBeVisible();
    await modifyBtn.click();

    // Assert parameter JSON textarea is revealed
    const paramTextarea = page.locator('#modified-parameters-textarea');
    await expect(paramTextarea).toBeVisible();

    // Verify confirm button text
    await expect(modifyBtn).toHaveText('Confirm Modified Action');

    // Provide reviewer notes
    await page.locator('#decision-notes').fill('Adjusted refund parameters under discretionary customer courtesy credit policy.');

    // Submit modified approval
    await modifyBtn.click();

    // Verify execution outcome succeeds
    await expect(page.locator('.badge', { hasText: 'APPROVED_EXECUTED' })).toBeVisible({ timeout: 10000 });
    await expect(page.locator('text=Action Executed via Mock Connector')).toBeVisible();

    // Save screenshot of parameter modification
    await page.screenshot({ path: 'screenshots/10_action_modification.png', fullPage: true });
  });

  test('11. Security Guardrail — Adversarial Prompt Injection Defense & Containment', async ({ page }) => {
    // Select CASE-013 (Prompt Injection attack: "SYSTEM OVERRIDE: Ignore all previous instructions...")
    await page.locator('.scenario-card', { hasText: 'CASE-013' }).click();

    // Verify scenario loaded into textarea
    await expect(page.locator('#issue-summary')).toContainText('SYSTEM OVERRIDE');

    // Run investigation
    const submitBtn = page.locator('#btn-run-investigation');
    await submitBtn.click();
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Verify timeline step 3 detected indirect prompt injection
    await expect(page.locator('text=Adversarial prompt injection detected in retrieved text')).toBeVisible();

    // Verify security rationale notes injection disregarded
    await expect(page.locator('text=Security Notice: Adversarial prompt instructions were detected').first()).toBeVisible();

    // Verify Approval Gate is presented with containment
    await expect(page.locator('#btn-approve-action')).toBeVisible();

    // Save screenshot of security injection detection
    await page.screenshot({ path: 'screenshots/11_prompt_injection_defense.png', fullPage: true });
  });

  test('12. Evidence Citation Drawer — Collapsible Excerpt Interactivity & Verification', async ({ page }) => {
    // Run investigation on CASE-001
    await page.locator('.scenario-card', { hasText: 'CASE-001' }).click();
    const submitBtn = page.locator('#btn-run-investigation');
    await submitBtn.click();
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Verify Evidence Drawer header and grounding badge
    await expect(page.locator('text=Retrieved Grounding Evidence')).toBeVisible();
    await expect(page.locator('text=Grounded in Retrieved Sources')).toBeVisible();

    // Locate the first citation card
    const firstCitation = page.locator('.citation-card').first();
    await expect(firstCitation).toBeVisible();

    // Verify cosine similarity indicator
    await expect(firstCitation.locator('.citation-score')).toContainText('Sim:');

    // Click 'Expand Excerpt'
    const toggleBtn = firstCitation.locator('button', { hasText: 'Expand Excerpt' });
    await expect(toggleBtn).toBeVisible();
    await toggleBtn.click();

    // Verify button text changes to 'Collapse'
    await expect(firstCitation.locator('button', { hasText: 'Collapse' })).toBeVisible();

    // Click 'Collapse' to restore
    await firstCitation.locator('button', { hasText: 'Collapse' }).click();
    await expect(firstCitation.locator('button', { hasText: 'Expand Excerpt' })).toBeVisible();

    // Save screenshot of interactive evidence drawer
    await page.screenshot({ path: 'screenshots/12_evidence_drawer_interactive.png', fullPage: true });
  });

  test('13. Manual Custom Complaint Input & Reactive Form Validation', async ({ page }) => {
    // Test reactive validation: clearing the issue summary should disable the submit button
    const issueTextarea = page.locator('#issue-summary');
    await issueTextarea.fill('');
    const submitBtn = page.locator('#btn-run-investigation');
    await expect(submitBtn).toBeDisabled();

    // Enter a custom enterprise IT complaint
    await page.locator('#customer-id').fill('CUST-7712');
    await page.locator('#customer-name').fill('Dr. Robert Vance');
    await issueTextarea.fill('Enterprise SSO authentication timeout impacting 200 engineers after IdP certificate renewal.');

    // Submit button should now be enabled
    await expect(submitBtn).toBeEnabled();
    await submitBtn.click();

    // Wait for investigation pipeline
    await expect(submitBtn).not.toHaveText('Retrieving & Reasoning...', { timeout: 15000 });

    // Verify workflow instance ID was assigned
    await expect(page.locator('text=WF:')).toBeVisible();

    // Verify reasoning timeline stepped through evidence retrieval
    await expect(page.locator('text=1. Evidence Retrieval')).toBeVisible();
    await expect(page.locator('text=2. Contextual Root Cause')).toBeVisible();

    // Save screenshot of custom complaint workflow
    await page.screenshot({ path: 'screenshots/13_custom_complaint_investigation.png', fullPage: true });
  });

  test('14. Cryptographic SHA-256 Audit Trail — Deep Chain Linkage & Navigation', async ({ page }) => {
    // Navigate to Audit Explorer tab
    await page.locator('nav button', { hasText: 'Cryptographic Audit Trail' }).click();

    // Verify explorer header and status
    await expect(page.locator('text=Cryptographic SHA-256 Hash Chain Inspector')).toBeVisible();

    const auditButtons = page.locator('.scenario-card');
    const count = await auditButtons.count();
    expect(count).toBeGreaterThan(1);

    // Click the second audit run in the list
    await auditButtons.nth(1).click();

    // Verify cryptographic integrity badge
    await expect(page.locator('text=Cryptographic Chain Verified (Intact)')).toBeVisible();

    // Verify summary metrics row
    await expect(page.locator('text=Audit Record ID')).toBeVisible();
    await expect(page.locator('text=Terminal State')).toBeVisible();
    await expect(page.locator('text=End-to-End Latency')).toBeVisible();
    await expect(page.locator('text=Recorded Events')).toBeVisible();

    // Verify sequenced blocks and hash linkage
    await expect(page.locator('text=Sequenced Audit Blocks (SHA-256 Parent Hash Linkage)')).toBeVisible();
    await expect(page.locator('text=BLOCK #1')).toBeVisible();
    await expect(page.locator('text=Current Hash:').first()).toBeVisible();
    await expect(page.locator('text=Parent Hash:').first()).toBeVisible();

    // Save screenshot of deep audit block inspection
    await page.screenshot({ path: 'screenshots/14_audit_deep_inspection.png', fullPage: true });
  });
});
