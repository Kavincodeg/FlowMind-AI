import React, { useState } from 'react';
import type { DemonstrationScenario, Persona, WorkflowInstance } from '../types';
import { api } from '../api';
import { EvidenceDrawer } from './EvidenceDrawer';
import { ApprovalGate } from './ApprovalGate';
import { SearchIcon, ShieldIcon, AlertTriangleIcon, CpuIcon } from './Icons';

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
        setError('Investigation pipeline failed.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  const reasoning = workflow?.reasoning;

  return (
    <div className="investigation-grid">
      {/* 1. Request Input & Scenarios Column */}
      <div className="console-panel">
        <div className="panel-header">
          <div className="panel-title">
            <SearchIcon size={16} /> Customer Complaint Request
          </div>
        </div>

        <div className="scenarios-container">
          <span className="scenarios-label">Preset Benchmark Scenarios</span>
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
              <div className="scenario-category">{sc.category}</div>
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

        <form onSubmit={handleRunInvestigation} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '0.5rem' }}>
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

          <div className="form-group">
            <label className="form-label" htmlFor="issue-summary">
              Complaint Details / Operational Request
            </label>
            <textarea
              id="issue-summary"
              className="form-textarea"
              rows={4}
              value={issueSummary}
              onChange={(e) => setIssueSummary(e.target.value)}
              required
            />
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
          >
            {isLoading ? 'Retrieving & Reasoning...' : 'Run Investigation & Reasoning'}
          </button>
        </form>
      </div>

      {/* 2. Reasoning & Evidence Column */}
      <div className="console-panel">
        <div className="panel-header">
          <div className="panel-title">
            <CpuIcon size={16} /> Evidence-Grounded Reasoning
          </div>
          {workflow && (
            <span className="hash-pill" style={{ color: 'var(--text-secondary)' }}>
              WF: {workflow.workflow_id}
            </span>
          )}
        </div>

        {/* Step Progression Timeline */}
        <div className="timeline-list">
          <div className="timeline-item">
            <div className="timeline-marker">
              <div className={`timeline-node ${workflow ? 'done' : isLoading ? 'active' : ''}`}>1</div>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">1. Evidence Retrieval (ChromaDB / pgvector)</div>
              <div className="timeline-desc">
                {workflow?.reasoning?.citations
                  ? `Retrieved ${workflow.reasoning.citations.length} grounded chunks matching customer history & policies.`
                  : 'Awaiting complaint submission to execute vector similarity search.'}
              </div>
            </div>
          </div>

          <div className="timeline-item">
            <div className="timeline-marker">
              <div className={`timeline-node ${reasoning?.status === 'grounded' ? 'done' : reasoning?.status === 'abstained' ? 'active' : ''}`}>2</div>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">2. Contextual Root Cause & Grounding Check</div>
              <div className="timeline-desc">
                {reasoning?.root_cause
                  ? `Root Cause Identified: ${reasoning.root_cause}`
                  : 'Verifies claims exclusively against retrieved evidence to prevent hallucinations.'}
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
              <div className="timeline-heading">3. Security & Indirect Injection Guardrail</div>
              <div className="timeline-desc">
                {reasoning?.indirect_injection_detected ? (
                  <span style={{ color: 'var(--status-danger-text)', fontWeight: 600 }}>
                    Adversarial prompt injection detected in retrieved text. Action blocked; abstention enforced.
                  </span>
                ) : reasoning ? (
                  <span style={{ color: 'var(--status-success-text)' }}>
                    Security scan clean. No prompt injection or system override tokens detected.
                  </span>
                ) : (
                  'Scans context for jailbreaks, system command overrides, or credential exfiltration.'
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Detailed Rationale Box */}
        {reasoning?.rationale && (
          <div
            style={{
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.4rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                Synthesized Rationale
              </span>
              {typeof reasoning.confidence_score === 'number' && (
                <span className="badge badge-success" style={{ fontFamily: 'var(--font-mono)' }}>
                  Confidence: {Math.round(reasoning.confidence_score * 100)}%
                </span>
              )}
            </div>
            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              {reasoning.rationale}
            </div>
          </div>
        )}

        {/* Expandable Evidence Drawer */}
        <EvidenceDrawer
          citations={reasoning?.citations || []}
          groundingStatus={reasoning?.status || null}
          abstentionReason={reasoning?.abstention_reason || null}
        />
      </div>

      {/* 3. Human Governance & Execution Column */}
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
              <ShieldIcon size={16} /> Human Governance & Approval Gate
            </div>
            <span className="badge badge-neutral">IDLE</span>
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '2rem 0', textAlign: 'center' }}>
            Submit an investigation on the left to initiate evidence-grounded action gating.
          </div>
        </div>
      )}
    </div>
  );
};
