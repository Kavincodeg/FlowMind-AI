import React, { useEffect, useState } from 'react';
import type { AuditListItem, Persona } from '../types';
import { api } from '../api';
import { SearchIcon, CheckCircleIcon, ClockIcon, AlertTriangleIcon, XCircleIcon, ArrowRightIcon } from './Icons';
import { getRoleCapabilitySummary } from './Header';

interface HomeViewProps {
  activePersona: Persona;
  onNavigateToNewCase: () => void;
  onSelectCase: (workflowId: string) => void;
}

export const getPlainStatusLabel = (status: string): { label: string; badgeClass: string } => {
  switch (status) {
    case 'PENDING_APPROVAL':
      return { label: 'Waiting for an OK', badgeClass: 'badge-warning' };
    case 'APPROVED_EXECUTED':
    case 'COMPLETED':
      return { label: 'Sorted and finished', badgeClass: 'badge-success' };
    case 'REJECTED':
      return { label: 'Turned down', badgeClass: 'badge-danger' };
    case 'ABSTAINED':
      return { label: "Couldn't tell — no guess made", badgeClass: 'badge-warning' };
    case 'PENDING_REASONING':
      return { label: 'Looking into what happened...', badgeClass: 'badge-neutral' };
    default:
      return { label: status, badgeClass: 'badge-neutral' };
  }
};

export const HomeView: React.FC<HomeViewProps> = ({
  activePersona,
  onNavigateToNewCase,
  onSelectCase,
}) => {
  const [cases, setCases] = useState<AuditListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchCases = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const list = await api.listAudits(activePersona.token);
        setCases(list);
      } catch (err) {
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Could not load current cases.');
        }
      } finally {
        setIsLoading(false);
      }
    };

    fetchCases();
  }, [activePersona]);

  // Derive real counts from real backend list
  const waitingCount = cases.filter((c) => c.terminal_state === 'PENDING_APPROVAL').length;
  const sortedCount = cases.filter(
    (c) => c.terminal_state === 'APPROVED_EXECUTED' || c.terminal_state === 'COMPLETED'
  ).length;
  const rejectedCount = cases.filter((c) => c.terminal_state === 'REJECTED').length;
  const abstainedCount = cases.filter((c) => c.terminal_state === 'ABSTAINED').length;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: '1000px', margin: '0 auto' }}>
      {/* Friendly greeting hero */}
      <div
        className="console-panel"
        style={{
          padding: '2rem',
          background: 'linear-gradient(135deg, var(--bg-surface) 0%, var(--bg-surface-elevated) 100%)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1.5rem',
        }}
      >
        <div style={{ maxWidth: '600px' }}>
          <h1 style={{ fontSize: '1.6rem', fontWeight: 700, color: 'var(--text-primary)', margin: 0, marginBottom: '0.4rem' }}>
            Hello, {activePersona.name}!
          </h1>
          <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0, lineHeight: 1.5 }}>
            {getRoleCapabilitySummary(activePersona.role)}. Here is an overview of what needs attention across customer cases today.
          </p>
        </div>

        <div>
          <button
            type="button"
            id="btn-home-new-case"
            className="btn btn-primary"
            style={{ padding: '0.75rem 1.4rem', fontSize: '0.95rem', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: '0.5rem' }}
            onClick={onNavigateToNewCase}
          >
            <SearchIcon size={16} /> Look into a new case
          </button>
        </div>
      </div>

      {/* Real counters from backend */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem' }}>
        <div className="console-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--status-warning-text)', fontSize: '0.8rem', fontWeight: 600 }}>
            <ClockIcon size={16} /> Waiting for an OK
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.5rem' }}>
            {waitingCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            {waitingCount === 1 ? '1 case needs review' : `${waitingCount} cases need review`}
          </div>
        </div>

        <div className="console-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--status-success-text)', fontSize: '0.8rem', fontWeight: 600 }}>
            <CheckCircleIcon size={16} /> Sorted and finished
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.5rem' }}>
            {sortedCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Fully checked and handled
          </div>
        </div>

        <div className="console-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--status-danger-text)', fontSize: '0.8rem', fontWeight: 600 }}>
            <XCircleIcon size={16} /> Turned down
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.5rem' }}>
            {rejectedCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Decided against by a reviewer
          </div>
        </div>

        <div className="console-panel" style={{ padding: '1.25rem' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--text-muted)', fontSize: '0.8rem', fontWeight: 600 }}>
            <AlertTriangleIcon size={16} /> No guess made
          </div>
          <div style={{ fontSize: '1.8rem', fontWeight: 700, color: 'var(--text-primary)', marginTop: '0.5rem' }}>
            {abstainedCount}
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
            Safely stepped aside for human review
          </div>
        </div>
      </div>

      {/* Real cases list */}
      <div className="console-panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">Recent Customer Cases</div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Cases recorded in the system. Click any case to see its full story and details.
            </span>
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
            onClick={onNavigateToNewCase}
          >
            + New Case
          </button>
        </div>

        {error && (
          <div className="alert-banner alert-danger">
            <AlertTriangleIcon size={14} />
            <span>{error}</span>
          </div>
        )}

        {isLoading ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '2rem 0', textAlign: 'center' }}>
            Loading your customer cases...
          </div>
        ) : cases.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '2.5rem 0', textAlign: 'center' }}>
            <p>No customer cases recorded yet.</p>
            <button
              type="button"
              className="btn btn-primary"
              style={{ marginTop: '0.75rem' }}
              onClick={onNavigateToNewCase}
            >
              Look into your first case
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
            {cases.map((c) => {
              const statusInfo = getPlainStatusLabel(c.terminal_state);
              return (
                <div
                  key={c.audit_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.85rem 1rem',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-default)',
                    cursor: 'pointer',
                    transition: 'border-color 0.15s ease',
                  }}
                  onClick={() => onSelectCase(c.workflow_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') onSelectCase(c.workflow_id);
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.2rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                        Case {c.workflow_id}
                      </span>
                      <span className={`badge ${statusInfo.badgeClass}`} style={{ fontSize: '0.675rem' }}>
                        {statusInfo.label}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Started {new Date(c.started_at).toLocaleString()}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: 'var(--accent-primary)', fontSize: '0.8rem', fontWeight: 500 }}>
                    <span>View details</span>
                    <ArrowRightIcon size={14} />
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
};
