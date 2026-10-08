import React from 'react';
import type { ExecutionRecord } from '../types';
import { formatDateTime, getPlainActionLabel } from '../types';
import { CheckCircleIcon } from './Icons';

interface ExecutionOutcomeProps {
  execution: ExecutionRecord | null;
}

export const ExecutionOutcome: React.FC<ExecutionOutcomeProps> = ({ execution }) => {
  if (!execution) return null;

  return (
    <div
      style={{
        backgroundColor: 'var(--bg-surface-elevated)',
        border: '1px solid var(--status-success-border)',
        borderRadius: 'var(--radius-md)',
        padding: '1rem',
        marginTop: '0.85rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.6rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span
          style={{
            fontSize: '0.85rem',
            fontWeight: 600,
            color: 'var(--status-success-text)',
            display: 'flex',
            alignItems: 'center',
            gap: '0.4rem',
          }}
        >
          <CheckCircleIcon size={16} /> Sorted and finished — Action Executed via Mock Connector
        </span>
        <span className="badge badge-success">SUCCESS</span>
      </div>

      <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', margin: 0 }}>
        The approved action was dispatched directly to the destination team's system and marked complete.
      </p>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.6rem', fontSize: '0.775rem' }}>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Target System: </span>
          {/* connector_name is the correct backend field (was: dispatched_to) */}
          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{execution.connector_name}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Action: </span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{getPlainActionLabel(execution.action_type)}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Transaction ID: </span>
          {/* transaction_id is the correct backend field (was: target_id) */}
          <span className="hash-pill" style={{ color: 'var(--text-primary)' }}>{execution.transaction_id}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Time Completed: </span>
          {/* executed_at is the correct backend field (was: timestamp); formatTime guards against "Invalid Date" */}
          <span style={{ color: 'var(--text-secondary)' }}>
            {formatDateTime(execution.executed_at)}
          </span>
        </div>
      </div>

      {execution.details && Object.keys(execution.details).length > 0 && (
        <details style={{ marginTop: '0.25rem', fontSize: '0.725rem', color: 'var(--text-muted)' }}>
          <summary style={{ cursor: 'pointer', userSelect: 'none' }}>
            See technical details
          </summary>
          <pre
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.7rem',
              backgroundColor: 'var(--bg-app)',
              padding: '0.5rem',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              overflowX: 'auto',
              marginTop: '0.35rem',
            }}
          >
            {JSON.stringify(execution.details, null, 2)}
          </pre>
        </details>
      )}
    </div>
  );
};
