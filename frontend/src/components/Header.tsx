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
      return 'Customer Support';
    case 'team_lead':
      return 'Team Lead';
    case 'manager':
      return 'Manager';
    case 'admin':
      return 'System Admin';
    default:
      return role;
  }
};

export const getRoleCapabilitySummary = (role: UserRole | string): string => {
  switch (role) {
    case 'support_agent':
      return 'Customer support — everyday questions, basic information, and standard help';
    case 'team_lead':
      return 'Team lead — everyday requests, plus moving things between teams and first-level escalations';
    case 'manager':
      return 'Manager — everything team leads can do, plus money refunds and higher escalations';
    case 'admin':
      return 'System admin — full access to all decisions, executive escalations, and system settings';
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
                activePersona.role === 'admin'
                  ? 'danger'
                  : activePersona.role === 'manager' || activePersona.role === 'team_lead'
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
