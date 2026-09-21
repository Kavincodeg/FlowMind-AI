import React, { useState } from 'react';
import type { DemonstrationScenario, Persona, WorkflowInstance } from '../types';
import { api } from '../api';
import { EvidenceDrawer } from './EvidenceDrawer';
import { ApprovalGate } from './ApprovalGate';
import { SearchIcon, ShieldIcon, AlertTriangleIcon } from './Icons';

interface InvestigationConsoleProps {
  scenarios: DemonstrationScenario[];
  activePersona: Persona;
  workflow: WorkflowInstance | null;
  onWorkflowUpdated: (instance: WorkflowInstance) => void;
}

export const InvestigationConsole: React.FC<InvestigationConsoleProps> = ({
  scenarios,
  activePersona,
  workflow,
  onWorkflowUpdated,
}) => {
  const [selectedScenarioId, setSelectedScenarioId] = useState<string>('CASE-001');
  const [customerId, setCustomerId] = useState('CUST-4091');
  const [customerName, setCustomerName] = useState('Sarah Lin');
  const [issueSummary, setIssueSummary] = useState(
    'Customer was charged twice for their monthly enterprise subscription renewal ($499 x 2). Requesting immediate refund of the duplicate charge and priority escalation.'
  );
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSelectScenario = (scenario: DemonstrationScenario) => {
    setSelectedScenarioId(scenario.id);
    setCustomerId(scenario.customer_id);
    setCustomerName(scenario.customer_name);
    setIssueSummary(scenario.issue_summary);
    setError(null);
  };

  const handleRunInvestigation = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!issueSummary.trim()) return;

    setIsLoading(true);
    setError(null);

    try {
      const result = await api.investigateComplaint(
        {
          customer_id: customerId.trim() || 'CUST-AUTO',
          customer_name: customerName.trim() || 'Valued Customer',
          issue_summary: issueSummary.trim(),
        },
        activePersona.token
      );
      onWorkflowUpdated(result);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Could not complete case review.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const reasoning = workflow?.reasoning;

  return (
    <div className="investigation-grid">
      {/* 1. Request Input & Example Scenarios Column */}
      <div className="console-panel">
        <div className="panel-header">
          <div className="panel-title">
            <SearchIcon size={16} /> Look into a Customer Case
          </div>
        </div>

        {/* Quick Example Scenarios */}
        <div className="scenarios-container">
          <span className="scenarios-label">Try an example case:</span>
          {scenarios.map((sc) => (
            <button
              key={sc.id}
              type="button"
              className={`scenario-card ${selectedScenarioId === sc.id ? 'active' : ''}`}
              onClick={() => handleSelectScenario(sc)}
            >
              <div className="scenario-card-header">
                <span className="scenario-title">{sc.title}</span>
                <span className="badge badge-neutral" style={{ fontSize: '0.65rem' }}>
                  {sc.id}
                </span>
              </div>
              <div className="scenario-category" style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                {sc.category}
              </div>
              <div style={{ marginTop: '0.35rem' }}>
                <span
                  className={`badge ${
                    sc.badge.includes('Team Lead')
                      ? 'badge-warning'
                      : sc.badge.includes('Abstention')
                      ? 'badge-danger'
                      : 'badge-success'
                  }`}
                  style={{ fontSize: '0.65rem' }}
                >
                  {sc.badge}
                </span>
              </div>
            </button>
          ))}
        </div>

        <form
          onSubmit={handleRunInvestigation}
          style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', marginTop: '0.65rem' }}
        >
          <div className="form-group">
            <label className="form-label" htmlFor="issue-summary" style={{ fontSize: '0.875rem', fontWeight: 600 }}>
              What did the customer say?
            </label>
            <textarea
              id="issue-summary"
              className="form-textarea"
              rows={4}
              placeholder="Paste or type the customer's message, email, or complaint here..."
              value={issueSummary}
              onChange={(e) => setIssueSummary(e.target.value)}
              required
            />
            <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              We'll check our company policies and past tickets to see what happened and what to do next.
            </span>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem' }}>
            <div className="form-group">
              <label className="form-label" htmlFor="customer-id">
                Customer ID
              </label>
              <input
                id="customer-id"
                type="text"
                className="form-input"
                value={customerId}
                onChange={(e) => setCustomerId(e.target.value)}
                required
              />
            </div>

            <div className="form-group">
              <label className="form-label" htmlFor="customer-name">
                Customer Name
              </label>
              <input
                id="customer-name"
                type="text"
                className="form-input"
                value={customerName}
                onChange={(e) => setCustomerName(e.target.value)}
                required
              />
            </div>
          </div>

          {error && (
            <div className="alert-banner alert-danger">
              <AlertTriangleIcon size={14} />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            id="btn-run-investigation"
            className="btn btn-primary"
            disabled={isLoading || !issueSummary.trim()}
            style={{ fontWeight: 600, padding: '0.65rem 1rem' }}
          >
            {isLoading ? 'Looking into what happened...' : 'Look into what happened'}
          </button>
        </form>
      </div>

      {/* 2. What we found & Timeline Column */}
      <div className="console-panel">
        <div className="panel-header">
          <div className="panel-title">
            <ShieldIcon size={16} /> What we found
          </div>
          {workflow && (
            <span className="hash-pill" style={{ color: 'var(--text-secondary)' }}>
              Case WF: {workflow.workflow_id}
            </span>
          )}
        </div>

        {/* Plain Step Tracker Timeline */}
        <div className="timeline-list">
          <div className="timeline-item">
            <div className="timeline-marker">
              <div className={`timeline-node ${workflow ? 'done' : isLoading ? 'active' : ''}`}>1</div>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">
                1. Evidence Retrieval — Checking past cases &amp; company guides
              </div>
              <div className="timeline-desc">
                {workflow?.reasoning?.citations && workflow.reasoning.citations.length > 0
                  ? `Found ${workflow.reasoning.citations.length} relevant records in company policies and past tickets.`
                  : 'Checks our knowledge base for similar tickets and official company rules.'}
              </div>
            </div>
          </div>

          <div className="timeline-item">
            <div className="timeline-marker">
              <div
                className={`timeline-node ${
                  reasoning?.status === 'grounded' ? 'done' : reasoning?.status === 'abstained' ? 'active' : ''
                }`}
              >
                2
              </div>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">
                2. Contextual Root Cause — What we think is going on
              </div>
              <div className="timeline-desc">
                {reasoning?.root_cause ? (
                  <strong style={{ color: 'var(--text-primary)' }}>{reasoning.root_cause}</strong>
                ) : (
                  'Explains what caused the issue, using only verified facts from the retrieved records.'
                )}
              </div>
            </div>
          </div>

          <div className="timeline-item">
            <div className="timeline-marker">
              <div
                className={`timeline-node ${
                  reasoning?.indirect_injection_detected
                    ? 'active'
                    : reasoning
                    ? 'done'
                    : ''
                }`}
              >
                3
              </div>
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">
                3. Security &amp; Indirect Injection Guardrail — Safety check
              </div>
              <div className="timeline-desc">
                {reasoning?.indirect_injection_detected ? (
                  <span style={{ color: 'var(--status-danger-text)', fontWeight: 600 }}>
                    Adversarial prompt injection detected in retrieved text. Warning: This message tried to bypass normal checks. A person must review this carefully before taking any action.
                  </span>
                ) : reasoning ? (
                  <span style={{ color: 'var(--status-success-text)' }}>
                    Safety check passed. No deceptive instructions or attempt to bypass rules detected.
                  </span>
                ) : (
                  'Scans for deceptive messages or attempts to trick the system into breaking policy.'
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Root Cause & Recommendation Summary Card */}
        {reasoning?.root_cause && (
          <div
            style={{
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
              padding: '0.85rem 1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div>
              <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                What we think is going on
              </div>
              <div style={{ fontSize: '0.875rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                {reasoning.root_cause}
              </div>
            </div>

            {reasoning.rationale && (
              <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45, borderTop: '1px solid var(--border-subtle)', paddingTop: '0.4rem' }}>
                <strong style={{ color: 'var(--text-muted)' }}>Explanation: </strong>
                {reasoning.rationale}
              </div>
            )}
          </div>
        )}

        {/* Expandable Evidence Drawer */}
        <EvidenceDrawer
          citations={reasoning?.citations || []}
          groundingStatus={reasoning?.status || null}
          abstentionReason={reasoning?.abstention_reason || null}
        />
      </div>

      {/* 3. Review & Decide Column */}
      {workflow ? (
        <ApprovalGate
          workflow={workflow}
          activePersona={activePersona}
          onWorkflowUpdated={onWorkflowUpdated}
        />
      ) : (
        <div className="console-panel">
          <div className="panel-header">
            <div className="panel-title">
              <ShieldIcon size={16} /> Review &amp; Decide
            </div>
            <span className="badge badge-neutral">Ready for next case</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '2.5rem 1rem', textAlign: 'center', lineHeight: 1.5 }}>
            Type what the customer said on the left to see what we find and review recommended actions.
          </div>
        </div>
      )}
    </div>
  );
};
