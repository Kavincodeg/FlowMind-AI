import React from 'react';
import type { Persona, UserRole } from '../types';
import { ShieldIcon, UserIcon } from './Icons';
import { Badge } from './ui';

interface HeaderProps {
  personas: Persona[];
  activePersona: Persona | null;
  onSelectPersona: (persona: Persona) => void;
  isBackendHealthy: boolean;
}

export const getRolePlainTitle = (role: UserRole | string): string => {
  switch (role) {
    case 'support_agent':
      return 'Tier 1 Agent';
    case 'team_lead':
      return 'Team Lead';
    case 'team_manager':
      return 'Team Manager';
    case 'department_head':
      return 'Department Head';
    case 'executive':
      return 'Executive';
    case 'finance_reviewer':
      return 'Finance Reviewer';
    case 'vp_finance':
      return 'VP Finance';
    case 'system_admin':
      return 'System Administrator';
    default:
      return role;
  }
};

export const getRoleCapabilitySummary = (role: UserRole | string): string => {
  switch (role) {
    case 'support_agent':
      return 'Standard resolutions. Refunds up to $50';
    case 'team_lead':
      return 'Everything a Tier 1 Agent can. Re-routing within the team. L1 escalations. Refunds up to $200. Closing a case without resolution when the customer is unreachable';
    case 'team_manager':
      return 'Everything a Team Lead can. L2 escalations. Accepting or releasing a cross-team transfer. Refunds up to $500. Reversing an escalation. Restricting an abusive customer to email';
    case 'department_head':
      return 'Everything a Team Manager can, except refunds above $500. L3 escalations. Policy exceptions. Emergency authorisations';
    case 'executive':
      return 'Everything a Department Head can. L4 escalations';
    case 'finance_reviewer':
      return 'Refunds from $51 up to $1,000. Nothing else';
    case 'vp_finance':
      return 'Refunds of any amount. Nothing else';
    case 'system_admin':
      return 'Nothing. Manages accounts, settings and policy documents only';
    default:
      return 'Standard access';
  }
};

export const Header: React.FC<HeaderProps> = ({
  personas,
  activePersona,
  onSelectPersona,
  isBackendHealthy,
}) => {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo" title="FlowMind AI Support Assistant">
          <ShieldIcon size={18} />
        </div>
        <div>
          <div className="brand-title">FlowMind AI</div>
          <span className="brand-subtitle">Everyday Customer Support Assistant — Safe &amp; Auditable Actions</span>
        </div>
      </div>

      <div className="header-controls">
        <div className="api-status-badge">
          <span className={`status-dot ${isBackendHealthy ? '' : 'offline'}`} />
          <span>{isBackendHealthy ? 'System Connected' : 'System Offline'}</span>
        </div>

        {activePersona && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-1)', color: 'var(--text-muted)' }}>
              <UserIcon size={14} />
              <span style={{ fontSize: 'var(--text-xs)', fontWeight: 500 }}>Signed in as:</span>
            </div>

            <select
              className="form-select"
              style={{ padding: 'var(--space-1) var(--space-3)', fontSize: 'var(--text-xs)', fontWeight: 500, maxWidth: '420px' }}
              value={activePersona.user_id}
              onChange={(e) => {
                const found = personas.find((p) => p.user_id === e.target.value);
                if (found) onSelectPersona(found);
              }}
              aria-label="Select active team member"
            >
              {personas.map((p) => (
                <option key={p.user_id} value={p.user_id}>
                  {p.name} — {getRoleCapabilitySummary(p.role)}
                </option>
              ))}
            </select>

            <Badge
              variant={
                activePersona.role === 'system_admin'
                  ? 'danger'
                  : activePersona.role === 'finance_reviewer' || activePersona.role === 'vp_finance'
                  ? 'success'
                  : activePersona.role === 'team_manager' || activePersona.role === 'department_head' || activePersona.role === 'executive' || activePersona.role === 'team_lead'
                  ? 'warning'
                  : 'neutral'
              }
              style={{ letterSpacing: '0.02em', whiteSpace: 'nowrap' }}
              title={getRoleCapabilitySummary(activePersona.role)}
            >
              {getRolePlainTitle(activePersona.role)} ({activePersona.role})
            </Badge>
          </div>
        )}
      </div>
    </header>
  );
};
