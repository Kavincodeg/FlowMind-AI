import React, { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import type { AuditListItem, Persona } from '../types';
import { api } from '../api';
import { SearchIcon, CheckCircleIcon, ClockIcon, AlertTriangleIcon, XCircleIcon, ArrowRightIcon } from './Icons';
import { getRoleCapabilitySummary } from './Header';
import { Button, LoadingState, EmptyState } from './ui';

interface HomeViewProps {
  activePersona: Persona;
  onNavigateToNewCase?: () => void;
  onSelectCase?: (workflowId: string) => void;
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
  const navigate = useNavigate();
  const [cases, setCases] = useState<AuditListItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    const fetchCases = async () => {
      setIsLoading(true);
      setError(null);
      try {
        const list = await api.listAudits(activePersona.token);
        if (!isMounted) return;
        setCases(list);
      } catch (err) {
        if (!isMounted) return;
        if (err instanceof Error) {
          setError(err.message);
        } else {
          setError('Could not load current cases.');
        }
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };

    fetchCases();
    return () => {
      isMounted = false;
    };
  }, [activePersona]);

  const handleNewCase = () => {
    if (onNavigateToNewCase) {
      onNavigateToNewCase();
    } else {
      navigate('/investigate');
    }
  };

  const handleCaseClick = (wfId: string) => {
    if (onSelectCase) {
      onSelectCase(wfId);
    } else {
      navigate(`/investigate/${wfId}`);
    }
  };

  // Derive real counts from real backend list
  const waitingCount = cases.filter((c) => c.terminal_state === 'PENDING_APPROVAL').length;
  const sortedCount = cases.filter(
    (c) => c.terminal_state === 'APPROVED_EXECUTED' || c.terminal_state === 'COMPLETED'
  ).length;
  const rejectedCount = cases.filter((c) => c.terminal_state === 'REJECTED').length;
  const abstainedCount = cases.filter((c) => c.terminal_state === 'ABSTAINED').length;

  return (
    <div className="page-container" style={{ maxWidth: '1000px' }}>
      {/* Friendly greeting hero */}
      <div
        className="console-panel card-elevated"
        style={{
          padding: 'var(--space-6) var(--space-8)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}
      >
        <div style={{ maxWidth: '600px' }}>
          <h1 className="page-title" style={{ marginBottom: 'var(--space-1)' }}>
            Hello, {activePersona.name}!
          </h1>
          <p className="page-subtitle" style={{ lineHeight: 1.5 }}>
            {getRoleCapabilitySummary(activePersona.role)}. Here is an overview of what needs attention across customer cases today.
          </p>
        </div>

        <div>
          <button
            type="button"
            id="btn-home-new-case"
            className="btn btn-primary"
            style={{ padding: '0.75rem 1.4rem', fontSize: 'var(--text-sm)', fontWeight: 600, display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)' }}
            onClick={handleNewCase}
          >
            <SearchIcon size={16} /> Look into a new case
          </button>
        </div>
      </div>

      {/* Real counters from backend */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 'var(--space-4)' }}>
        <div className="console-panel" style={{ padding: 'var(--space-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--status-warning-text)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
            <ClockIcon size={16} /> Waiting for an OK
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text-primary)', marginTop: 'var(--space-2)' }}>
            {waitingCount}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 'var(--space-1)' }}>
            {waitingCount === 1 ? '1 case needs review' : `${waitingCount} cases need review`}
          </div>
        </div>

        <div className="console-panel" style={{ padding: 'var(--space-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--status-success-text)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
            <CheckCircleIcon size={16} /> Sorted and finished
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text-primary)', marginTop: 'var(--space-2)' }}>
            {sortedCount}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 'var(--space-1)' }}>
            Fully checked and handled
          </div>
        </div>

        <div className="console-panel" style={{ padding: 'var(--space-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--status-danger-text)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
            <XCircleIcon size={16} /> Turned down
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text-primary)', marginTop: 'var(--space-2)' }}>
            {rejectedCount}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 'var(--space-1)' }}>
            Decided against by a reviewer
          </div>
        </div>

        <div className="console-panel" style={{ padding: 'var(--space-5)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--text-muted)', fontSize: 'var(--text-xs)', fontWeight: 600 }}>
            <AlertTriangleIcon size={16} /> No guess made
          </div>
          <div style={{ fontSize: 'var(--text-3xl)', fontWeight: 700, color: 'var(--text-primary)', marginTop: 'var(--space-2)' }}>
            {abstainedCount}
          </div>
          <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)', marginTop: 'var(--space-1)' }}>
            Safely stepped aside for human review
          </div>
        </div>
      </div>

      {/* Real cases list */}
      <div className="console-panel">
        <div className="panel-header" style={{ flexWrap: 'wrap', gap: 'var(--space-2)' }}>
          <div>
            <div className="panel-title">Recent Customer Cases</div>
            <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
              Cases recorded in the system. Click any case to see its full story and details.
            </span>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <Link
              to="/cases"
              className="btn btn-secondary btn-sm"
              style={{ textDecoration: 'none' }}
            >
              View all cases
            </Link>
            <Button
              type="button"
              variant="primary"
              size="sm"
              onClick={handleNewCase}
            >
              + New Case
            </Button>
          </div>
        </div>

        {error && (
          <div className="alert-banner alert-danger">
            <AlertTriangleIcon size={14} />
            <span>{error}</span>
          </div>
        )}

        {isLoading ? (
          <LoadingState message="Loading your customer cases..." />
        ) : cases.length === 0 ? (
          <EmptyState
            title="No customer cases recorded yet"
            description="Start by investigating a customer message or selecting an existing test scenario."
            action={
              <Button type="button" variant="primary" onClick={handleNewCase}>
                Look into your first case
              </Button>
            }
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {cases.map((c) => {
              const statusInfo = getPlainStatusLabel(c.terminal_state);
              return (
                <div
                  key={c.audit_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: 'var(--space-3) var(--space-4)',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-default)',
                    cursor: 'pointer',
                    transition: 'border-color 0.15s ease',
                  }}
                  onClick={() => handleCaseClick(c.workflow_id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handleCaseClick(c.workflow_id);
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <span style={{ fontWeight: 600, fontSize: 'var(--text-sm)', color: 'var(--text-primary)' }}>
                        Case {c.workflow_id}
                      </span>
                      <span className={`badge ${statusInfo.badgeClass}`}>
                        {statusInfo.label}
                      </span>
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      Started {new Date(c.started_at).toLocaleString()}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', color: 'var(--accent-primary)', fontSize: 'var(--text-xs)', fontWeight: 500 }}>
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
