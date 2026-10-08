import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';
import { getPlainStatusLabel } from './HomeView';
import { SearchIcon, RefreshIcon, AlertTriangleIcon, HashIcon, LayersIcon } from './Icons';
import { Button, LoadingState, EmptyState } from './ui';
import type { AuditListItem } from '../types';
import { formatDateTime } from '../types';

export const CasesListView: React.FC = () => {
  const { activePersona } = useAppContext();

  const [cases, setCases] = useState<AuditListItem[]>([]);
  const [filter, setFilter] = useState<string>('ALL');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchCases = async () => {
    if (!activePersona) return;
    setIsLoading(true);
    setError(null);
    try {
      const items = await api.listAudits(activePersona.token);
      setCases(items);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError('Failed to load cases from audit records.');
      }
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchCases();
  }, [activePersona]);

  const filteredCases = cases.filter((c) => {
    const matchesFilter =
      filter === 'ALL' ||
      (filter === 'PENDING' && c.terminal_state === 'PENDING_APPROVAL') ||
      (filter === 'COMPLETED' && (c.terminal_state === 'APPROVED_EXECUTED' || c.terminal_state === 'COMPLETED')) ||
      (filter === 'REJECTED' && c.terminal_state === 'REJECTED') ||
      (filter === 'ABSTAINED' && c.terminal_state === 'ABSTAINED');

    const matchesSearch =
      !searchQuery.trim() ||
      c.workflow_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.audit_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
      c.terminal_state.toLowerCase().includes(searchQuery.toLowerCase());

    return matchesFilter && matchesSearch;
  });

  return (
    <div className="page-container" style={{ maxWidth: '1050px' }}>
      {/* Header bar */}
      <div
        className="console-panel"
        style={{
          padding: 'var(--space-6)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-4)',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <LayersIcon size={20} />
            <h1 className="page-title" style={{ margin: 0 }}>
              Past Customer Cases &amp; History
            </h1>
          </div>
          <p className="page-subtitle" style={{ margin: 'var(--space-1) 0 0 0' }}>
            Complete ledger of past and active investigations. Click any case to inspect its evidence, decision, or cryptographic proof.
          </p>
        </div>

        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <Button
            type="button"
            variant="secondary"
            size="sm"
            onClick={fetchCases}
            disabled={isLoading}
            icon={<RefreshIcon size={14} />}
          >
            Refresh
          </Button>
          <Link
            to="/investigate"
            className="btn btn-primary btn-sm"
            style={{ textDecoration: 'none' }}
          >
            <span className="btn-icon"><SearchIcon size={14} /></span>
            <span>+ New Case</span>
          </Link>
        </div>
      </div>

      {/* Filter and search bar */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: 'var(--space-3)',
        }}
      >
        <div style={{ display: 'flex', gap: 'var(--space-2)', flexWrap: 'wrap' }}>
          {[
            { id: 'ALL', label: `All (${cases.length})` },
            { id: 'PENDING', label: `Waiting for OK (${cases.filter((c) => c.terminal_state === 'PENDING_APPROVAL').length})` },
            { id: 'COMPLETED', label: `Sorted & Finished (${cases.filter((c) => c.terminal_state === 'APPROVED_EXECUTED' || c.terminal_state === 'COMPLETED').length})` },
            { id: 'REJECTED', label: `Turned Down (${cases.filter((c) => c.terminal_state === 'REJECTED').length})` },
            { id: 'ABSTAINED', label: `No Guess (${cases.filter((c) => c.terminal_state === 'ABSTAINED').length})` },
          ].map((tab) => (
            <button
              key={tab.id}
              type="button"
              className={`btn btn-sm ${filter === tab.id ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <input
          type="text"
          className="form-input"
          style={{ maxWidth: '260px', padding: 'var(--space-1) var(--space-3)', fontSize: 'var(--text-xs)' }}
          placeholder="Filter by Case WF- ID..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
      </div>

      {error && (
        <div className="alert-banner alert-danger">
          <AlertTriangleIcon size={16} />
          <span>{error}</span>
        </div>
      )}

      {/* Cases list */}
      <div className="console-panel" style={{ padding: 'var(--space-2)' }}>
        {isLoading ? (
          <LoadingState message="Loading customer cases..." />
        ) : filteredCases.length === 0 ? (
          <EmptyState
            title="No customer cases found"
            description="No customer cases matched your current filter criteria."
            action={
              <Link to="/investigate" className="btn btn-primary" style={{ textDecoration: 'none' }}>
                Look into your first case
              </Link>
            }
          />
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', padding: 'var(--space-2)' }}>
            {filteredCases.map((c) => {
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
                    flexWrap: 'wrap',
                    gap: 'var(--space-3)',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                      <Link
                        to={`/investigate/${c.workflow_id}`}
                        style={{ fontWeight: 700, fontSize: 'var(--text-sm)', color: 'var(--text-primary)', textDecoration: 'none' }}
                      >
                        Case {c.workflow_id}
                      </Link>
                      <span className={`badge ${statusInfo.badgeClass}`}>
                        {statusInfo.label}
                      </span>
                    </div>
                    <div style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                      Started {formatDateTime(c.started_at)} &bull; Audit ID: {c.audit_id}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
                    <Link
                      to={`/cases/${c.workflow_id}`}
                      className="btn btn-secondary btn-sm"
                      style={{ textDecoration: 'none' }}
                    >
                      Status / Timeline
                    </Link>
                    <Link
                      to={`/investigate/${c.workflow_id}`}
                      className="btn btn-secondary btn-sm"
                      style={{ textDecoration: 'none' }}
                    >
                      Investigation
                    </Link>
                    <Link
                      to={`/trust/${c.workflow_id}`}
                      className="btn btn-secondary btn-sm"
                      style={{ textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: 'var(--space-1)' }}
                    >
                      <HashIcon size={12} /> Audit Record
                    </Link>
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
