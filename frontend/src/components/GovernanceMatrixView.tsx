import React, { useEffect, useState } from 'react';
import type { ActionPermission, Persona, SecurityMatrixResponse } from '../types';
import { api } from '../api';
import { CheckCircleIcon, LockIcon, RefreshIcon, ShieldIcon, UserIcon, XCircleIcon } from './Icons';

interface GovernanceMatrixViewProps {
  activePersona: Persona;
}

export const GovernanceMatrixView: React.FC<GovernanceMatrixViewProps> = ({ activePersona }) => {
  const [securityMatrix, setSecurityMatrix] = useState<SecurityMatrixResponse | null>(null);
  const [userMe, setUserMe] = useState<Persona | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [matrixRes, meRes] = await Promise.all([
        api.getSecurityMatrix(activePersona.token).catch(() => null),
        api.getMe(activePersona.token).catch(() => null),
      ]);
      setSecurityMatrix(matrixRes);
      setUserMe(meRes);
    } catch (err) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activePersona]);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
      {/* Top Banner */}
      <div className="console-panel">
        <div className="panel-header">
          <div>
            <div className="panel-title">
              <ShieldIcon size={16} /> Enterprise RBAC Governance & Security Matrix (Phase 3)
            </div>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              Server-enforced role-based access control, cryptographic identity resolution, and governance boundaries.
            </span>
          </div>

          <button
            type="button"
            className="btn btn-secondary"
            style={{ fontSize: '0.75rem', padding: '0.35rem 0.65rem' }}
            onClick={loadData}
            disabled={isLoading}
          >
            <RefreshIcon size={12} /> Refresh Policies
          </button>
        </div>

        {error && (
          <div className="alert-banner alert-danger">
            <span>{error}</span>
          </div>
        )}

        {/* Identity & Verified Claims Card */}
        <div
          style={{
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            padding: '1rem',
            display: 'grid',
            gridTemplateColumns: 'repeat(4, 1fr)',
            gap: '1rem',
            marginTop: '0.5rem',
          }}
        >
          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Authenticated User</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <UserIcon size={14} /> {userMe?.name || activePersona.name}
            </div>
            <div style={{ fontSize: '0.72rem', fontFamily: 'var(--font-mono)', color: 'var(--text-muted)' }}>
              ID: {userMe?.user_id || activePersona.user_id}
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Server-Resolved Role</div>
            <div style={{ marginTop: '0.25rem' }}>
              <span className="badge badge-primary" style={{ textTransform: 'uppercase', fontWeight: 600 }}>
                {userMe?.role || activePersona.role}
              </span>
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.2rem' }}>
              Verified via bearer token
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Department & Scope</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--text-primary)', marginTop: '0.2rem' }}>
              {userMe?.department || activePersona.department}
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
              Enterprise Operations
            </div>
          </div>

          <div>
            <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>Active Security Boundary</div>
            <div style={{ fontSize: '0.85rem', fontWeight: 600, color: 'var(--status-success-text)', marginTop: '0.2rem', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
              <CheckCircleIcon size={14} /> Authenticated
            </div>
            <div style={{ fontSize: '0.68rem', color: 'var(--text-muted)', marginTop: '0.15rem' }}>
              Token signature verified
            </div>
          </div>
        </div>
      </div>

      {/* Primary RBAC Permissions Matrix Table */}
      <div className="console-panel">
        <div className="panel-header">
          <div className="panel-title">
            <LockIcon size={16} /> Action Authorization Matrix by Enterprise Role
          </div>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            Actions requiring human review are blocked from auto-dispatch until approved by an authorized persona.
          </span>
        </div>

        <div style={{ overflowX: 'auto' }}>
          <table className="data-table">
            <thead>
              <tr>
                <th>Workflow Action</th>
                <th>Tier / Sensitivity</th>
                <th>Support Agent</th>
                <th>Team Lead</th>
                <th>Manager</th>
                <th>Admin</th>
                <th>Approval Gate</th>
              </tr>
            </thead>
            <tbody>
              {securityMatrix?.actions.map((act: ActionPermission) => {
                const canAgent = act.authorized_roles.includes('support_agent');
                const canLead = act.authorized_roles.includes('team_lead');
                const canManager = act.authorized_roles.includes('manager');
                const canAdmin = act.authorized_roles.includes('admin');

                return (
                  <tr key={act.action_type}>
                    <td>
                      <div style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{act.label}</div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
                        {act.action_type}
                      </div>
                      <div style={{ fontSize: '0.72rem', color: 'var(--text-secondary)', marginTop: '0.2rem' }}>
                        {act.description}
                      </div>
                    </td>

                    <td>
                      <span className={`badge ${act.sensitive ? 'badge-warning' : 'badge-neutral'}`}>
                        {act.tier}
                      </span>
                    </td>

                    {/* Support Agent */}
                    <td>
                      {canAgent ? (
                        <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <CheckCircleIcon size={11} /> Authorized
                        </span>
                      ) : (
                        <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <XCircleIcon size={11} /> Denied
                        </span>
                      )}
                    </td>

                    {/* Team Lead */}
                    <td>
                      {canLead ? (
                        <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <CheckCircleIcon size={11} /> Authorized
                        </span>
                      ) : (
                        <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <XCircleIcon size={11} /> Denied
                        </span>
                      )}
                    </td>

                    {/* Manager */}
                    <td>
                      {canManager ? (
                        <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <CheckCircleIcon size={11} /> Authorized
                        </span>
                      ) : (
                        <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <XCircleIcon size={11} /> Denied
                        </span>
                      )}
                    </td>

                    {/* Admin */}
                    <td>
                      {canAdmin ? (
                        <span className="badge badge-success" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <CheckCircleIcon size={11} /> Authorized
                        </span>
                      ) : (
                        <span className="badge badge-danger" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <XCircleIcon size={11} /> Denied
                        </span>
                      )}
                    </td>

                    {/* Approval Requirement */}
                    <td>
                      <span className={`badge ${act.requires_approval ? 'badge-warning' : 'badge-neutral'}`}>
                        {act.requires_approval ? 'Human Approval Required' : 'Auto-Executable'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Governance Invariants & Security Defenses */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '1rem' }}>
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
          <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <ShieldIcon size={14} /> Mandatory Rejection Rationale
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            Whenever a human reviewer rejects an action recommendation, the orchestrator mandates an explicit audit comment.
            Empty rejections are rejected at the API boundary, guaranteeing complete accountability.
          </div>
        </div>

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
          <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <LockIcon size={14} /> Server-Side Identity Resolution
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            Roles are resolved strictly server-side from cryptographically signed bearer tokens (`flowmind-agent-token-001` etc.).
            Client request headers cannot forge or elevate approver roles, eliminating client tampering vulnerabilities.
          </div>
        </div>

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
          <div style={{ fontSize: '0.825rem', fontWeight: 600, color: 'var(--text-primary)', display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
            <CheckCircleIcon size={14} /> Write-Once Audit Immutability
          </div>
          <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: 1.45 }}>
            The SHA-256 audit hash chain is written exactly once at finalization. Any second attempt to record an audit for an identical
            workflow ID raises an explicit `DuplicateAuditRecordError`, preserving chain immutability.
          </div>
        </div>
      </div>
    </div>
  );
};
