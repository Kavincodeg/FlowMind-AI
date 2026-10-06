import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';
import { getPlainStatusLabel } from './HomeView';
import { HashIcon, RefreshIcon, AlertTriangleIcon, ArrowRightIcon, ClockIcon } from './Icons';
import { ExecutionOutcome } from './ExecutionOutcome';
import type { WorkflowInstance } from '../types';

export const CaseDetailView: React.FC = () => {
  const { workflowId } = useParams<{ workflowId: string }>();
  const { activePersona } = useAppContext();

  const [workflow, setWorkflow] = useState<WorkflowInstance | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    if (workflowId && activePersona) {
      setIsLoading(true);
      setError(null);
      api
        .getWorkflowDetails(workflowId, activePersona.token)
        .then((data) => {
          if (!isMounted) return;
          setWorkflow(data);
        })
        .catch((err) => {
          if (!isMounted) return;
          setError(err instanceof Error ? err.message : `Could not load case ${workflowId}`);
        })
        .finally(() => {
          if (!isMounted) return;
          setIsLoading(false);
        });
    }
    return () => {
      isMounted = false;
    };
  }, [workflowId, activePersona]);

  if (isLoading) {
    return (
      <div className="console-panel" style={{ padding: '3rem 1.5rem', textAlign: 'center', maxWidth: '850px', margin: '2rem auto' }}>
        <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-secondary)' }}>
          <RefreshIcon size={18} />
          <span>Loading case timeline for {workflowId}...</span>
        </div>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="console-panel" style={{ padding: '2rem', maxWidth: '800px', margin: '2rem auto' }}>
        <div className="alert-banner alert-danger">
          <AlertTriangleIcon size={16} />
          <span>{error || `Case ${workflowId} could not be found.`}</span>
        </div>
        <div style={{ marginTop: '1rem', display: 'flex', gap: '0.75rem' }}>
          <Link to="/cases" className="btn btn-secondary">
            &larr; Back to Past Cases
          </Link>
          <Link to="/investigate" className="btn btn-primary">
            Look into a new case
          </Link>
        </div>
      </div>
    );
  }

  const statusInfo = getPlainStatusLabel(workflow.status);
  const reasoning = workflow.reasoning;

  return (
    <div style={{ maxWidth: '960px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Breadcrumb navigation */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.75rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          <Link to="/home" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
            Home
          </Link>
          <span>/</span>
          <Link to="/cases" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
            Past Cases
          </Link>
          <span>/</span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Case {workflow.workflow_id}</span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Link
            to={`/investigate/${workflow.workflow_id}`}
            className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', textDecoration: 'none' }}
          >
            Investigation Console
          </Link>
          <Link
            to={`/trust/${workflow.workflow_id}`}
            className="btn btn-primary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
          >
            <HashIcon size={14} /> View Cryptographic Audit Record
          </Link>
        </div>
      </div>

      {/* Case Overview Header Panel */}
      <div
        className="console-panel"
        style={{
          padding: '1.75rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          backgroundColor: 'var(--bg-surface-elevated)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Case {workflow.workflow_id}
            </h1>
            <span className={`badge ${statusInfo.badgeClass}`} style={{ fontSize: '0.75rem' }}>
              {statusInfo.label}
            </span>
          </div>
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)', marginTop: '0.35rem' }}>
            Started: {new Date(workflow.started_at).toLocaleString()} &bull; State: {workflow.status}
          </div>
        </div>

        {workflow.status === 'PENDING_APPROVAL' && (
          <Link
            to={`/investigate/${workflow.workflow_id}/decide`}
            className="btn btn-warning"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontWeight: 600, textDecoration: 'none' }}
          >
            <ClockIcon size={14} /> Review &amp; Decide Now &rarr;
          </Link>
        )}
      </div>

      {/* Customer Complaint Details */}
      <div className="console-panel" style={{ padding: '1.5rem' }}>
        <div className="panel-title" style={{ marginBottom: '0.75rem' }}>
          Customer Complaint &amp; Input
        </div>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>Customer ID</span>
            <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{workflow.request?.customer_id}</strong>
          </div>
          <div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>Customer Name</span>
            <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)' }}>{workflow.request?.customer_name}</strong>
          </div>
        </div>

        <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)', display: 'block' }}>What did the customer say?</span>
          <p style={{ margin: '0.3rem 0 0 0', fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: 1.5 }}>
            {workflow.request?.issue_summary}
          </p>
        </div>
      </div>

      {/* Status & Lifecycle Timeline */}
      <div className="console-panel" style={{ padding: '1.5rem' }}>
        <div className="panel-title" style={{ marginBottom: '1rem' }}>
          Case Lifecycle &amp; Reasoning Timeline
        </div>

        <div className="timeline-list">
          <div className="timeline-item">
            <div className="timeline-marker">
              <div className="timeline-node done">1</div>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">1. Evidence Retrieval &amp; Policy Checking</div>
              <div className="timeline-desc">
                {reasoning?.citations && reasoning.citations.length > 0
                  ? `Retrieved ${reasoning.citations.length} evidence records from company policies and tickets.`
                  : 'Retrieved evidence from knowledge backbone.'}
              </div>
            </div>
          </div>

          <div className="timeline-item">
            <div className="timeline-marker">
              <div className={`timeline-node ${reasoning ? 'done' : ''}`}>2</div>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">2. Contextual Root Cause &amp; Recommendation</div>
              <div className="timeline-desc">
                {reasoning?.root_cause ? (
                  <>
                    <strong style={{ color: 'var(--text-primary)', display: 'block', marginBottom: '0.2rem' }}>
                      {reasoning.root_cause}
                    </strong>
                    {reasoning.rationale && <span>{reasoning.rationale}</span>}
                  </>
                ) : (
                  'Root cause evaluation complete.'
                )}
              </div>
            </div>
          </div>

          <div className="timeline-item">
            <div className="timeline-marker">
              <div className={`timeline-node ${reasoning?.indirect_injection_detected ? 'active' : 'done'}`}>3</div>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">3. Security &amp; Indirect Injection Guardrail</div>
              <div className="timeline-desc">
                {reasoning?.indirect_injection_detected ? (
                  <span style={{ color: 'var(--status-danger-text)', fontWeight: 600 }}>
                    Adversarial prompt injection detected. Safety containment triggered.
                  </span>
                ) : (
                  <span style={{ color: 'var(--status-success-text)' }}>
                    Safety check passed. No deceptive instructions detected.
                  </span>
                )}
              </div>
            </div>
          </div>

          <div className="timeline-item">
            <div className="timeline-marker">
              <div className={`timeline-node ${workflow.completed_at || workflow.execution_record ? 'done' : 'active'}`}>4</div>
            </div>
            <div className="timeline-content">
              <div className="timeline-heading">4. Governance Decision &amp; Action Outcome</div>
              <div className="timeline-desc">
                Status: <strong style={{ color: 'var(--text-primary)' }}>{statusInfo.label}</strong>
                {workflow.approval_record && (
                  <div style={{ marginTop: '0.4rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    Decision: <strong>{workflow.approval_record.decision}</strong> by {workflow.approval_record.approver_id} ({workflow.approval_record.approver_role})
                    {workflow.approval_record.rejection_reason && (
                      <div style={{ color: 'var(--status-danger-text)', marginTop: '0.2rem' }}>
                        Rejection reason: {workflow.approval_record.rejection_reason}
                      </div>
                    )}
                    {workflow.approval_record.comments && (
                      <div style={{ marginTop: '0.2rem' }}>
                        Notes: {workflow.approval_record.comments}
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Execution Outcome card if connector executed */}
      {workflow.execution_record && (
        <ExecutionOutcome execution={workflow.execution_record} />
      )}

      {/* Link to Audit Record */}
      <div
        className="console-panel"
        style={{
          padding: '1.25rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
          backgroundColor: 'var(--bg-surface-elevated)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <HashIcon size={20} />
          <div>
            <strong style={{ fontSize: '0.9rem', color: 'var(--text-primary)', display: 'block' }}>
              Cryptographic SHA-256 Audit Record
            </strong>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Inspect the immutable hash chain, block sequence, and independent server-side verification.
            </span>
          </div>
        </div>

        <Link
          to={`/trust/${workflow.workflow_id}`}
          className="btn btn-primary"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', textDecoration: 'none' }}
        >
          <span>Inspect Hash Chain</span>
          <ArrowRightIcon size={14} />
        </Link>
      </div>
    </div>
  );
};
