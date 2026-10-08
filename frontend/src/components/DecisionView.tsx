import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';
import { ApprovalGate } from './ApprovalGate';
import { HashIcon, AlertTriangleIcon } from './Icons';
import { LoadingState } from './ui';
import type { WorkflowInstance } from '../types';
import { formatDateTime, statusLabel } from '../types';

export const DecisionView: React.FC = () => {
  const { workflowId } = useParams<{ workflowId: string }>();
  const { activePersona, currentWorkflow, setCurrentWorkflow } = useAppContext();

  const [workflow, setWorkflow] = useState<WorkflowInstance | null>(
    currentWorkflow?.workflow_id === workflowId ? currentWorkflow : null
  );
  const [isLoading, setIsLoading] = useState(!workflow);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    if (workflowId && (!workflow || workflow.workflow_id !== workflowId)) {
      if (!activePersona) return;
      setIsLoading(true);
      setError(null);
      api
        .getWorkflowDetails(workflowId, activePersona.token)
        .then((fetched) => {
          if (!isMounted) return;
          setWorkflow(fetched);
          setCurrentWorkflow(fetched);
        })
        .catch((err) => {
          if (!isMounted) return;
          setError(err instanceof Error ? err.message : `Failed to load case ${workflowId}`);
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

  if (!activePersona) {
    return (
      <div className="page-container" style={{ maxWidth: '800px' }}>
        <div className="console-panel" style={{ padding: 'var(--space-8)', textAlign: 'center' }}>
          Please select a team persona to review cases.
        </div>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="page-container" style={{ maxWidth: '800px' }}>
        <div className="console-panel">
          <LoadingState message={`Loading case decision details for ${workflowId}...`} />
        </div>
      </div>
    );
  }

  if (error || !workflow) {
    return (
      <div className="page-container" style={{ maxWidth: '800px' }}>
        <div className="console-panel" style={{ padding: 'var(--space-6)' }}>
          <div className="alert-banner alert-danger">
            <AlertTriangleIcon size={16} />
            <span>{error || `Case ${workflowId} could not be found.`}</span>
          </div>
          <div style={{ marginTop: 'var(--space-4)', display: 'flex', gap: 'var(--space-3)' }}>
            <Link to="/home" className="btn btn-secondary">
              Return to Home
            </Link>
            <Link to="/investigate" className="btn btn-primary">
              Start a new case
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-container" style={{ maxWidth: '960px' }}>
      {/* Top breadcrumb & navigation bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-3)',
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', fontSize: 'var(--text-sm)', color: 'var(--text-muted)' }}>
          <Link to="/home" style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
            Home
          </Link>
          <span>/</span>
          <Link to={`/investigate/${workflow.workflow_id}`} style={{ color: 'var(--text-secondary)', textDecoration: 'none' }}>
            Investigation ({workflow.workflow_id})
          </Link>
          <span>/</span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>Review &amp; Decision Gate</span>
        </div>

        <div style={{ display: 'flex', gap: '0.5rem' }}>
          <Link
            to={`/investigate/${workflow.workflow_id}`}
            className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', textDecoration: 'none' }}
          >
            &larr; View Evidence &amp; Timeline
          </Link>
          <Link
            to={`/trust/${workflow.workflow_id}`}
            className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
          >
            <HashIcon size={12} /> Audit Trail
          </Link>
        </div>
      </div>

      {/* Case Context Summary Card */}
      <div
        className="console-panel"
        style={{
          padding: '1.25rem 1.5rem',
          display: 'flex',
          flexDirection: 'column',
          gap: '0.75rem',
          backgroundColor: 'var(--bg-surface-elevated)',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <div style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
              Case Context &amp; Customer Information
            </div>
            <h2 style={{ fontSize: '1.2rem', fontWeight: 700, margin: '0.2rem 0', color: 'var(--text-primary)' }}>
              Case {workflow.workflow_id}
            </h2>
          </div>
          <span className="hash-pill">
            Started: {formatDateTime(workflow.started_at)}
          </span>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: '0.75rem', fontSize: '0.85rem' }}>
          <div>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>Customer</span>
            <strong style={{ color: 'var(--text-primary)' }}>
              {workflow.request?.customer_name || 'Valued Customer'} ({workflow.request?.customer_id})
            </strong>
          </div>
          <div>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>Current Status</span>
            <strong style={{ color: 'var(--text-primary)' }}>{statusLabel(workflow.status)}</strong>
          </div>
        </div>

        {workflow.request?.issue_summary && (
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.6rem' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>
              What did the customer say?
            </span>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
              {workflow.request.issue_summary}
            </p>
          </div>
        )}

        {workflow.reasoning?.root_cause && (
          <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.6rem' }}>
            <span style={{ color: 'var(--text-muted)', fontSize: '0.75rem', display: 'block' }}>
              What we think is going on (Root Cause)
            </span>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-primary)', fontWeight: 500, lineHeight: 1.45 }}>
              {workflow.reasoning.root_cause}
            </p>
          </div>
        )}
      </div>

      {/* Primary Approval Gate */}
      <ApprovalGate
        workflow={workflow}
        activePersona={activePersona}
        onWorkflowUpdated={(updated) => {
          setWorkflow(updated);
          setCurrentWorkflow(updated);
        }}
      />
    </div>
  );
};
