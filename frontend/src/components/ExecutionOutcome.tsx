import React from 'react';
import type { ExecutionRecord } from '../types';
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
        padding: '0.85rem',
        marginTop: '0.75rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--status-success-text)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          <CheckCircleIcon size={14} /> Action Executed via Mock Connector
        </span>
        <span className="badge badge-success">{execution.status}</span>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.775rem' }}>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Target System: </span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{execution.dispatched_to}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Action Type: </span>
          <span style={{ color: 'var(--text-primary)', fontWeight: 500 }}>{execution.action_type}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Generated ID: </span>
          <span className="hash-pill" style={{ color: 'var(--text-primary)' }}>{execution.target_id}</span>
        </div>
        <div>
          <span style={{ color: 'var(--text-muted)' }}>Timestamp: </span>
          <span style={{ color: 'var(--text-secondary)' }}>
            {new Date(execution.timestamp).toLocaleTimeString()}
          </span>
        </div>
      </div>

      {execution.response_payload && Object.keys(execution.response_payload).length > 0 && (
        <div style={{ marginTop: '0.25rem' }}>
          <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', marginBottom: '0.2rem' }}>
            External API Response Payload:
          </div>
          <pre
            style={{
              fontFamily: 'var(--font-mono)',
              fontSize: '0.72rem',
              backgroundColor: 'var(--bg-app)',
              padding: '0.5rem',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
              overflowX: 'auto',
            }}
          >
            {JSON.stringify(execution.response_payload, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};
