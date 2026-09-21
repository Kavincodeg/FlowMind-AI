import React, { useState } from 'react';
import type { WorkflowInstance, Persona } from '../types';
import { api, ApiError } from '../api';
import { ExecutionOutcome } from './ExecutionOutcome';
import { ShieldIcon, AlertTriangleIcon, CheckCircleIcon, XCircleIcon, LockIcon } from './Icons';
import { getRolePlainTitle } from './Header';

interface ApprovalGateProps {
  workflow: WorkflowInstance;
  activePersona: Persona;
  onWorkflowUpdated: (updated: WorkflowInstance) => void;
}

export const getPlainActionLabel = (actionType: string): string => {
  const norm = actionType.toUpperCase();
  if (norm.includes('REFUND')) return 'Issue a refund recommendation';
  if (norm.includes('TRANSFER')) return 'Transfer case to a specialist team';
  if (norm.includes('ESCALATE')) return 'Escalate to higher-level review';
  if (norm.includes('REQUEST')) return 'Ask customer for additional details';
  if (norm.includes('RESOLVE')) return 'Send standard helpful resolution';
  return actionType.replace(/_/g, ' ').toLowerCase();
};

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
        setRbacError('Please check the parameters format — it must be valid JSON text.');
        setIsSubmitting(false);
        return;
      }
    }

    try {
      const updated = await api.submitDecision(
        workflow.workflow_id,
        {
          decision,
          rejection_reason: decisionNotes.trim() || 'Action turned down by reviewer.',
          comments: decisionNotes.trim() || `Reviewed by ${activePersona.name} (${getRolePlainTitle(activePersona.role)})`,
          notes: decisionNotes.trim() || `Reviewed by ${activePersona.name} (${getRolePlainTitle(activePersona.role)})`,
          modified_action: modifiedAction,
        },
        activePersona.token
      );
      setIsModifying(false);
      onWorkflowUpdated(updated);
    } catch (err) {
      if (err instanceof ApiError && err.status === 403) {
        const roleTitle = getRolePlainTitle(activePersona.role);
        setRbacError(
          `As a ${roleTitle} (${activePersona.role}), you can't say yes to this one — it needs a Manager or Admin. Current role '${activePersona.role}' lacks authorization for this action.`
        );
      } else if (err instanceof Error) {
        setRbacError(err.message);
      } else {
        setRbacError('Could not submit your decision. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="console-panel">
      <div className="panel-header">
        <div className="panel-title">
          <ShieldIcon size={16} /> Review &amp; Decide
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
          {isExecuted
            ? 'Sorted and finished (APPROVED_EXECUTED)'
            : isPending
            ? 'Waiting for an OK'
            : isRejected
            ? 'Turned down (REJECTED)'
            : isAbstained
            ? 'No guess made'
            : workflow.status}
        </span>
      </div>

      {recommendation ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem' }}>
          {/* Suggestion Card */}
          <div
            style={{
              backgroundColor: 'var(--bg-surface-elevated)',
              border: '1px solid var(--border-default)',
              borderRadius: 'var(--radius-md)',
              padding: '1rem',
              display: 'flex',
              flexDirection: 'column',
              gap: '0.5rem',
            }}
          >
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '0.5rem' }}>
              <span style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', fontWeight: 600 }}>
                What we'd suggest doing
              </span>
              <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                {(recommendation.priority ? String(recommendation.priority).toUpperCase() : 'NORMAL')} PRIORITY
              </span>
            </div>

            <div style={{ fontSize: '1rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
              <span>{getPlainActionLabel(recommendation.action_type)}</span>
              {recommendation.action_type && (
                <span className="hash-pill" style={{ fontSize: '0.675rem', fontWeight: 400 }}>
                  {recommendation.action_type}
                </span>
              )}
            </div>

            <div style={{ fontSize: '0.825rem', color: 'var(--text-secondary)' }}>
              Team handling this:{' '}
              <strong style={{ color: 'var(--text-primary)' }}>{recommendation.target_team || 'Customer Support Team'}</strong>
            </div>

            <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.5rem' }}>
              <strong style={{ color: 'var(--text-muted)' }}>Why: </strong>
              {recommendation.justification}
            </div>

            {recommendation.parameters && Object.keys(recommendation.parameters).length > 0 && (
              <details style={{ marginTop: '0.25rem', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                <summary style={{ cursor: 'pointer', userSelect: 'none' }}>
                  See suggested details/parameters
                </summary>
                <div style={{ marginTop: '0.35rem' }}>
                  <span className="hash-pill" style={{ display: 'inline-block' }}>
                    {JSON.stringify(recommendation.parameters)}
                  </span>
                </div>
              </details>
            )}
          </div>

          {/* RBAC Permission Error Banner */}
          {rbacError && (
            <div className="alert-banner alert-danger">
              <LockIcon size={16} />
              <div>
                <strong>Authorization Boundary Enforced</strong>
                <div style={{ marginTop: '0.25rem', fontSize: '0.825rem', lineHeight: 1.45 }}>{rbacError}</div>
                <div style={{ marginTop: '0.4rem', fontSize: '0.75rem', opacity: 0.9 }}>
                  Tip: Switch to a Manager or System Admin using the person selector at the top right to approve this.
                </div>
              </div>
            </div>
          )}

          {/* Reviewer Action Buttons */}
          {isPending && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.85rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.85rem' }}>
              <div className="form-group">
                <label className="form-label" htmlFor="decision-notes">
                  Add an optional note explaining your decision
                </label>
                <input
                  id="decision-notes"
                  type="text"
                  className="form-input"
                  placeholder="e.g. Checked invoice INV-2024-001 and confirmed double charge"
                  value={decisionNotes}
                  onChange={(e) => setDecisionNotes(e.target.value)}
                  disabled={isSubmitting}
                />
              </div>

              {isModifying && (
                <div className="form-group">
                  <label className="form-label" htmlFor="modified-parameters-textarea">
                    Change parameters before confirming
                  </label>
                  <textarea
                    id="modified-parameters-textarea"
                    className="form-textarea modified-params-input"
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '0.75rem' }}
                    rows={4}
                    value={modifiedParamsText}
                    onChange={(e) => setModifiedParamsText(e.target.value)}
                  />
                  <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
                    Adjust the amount, reason, or notes above before giving the final OK.
                  </span>
                </div>
              )}

              <div style={{ display: 'flex', gap: '0.6rem', flexWrap: 'wrap' }}>
                <button
                  type="button"
                  id="btn-approve-action"
                  className="btn btn-success"
                  onClick={() => handleSubmit('APPROVE')}
                  disabled={isSubmitting}
                  style={{ fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  <CheckCircleIcon size={14} /> Yes, do this
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
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  {isModifying ? 'Confirm Modified Action' : 'Change it first'}
                </button>

                <button
                  type="button"
                  id="btn-reject-action"
                  className="btn btn-danger"
                  onClick={() => handleSubmit('REJECT')}
                  disabled={isSubmitting}
                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}
                >
                  <XCircleIcon size={14} /> No, don't do this
                </button>
              </div>
            </div>
          )}

          {/* Outcome after execution */}
          {isExecuted && <ExecutionOutcome execution={workflow.execution_record} />}

          {/* Rejection State */}
          {isRejected && (
            <div className="alert-banner alert-danger">
              <XCircleIcon size={16} />
              <div>
                <strong>Action Turned Down — Action Rejected by Human Governance</strong>
                <div style={{ marginTop: '0.25rem', fontSize: '0.825rem' }}>
                  {workflow.approval_record?.rejection_reason ||
                    workflow.approval_record?.comments ||
                    workflow.approval_record?.notes ||
                    'Declined by reviewer.'}{' '}
                  (Reviewer: {workflow.approval_record?.approver_name || activePersona.name})
                </div>
              </div>
            </div>
          )}
        </div>
      ) : isAbstained ? (
        <div className="alert-banner alert-warning">
          <AlertTriangleIcon size={16} />
          <div>
            <strong>No automatic action proposed</strong>
            <div style={{ marginTop: '0.25rem', fontSize: '0.825rem', lineHeight: 1.45 }}>
              {workflow.reasoning?.abstention_reason ||
                'We do not have enough verified records to make a confident recommendation without guessing. A team member should investigate this directly.'}
            </div>
          </div>
        </div>
      ) : (
        <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '1.5rem 0', textAlign: 'center' }}>
          No suggestion ready yet. Submit the customer's request on the left to review what happened.
        </div>
      )}
    </div>
  );
};
