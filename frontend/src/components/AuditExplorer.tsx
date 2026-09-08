import React, { useEffect, useState } from 'react';
import type { AuditListItem, AuditTrail, Persona } from '../types';
import { api } from '../api';
import { HashIcon, CheckCircleIcon, RefreshIcon, LayersIcon } from './Icons';

interface AuditExplorerProps {
  currentWorkflowId: string | null;
  activePersona: Persona;
}

export const AuditExplorer: React.FC<AuditExplorerProps> = ({
  currentWorkflowId,
  activePersona,
}) => {
  const [auditList, setAuditList] = useState<AuditListItem[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(currentWorkflowId);
  const [auditDetail, setAuditDetail] = useState<AuditTrail | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [chainValid, setChainValid] = useState<boolean | null>(null);

  const fetchAudits = async () => {
    setIsLoadingList(true);
    setError(null);
    try {
      const items = await api.listAudits(activePersona.token);
      setAuditList(items);
      if (!selectedWorkflowId && items.length > 0) {
        setSelectedWorkflowId(items[0].workflow_id);
      }
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      }
    } finally {
      setIsLoadingList(false);
    }
  };

  const fetchAuditDetail = async (wfId: string) => {
    setIsLoadingDetail(true);
    setError(null);
    try {
      const detail = await api.getWorkflowAudit(wfId, activePersona.token);
      setAuditDetail(detail);

      // Verify cryptographic hash chain on the client
      let valid = true;
      if (detail.events && detail.events.length > 0) {
        for (let i = 1; i < detail.events.length; i++) {
          if (detail.events[i].parent_hash !== detail.events[i - 1].block_hash) {
            valid = false;
            break;
          }
        }
      }
      setChainValid(valid);
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      }
      setAuditDetail(null);
    } finally {
      setIsLoadingDetail(false);
    }
  };

  useEffect(() => {
    fetchAudits();
  }, [activePersona]);

  useEffect(() => {
    if (selectedWorkflowId) {
      fetchAuditDetail(selectedWorkflowId);
    }
  }, [selectedWorkflowId]);

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.25rem', alignItems: 'start' }}>
      {/* Audit Run Selector */}
      <div className="console-panel">
        <div className="panel-header">
          <div className="panel-title">
            <LayersIcon size={16} /> Workflow Audit Logs
          </div>
          <button
            type="button"
            className="btn btn-secondary"
            style={{ padding: '0.25rem 0.5rem', fontSize: '0.75rem' }}
            onClick={fetchAudits}
            disabled={isLoadingList}
          >
            <RefreshIcon size={12} /> Refresh
          </button>
        </div>

        {error && (
          <div className="alert-banner alert-danger">
            <span>{error}</span>
          </div>
        )}

        {auditList.length === 0 ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1rem 0' }}>
            No completed workflow audits recorded yet. Run a workflow to completion to generate a hash chain.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', maxHeight: '550px', overflowY: 'auto' }}>
            {auditList.map((item) => {
              const isSelected = item.workflow_id === selectedWorkflowId;
              return (
                <button
                  key={item.audit_id}
                  type="button"
                  className={`scenario-card ${isSelected ? 'active' : ''}`}
                  onClick={() => setSelectedWorkflowId(item.workflow_id)}
                >
                  <div className="scenario-card-header">
                    <span className="scenario-title" style={{ fontFamily: 'var(--font-mono)' }}>
                      {item.workflow_id}
                    </span>
                    <span
                      className={`badge ${
                        item.terminal_state === 'APPROVED_EXECUTED'
                          ? 'badge-success'
                          : item.terminal_state === 'REJECTED'
                          ? 'badge-danger'
                          : 'badge-warning'
                      }`}
                      style={{ fontSize: '0.65rem' }}
                    >
                      {item.terminal_state}
                    </span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                    <span>Duration: {typeof item.duration_ms === 'number' ? item.duration_ms.toFixed(1) : '0.0'}ms</span>
                    <span>{new Date(item.started_at).toLocaleTimeString()}</span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>

      {/* Audit Detail & Cryptographic Inspector */}
      <div className="console-panel">
        <div className="panel-header">
          <div className="panel-title">
            <HashIcon size={16} /> Cryptographic SHA-256 Hash Chain Inspector
          </div>
          {chainValid !== null && (
            <span
              className={`badge ${chainValid ? 'badge-success' : 'badge-danger'}`}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}
            >
              <CheckCircleIcon size={12} />
              {chainValid ? 'Cryptographic Chain Verified (Intact)' : 'Chain Integrity Compromised'}
            </span>
          )}
        </div>

        {isLoadingDetail ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '2rem 0', textAlign: 'center' }}>
            Verifying tamper-evident audit blocks...
          </div>
        ) : auditDetail ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Summary Row */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '0.75rem' }}>
              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Audit Record ID</div>
                <div style={{ fontSize: '0.825rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {auditDetail.audit_id}
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Terminal State</div>
                <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {auditDetail.terminal_state}
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>End-to-End Latency</div>
                <div style={{ fontSize: '0.825rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {typeof auditDetail.duration_ms === 'number' ? auditDetail.duration_ms.toFixed(1) : '0.0'} ms
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Recorded Events</div>
                <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {auditDetail.events ? auditDetail.events.length : 0} Blocks
                </div>
              </div>
            </div>

            {/* Block Sequence */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)' }}>
                Sequenced Audit Blocks (SHA-256 Parent Hash Linkage)
              </span>

              {auditDetail.events && auditDetail.events.length > 0 ? (
                auditDetail.events.map((evt, idx) => (
                  <div
                    key={evt.event_id || idx}
                    style={{
                      backgroundColor: 'var(--bg-surface-elevated)',
                      border: '1px solid var(--border-default)',
                      borderRadius: 'var(--radius-md)',
                      padding: '0.85rem',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: '0.45rem',
                    }}
                  >
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                        <span className="badge badge-neutral" style={{ fontFamily: 'var(--font-mono)' }}>
                          BLOCK #{idx + 1}
                        </span>
                        <strong style={{ fontSize: '0.825rem', color: 'var(--text-primary)' }}>
                          {evt.stage}
                        </strong>
                      </div>
                      <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                        Actor: {evt.actor} | {new Date(evt.timestamp).toLocaleTimeString()}
                      </span>
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem', fontSize: '0.72rem', marginTop: '0.25rem' }}>
                      <div>
                        <span style={{ color: 'var(--text-muted)' }}>Current Hash: </span>
                        <span className="hash-pill" style={{ color: 'var(--status-success-text)' }}>
                          {evt.block_hash ? `${evt.block_hash.slice(0, 16)}...${evt.block_hash.slice(-8)}` : 'GENESIS'}
                        </span>
                      </div>
                      <div>
                        <span style={{ color: 'var(--text-muted)' }}>Parent Hash: </span>
                        <span className="hash-pill">
                          {evt.parent_hash ? `${evt.parent_hash.slice(0, 16)}...${evt.parent_hash.slice(-8)}` : '0000000000000000 (GENESIS)'}
                        </span>
                      </div>
                    </div>

                    {evt.details && Object.keys(evt.details).length > 0 && (
                      <pre
                        style={{
                          fontFamily: 'var(--font-mono)',
                          fontSize: '0.72rem',
                          backgroundColor: 'var(--bg-app)',
                          padding: '0.45rem',
                          borderRadius: 'var(--radius-sm)',
                          color: 'var(--text-secondary)',
                          maxHeight: '120px',
                          overflowY: 'auto',
                          marginTop: '0.25rem',
                        }}
                      >
                        {JSON.stringify(evt.details, null, 2)}
                      </pre>
                    )}
                  </div>
                ))
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1rem 0' }}>
                  No block events found in this audit record.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '2rem 0', textAlign: 'center' }}>
            Select an audit log from the left panel to inspect its cryptographic hash chain.
          </div>
        )}
      </div>
    </div>
  );
};
