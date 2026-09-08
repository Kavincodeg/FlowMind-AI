import React from 'react';
import type { Persona } from '../types';
import { ShieldIcon, UserIcon } from './Icons';

interface HeaderProps {
  personas: Persona[];
  activePersona: Persona | null;
  onSelectPersona: (persona: Persona) => void;
  isBackendHealthy: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  personas,
  activePersona,
  onSelectPersona,
  isBackendHealthy,
}) => {
  return (
    <header className="app-header">
      <div className="brand-section">
        <div className="brand-logo" title="FlowMind AI Governance">
          <ShieldIcon size={18} />
        </div>
        <div>
          <div className="brand-title">FlowMind AI</div>
          <span className="brand-subtitle">Evidence-Grounded Enterprise Governance & Workflow Agent</span>
        </div>
      </div>

      <div className="header-controls">
        <div className="api-status-badge">
          <span className={`status-dot ${isBackendHealthy ? '' : 'offline'}`} />
          <span>{isBackendHealthy ? 'FastAPI Connected' : 'API Offline'}</span>
        </div>

        {activePersona && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', color: 'var(--text-muted)' }}>
              <UserIcon size={14} />
              <span style={{ fontSize: '0.75rem', fontWeight: 500 }}>Active Persona:</span>
            </div>

            <select
              className="form-select"
              style={{ padding: '0.35rem 0.65rem', fontSize: '0.8rem', fontWeight: 500 }}
              value={activePersona.user_id}
              onChange={(e) => {
                const found = personas.find((p) => p.user_id === e.target.value);
                if (found) onSelectPersona(found);
              }}
            >
              {personas.map((p) => (
                <option key={p.user_id} value={p.user_id}>
                  {p.name} ({p.role}) — {p.department}
                </option>
              ))}
            </select>

            <span
              className={`badge ${
                activePersona.role === 'admin'
                  ? 'badge-danger'
                  : activePersona.role === 'manager' || activePersona.role === 'team_lead'
                  ? 'badge-warning'
                  : 'badge-neutral'
              }`}
              style={{ textTransform: 'uppercase', letterSpacing: '0.04em' }}
            >
              {activePersona.role}
            </span>
          </div>
        )}
      </div>
    </header>
  );
};
