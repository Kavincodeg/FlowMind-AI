import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { api } from '../api';
import { getPlainStatusLabel } from './HomeView';
import { SearchIcon, RefreshIcon, AlertTriangleIcon, HashIcon, LayersIcon } from './Icons';
import type { AuditListItem } from '../types';

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
    <div style={{ maxWidth: '1050px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Header bar */}
      <div
        className="console-panel"
        style={{
          padding: '1.5rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          flexWrap: 'wrap',
          gap: '1rem',
        }}
      >
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <LayersIcon size={20} />
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0, color: 'var(--text-primary)' }}>
              Past Customer Cases &amp; History
            </h1>
          </div>
          <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Complete ledger of past and active investigations. Click any case to inspect its evidence, decision, or cryptographic proof.
          </p>
        </div>

        <div style={{ display: 'flex', gap: '0.6rem' }}>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={fetchCases}
            disabled={isLoading}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem' }}
          >
            <RefreshIcon size={14} /> Refresh
          </button>
          <Link
            to="/investigate"
            className="btn btn-primary"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.8rem', textDecoration: 'none' }}
          >
            <SearchIcon size={14} /> + New Case
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
          gap: '0.75rem',
        }}
      >
        <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap' }}>
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
              className={`btn ${filter === tab.id ? 'btn-primary' : 'btn-secondary'}`}
              style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
              onClick={() => setFilter(tab.id)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <input
          type="text"
          className="form-input"
          style={{ maxWidth: '260px', padding: '0.35rem 0.65rem', fontSize: '0.8rem' }}
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
      <div className="console-panel" style={{ padding: '0.5rem' }}>
        {isLoading ? (
          <div style={{ padding: '3rem 0', textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
            Loading customer cases...
          </div>
        ) : filteredCases.length === 0 ? (
          <div style={{ padding: '3rem 1rem', textAlign: 'center', color: 'var(--text-muted)' }}>
            <p style={{ margin: 0, fontSize: '0.9rem' }}>No customer cases found matching the current filter.</p>
            <Link to="/investigate" className="btn btn-primary" style={{ marginTop: '1rem', display: 'inline-block', textDecoration: 'none' }}>
              Look into your first case
            </Link>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem', padding: '0.5rem' }}>
            {filteredCases.map((c) => {
              const statusInfo = getPlainStatusLabel(c.terminal_state);
              return (
                <div
                  key={c.audit_id}
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    padding: '0.9rem 1.1rem',
                    backgroundColor: 'var(--bg-surface-elevated)',
                    borderRadius: 'var(--radius-md)',
                    border: '1px solid var(--border-default)',
                    flexWrap: 'wrap',
                    gap: '0.75rem',
                  }}
                >
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
                      <Link
                        to={`/investigate/${c.workflow_id}`}
                        style={{ fontWeight: 700, fontSize: '0.925rem', color: 'var(--text-primary)', textDecoration: 'none' }}
                      >
                        Case {c.workflow_id}
                      </Link>
                      <span className={`badge ${statusInfo.badgeClass}`} style={{ fontSize: '0.7rem' }}>
                        {statusInfo.label}
                      </span>
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                      Started {new Date(c.started_at).toLocaleString()} &bull; Audit ID: {c.audit_id}
                    </div>
                  </div>

                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                    <Link
                      to={`/cases/${c.workflow_id}`}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem', textDecoration: 'none' }}
                    >
                      Status / Timeline
                    </Link>
                    <Link
                      to={`/investigate/${c.workflow_id}`}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem', textDecoration: 'none' }}
                    >
                      Investigation
                    </Link>
                    <Link
                      to={`/trust/${c.workflow_id}`}
                      className="btn btn-secondary"
                      style={{ fontSize: '0.75rem', padding: '0.3rem 0.6rem', textDecoration: 'none', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}
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
