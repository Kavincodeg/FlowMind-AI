import React, { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import type { AuditListItem, AuditTrail, ChainVerificationResult, Persona } from '../types';
import { api } from '../api';
import { CheckCircleIcon, RefreshIcon, LayersIcon, ShieldIcon, AlertTriangleIcon } from './Icons';
import { getPlainStatusLabel } from './HomeView';
import { LoadingState } from './ui';

interface AuditExplorerProps {
  currentWorkflowId?: string | null;
  activePersona: Persona;
}

export const AuditExplorer: React.FC<AuditExplorerProps> = ({
  currentWorkflowId,
  activePersona,
}) => {
  const { workflowId: routeWorkflowId } = useParams<{ workflowId?: string }>();
  const navigate = useNavigate();

  const [auditList, setAuditList] = useState<AuditListItem[]>([]);
  const [selectedWorkflowId, setSelectedWorkflowId] = useState<string | null>(
    routeWorkflowId || currentWorkflowId || null
  );
  const [auditDetail, setAuditDetail] = useState<AuditTrail | null>(null);
  const [chainVerification, setChainVerification] = useState<ChainVerificationResult | null>(null);
  const [isLoadingList, setIsLoadingList] = useState(false);
  const [isLoadingDetail, setIsLoadingDetail] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync selectedWorkflowId when route parameter changes
  useEffect(() => {
    if (routeWorkflowId && routeWorkflowId !== selectedWorkflowId) {
      setSelectedWorkflowId(routeWorkflowId);
    }
  }, [routeWorkflowId]);

  const fetchAudits = async () => {
    setIsLoadingList(true);
    setError(null);
    try {
      const items = await api.listAudits(activePersona.token);
      setAuditList(items);
      if (!selectedWorkflowId && items.length > 0) {
        const firstId = routeWorkflowId || currentWorkflowId || items[0].workflow_id;
        setSelectedWorkflowId(firstId);
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
    setChainVerification(null);
    try {
      const [detail, verification] = await Promise.all([
        api.getWorkflowAudit(wfId, activePersona.token) as Promise<AuditTrail>,
        api.verifyAuditChain(wfId, activePersona.token),
      ]);
      setAuditDetail(detail);
      setChainVerification(verification);
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

  const handleSelectCase = (wfId: string) => {
    setSelectedWorkflowId(wfId);
    navigate(`/trust/${wfId}`);
  };

  const chainValid = chainVerification?.valid ?? null;
  const failedAtIndex = chainVerification?.failed_at_index ?? null;

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '320px 1fr', gap: '1.25rem', alignItems: 'start' }}>
      {/* 1. Past Cases List Column */}
      <div className="console-panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <LayersIcon size={16} /> Workflow Audit Logs — Past Cases
            </div>
            <span style={{ fontSize: '0.725rem', color: 'var(--text-muted)' }}>
              Nothing gets forgotten: every case is logged
            </span>
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
          <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1.5rem 0', textAlign: 'center' }}>
            No past cases recorded yet. Run a case to see its full tamper-evident record here.
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem', maxHeight: '580px', overflowY: 'auto' }}>
            {auditList.map((item) => {
              const isSelected = item.workflow_id === selectedWorkflowId;
              const statusInfo = getPlainStatusLabel(item.terminal_state);
              return (
                <button
                  key={item.audit_id}
                  type="button"
                  className={`scenario-card ${isSelected ? 'active' : ''}`}
                  onClick={() => handleSelectCase(item.workflow_id)}
                >
                  <div className="scenario-card-header">
                    <span className="scenario-title" style={{ fontFamily: 'var(--font-mono)' }}>
                      Case {item.workflow_id}
                    </span>
                    <span className={`badge ${statusInfo.badgeClass}`} style={{ fontSize: '0.65rem' }}>
                      {statusInfo.label}
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

      {/* 2. Trust & Proof Chain Inspector Column */}
      <div className="console-panel">
        <div className="panel-header" style={{ alignItems: 'flex-start', flexWrap: 'wrap', gap: '0.75rem' }}>
          <div>
            <div className="panel-title" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <ShieldIcon size={18} /> Trust &amp; Proof — Cryptographic SHA-256 Hash Chain Inspector
            </div>
            <span style={{ fontSize: '0.775rem', color: 'var(--text-secondary)', marginTop: '0.2rem', display: 'block' }}>
              <strong>Nobody can quietly change it afterwards.</strong> Every decision, check, and action is permanently locked in sequence.
            </span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            {selectedWorkflowId && (
              <div style={{ display: 'flex', gap: '0.4rem' }}>
                <Link
                  to={`/cases/${selectedWorkflowId}`}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.725rem', padding: '0.25rem 0.5rem', textDecoration: 'none' }}
                >
                  Timeline
                </Link>
                <Link
                  to={`/investigate/${selectedWorkflowId}`}
                  className="btn btn-secondary"
                  style={{ fontSize: '0.725rem', padding: '0.25rem 0.5rem', textDecoration: 'none' }}
                >
                  Investigation
                </Link>
              </div>
            )}

            {chainValid !== null && (
              <span
                className={`badge ${chainValid ? 'badge-success' : 'badge-danger'}`}
                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.35rem 0.65rem', fontSize: '0.75rem' }}
              >
                <CheckCircleIcon size={14} />
                {chainValid
                  ? `Checked just now — nothing has been altered (Cryptographic Chain Verified (Intact) — ${chainVerification?.chain_length ?? 0} blocks)`
                  : `Tampering detected at block #${(failedAtIndex ?? 0) + 1} (${chainVerification?.failed_event_id ?? 'unknown'})`}
              </span>
            )}
          </div>
        </div>

        {/* Honest Limits Disclosure Card */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-default)',
            borderLeft: '4px solid var(--accent-primary)',
            borderRadius: 'var(--radius-md)',
            padding: '0.85rem 1rem',
            marginBottom: '1rem',
          }}
        >
          <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
            <AlertTriangleIcon size={14} /> Being honest about the limits
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem', lineHeight: 1.45 }}>
            Tamper-evident logs show that nobody altered, deleted, or inserted a record after it was written. They do not guarantee that the original information entered by a person or external system was 100% correct in the first place. Human accountability and review remain essential.
          </div>
        </div>

        {isLoadingDetail ? (
          <LoadingState message="Checking tamper-evident seals for this case..." />
        ) : auditDetail ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Plain Summary Metric Cards */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '0.75rem' }}>
              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Audit Record ID</div>
                <div style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {auditDetail.audit_id}
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Terminal State</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {getPlainStatusLabel(auditDetail.terminal_state).label}
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>End-to-End Latency</div>
                <div style={{ fontSize: '0.8rem', fontFamily: 'var(--font-mono)', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {typeof auditDetail.duration_ms === 'number' ? auditDetail.duration_ms.toFixed(1) : '0.0'} ms
                </div>
              </div>

              <div style={{ backgroundColor: 'var(--bg-surface-elevated)', padding: '0.75rem', borderRadius: 'var(--radius-md)' }}>
                <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Recorded Events</div>
                <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
                  {auditDetail.chain_events ? auditDetail.chain_events.length : 0} Blocks
                </div>
              </div>
            </div>

            {/* Block Sequence in Plain Language */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.04em' }}>
                  Sequenced Audit Blocks (SHA-256 Parent Hash Linkage)
                </span>
                <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>
                  Chronological sequence — each block seals the previous one
                </span>
              </div>

              {auditDetail.chain_events && auditDetail.chain_events.length > 0 ? (
                auditDetail.chain_events.map((evt, idx) => {
                  const isFailed = failedAtIndex !== null && idx === failedAtIndex;
                  return (
                    <div
                      key={evt.event_id || idx}
                      style={{
                        backgroundColor: 'var(--bg-surface-elevated)',
                        border: isFailed ? '1px solid var(--status-danger-border)' : '1px solid var(--border-default)',
                        borderRadius: 'var(--radius-md)',
                        padding: '0.85rem 1rem',
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.4rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span className="badge badge-neutral" style={{ fontSize: '0.7rem' }}>
                            BLOCK #{idx + 1}
                          </span>
                          <span style={{ fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                            {evt.stage}
                          </span>
                        </div>
                        <span style={{ fontSize: '0.72rem', color: 'var(--text-muted)' }}>
                          {new Date(evt.timestamp).toLocaleTimeString()}
                        </span>
                      </div>

                      <div style={{ display: 'grid', gridTemplateColumns: '1fr', gap: '0.35rem', fontSize: '0.75rem', marginTop: '0.5rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ color: 'var(--text-muted)', minWidth: '95px' }}>Current Hash:</span>
                          <span className="hash-pill" style={{ color: isFailed ? 'var(--status-danger-text)' : 'var(--accent-primary)', wordBreak: 'break-all' }}>
                            {evt.block_hash}
                          </span>
                        </div>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                          <span style={{ color: 'var(--text-muted)', minWidth: '95px' }}>Parent Hash:</span>
                          <span className="hash-pill" style={{ wordBreak: 'break-all' }}>
                            {evt.parent_hash}
                          </span>
                        </div>
                      </div>

                      {evt.details && Object.keys(evt.details).length > 0 && (
                        <details style={{ marginTop: '0.5rem', fontSize: '0.75rem' }}>
                          <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}>
                            View Raw Block Payload
                          </summary>
                          <pre
                            style={{
                              backgroundColor: 'var(--bg-app)',
                              padding: '0.5rem',
                              borderRadius: 'var(--radius-sm)',
                              maxHeight: '160px',
                              overflowY: 'auto',
                              marginTop: '0.25rem',
                            }}
                          >
                            {JSON.stringify(evt.details, null, 2)}
                          </pre>
                        </details>
                      )}
                    </div>
                  );
                })
              ) : (
                <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', padding: '1rem 0' }}>
                  No block events found in this audit record.
                </div>
              )}
            </div>
          </div>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '2rem 0', textAlign: 'center' }}>
            Select a case from the left to view its proof chain.
          </div>
        )}
      </div>
    </div>
  );
};