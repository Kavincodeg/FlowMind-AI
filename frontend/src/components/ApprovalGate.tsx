import React, { useState } from 'react';
import type { WorkflowInstance, Persona } from '../types';
import { api, ApiError } from '../api';
import { ExecutionOutcome } from './ExecutionOutcome';
import { ShieldIcon, AlertTriangleIcon, CheckCircleIcon, XCircleIcon, LockIcon } from './Icons';

interface ApprovalGateProps {
  workflow: WorkflowInstance;
  activePersona: Persona;
  onWorkflowUpdated: (updated: WorkflowInstance) => void;
}

export const ApprovalGate: React.FC<ApprovalGateProps> = ({
  workflow,
  activePersona,
  onWorkflowUpdated,
}) => {
  const [decisionNotes, setDecisionNotes] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [rbacError, setRbacError] = useState<string | null>(null);
  const [isModifying, setIsModifying] = useState(false);
  const [modifiedParamsText, setModifiedParamsText] = useState(
    JSON.stringify(workflow.reasoning?.recommendation?.parameters || {}, null, 2)
  );

  const recommendation = workflow.reasoning?.recommendation;
  const isPending = workflow.status === 'PENDING_APPROVAL';
  const isExecuted =
    workflow.status === 'APPROVED_EXECUTED' ||
    (workflow.status as string) === 'COMPLETED' ||
    (workflow.status as string) === 'EXECUTING';
  const isRejected = workflow.status === 'REJECTED';
  const isAbstained = workflow.status === 'ABSTAINED';

  const handleSubmit = async (decision: 'APPROVE' | 'REJECT' | 'MODIFY') => {
    setIsSubmitting(true);
    setRbacError(null);

    let modifiedAction: Record<string, unknown> | undefined = undefined;
    if (decision === 'MODIFY') {
      try {
        const parsedParams = JSON.parse(modifiedParamsText);
        modifiedAction = {
          action_type: recommendation?.action_type || 'ISSUE_REFUND_RECOMMENDATION',
          target_team: recommendation?.target_team || 'Finance & Compliance Team',
          urgency: recommendation?.priority ? String(recommendation.priority).toLowerCase() : 'medium',
          parameters: parsedParams,
          requires_approval: true,
        };
      } catch {
        setRbacError('Invalid JSON format in modified parameters.');
        setIsSubmitting(false);
        return;
      }
    }

    try {
      const updated = await api.submitDecision(
        workflow.workflow_id,
        {
          decision,
          rejection_reason: decisionNotes.trim() || 'Action rejected by human reviewer.',
          comments: decisionNotes.trim() || `Submitted by ${activePersona.name} (${activePersona.role})`,
          notes: decisionNotes.trim() || `Submitted by ${activePersona.name} (${activePersona.role})`,
          modified_action: modifiedAction,
        },
        activePersona.token
      );
      setIsModifying(false);
      onWorkflowUpdated(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        setRbacError(
          `RBAC Permission Denied: ${err.message}. Current role '${activePersona.role}' lacks authorization. Switch persona in the header to Team Lead or Manager to authorize this action.`
        );
      } else if (err instanceof Error) {
        setRbacError(err.message);
      } else {
        setRbacError('An unexpected error occurred during approval submission.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="console-panel">
      <div className="panel-header">
        <div className="panel-title">
          <ShieldIcon size={16} /> Human Governance & Approval Gate
        </div>
        <span
          className={`badge ${
            isExecuted
              ? 'badge-success'
              : isPending
              ? 'badge-warning'
              : isRejected || isAbstained
              ? 'badge-danger'
              : 'badge-neutral'
          }`}
        >
          {isExecuted ? 'APPROVED_EXECUTED' : workflow.status}
        </span>
      </div>

      {recommendation ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
          <div
            style={{
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
              padding: '0.85rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span style={{ fontSize: '0.72rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                Recommended Action
              </span>
              <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
                {recommendation.priority} PRIORITY
              </span>
            </div>

            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)' }}>
              {recommendation.action_type.toUpperCase()}
            </div>

            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Target Queue: <strong style={{ color: 'var(--text-primary)' }}>{recommendation.target_team}</strong>
            </div>

            <div style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.4rem' }}>
              <span style={{ color: 'var(--text-muted)' }}>Justification: </span>
              {recommendation.justification}
            </div>

            {recommendation.parameters && Object.keys(recommendation.parameters).length > 0 && (
              <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <span>Parameters: </span>
                <span className="hash-pill" style={{ display: 'inline-block', marginTop: '0.2rem' }}>
                  {JSON.stringify(recommendation.parameters)}
                </span>
              </div>
            )}
          </div>

          {/* RBAC Error Banner */}
          {rbacError && (
            <div className="alert-banner alert-danger">
              <LockIcon size={16} />
              <div>
                <strong>Authorization Boundary Enforced</strong>
                <div style={{ marginTop: '0.2rem' }}>{rbacError}</div>
              </div>
            </div>
          )}

          {/* Active Approval Controls */}
          {isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="decision-notes">
                  Reviewer Rationale / Audit Notes (Optional)
                </label>
                <input
                  id="decision-notes"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Verified customer SLA contract and approved refund"
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>

              {isModifying && (
                <div className="form-group">
                  <label className="form-label" htmlFor="modified-parameters-textarea">Modify Parameters (JSON)</label>
                  <textarea
                    id="modified-parameters-textarea"
                    className="form-textarea modified-params-input"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}
                    value={modifiedParamsText}
                    onChange={(e) => setModifiedParamsText(e.target.value)}
                  />
                </div>
              )}

              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  id="btn-approve-action"
                  className="btn btn-success"
                  onClick={() => handleSubmit('APPROVE')}
                  disabled={isSubmitting}
                >
                  <CheckCircleIcon size={14} /> Approve Action
                </button>

                <button
                  type="button"
                  id="btn-reject-action"
                  className="btn btn-danger"
                  onClick={() => handleSubmit('REJECT')}
                  disabled={isSubmitting}
                >
                  <XCircleIcon size={14} /> Reject Action
                </button>

                <button
                  type="button"
                  id="btn-modify-action"
                  className="btn btn-secondary"
                  onClick={() => {
                    if (isModifying) {
                      handleSubmit('MODIFY');
                    } else {
                      setIsModifying(true);
                    }
                  }}
                  disabled={isSubmitting}
                >
                  {isModifying ? 'Confirm Modified Action' : 'Modify Parameters'}
                </button>
              </div>
            </div>
          )}

          {/* Execution Outcome Display */}
          {isExecuted && <ExecutionOutcome execution={workflow.execution_record} />}

          {/* Rejection State */}
          {isRejected && (
            <div className="alert-banner alert-danger">
              <XCircleIcon size={16} />
              <div>
                <strong>Action Rejected by Human Governance</strong>
                <div style={{ marginTop: '0.2rem' }}>
                  {workflow.approval_record?.rejection_reason || workflow.approval_record?.comments || workflow.approval_record?.notes || 'No notes provided.'} (Approver: {workflow.approval_record?.approver_name || activePersona.name}, Role: {workflow.approval_record?.approver_role || activePersona.role})
                </div>
              </div>
            </div>
          )}
        </div>
      ) : isAbstained ? (
        <div className="alert-banner alert-warning">
          <AlertTriangleIcon size={16} />
          <div>
            <strong>Workflow Abstained from Automated Action</strong>
            <div style={{ marginTop: '0.2rem' }}>
              Reason: {workflow.reasoning?.abstention_reason || 'Insufficient grounding evidence or security risk detected.'}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1.5rem 0', textAlign: 'center' }}>
          No action proposed yet. Start an investigation to generate an evidence-grounded recommendation.
        </div>
      )}
    </div>
  );
};
