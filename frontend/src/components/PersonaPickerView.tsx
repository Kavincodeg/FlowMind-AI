import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { getRoleCapabilitySummary, getRolePlainTitle } from './Header';
import { ShieldIcon, UserIcon, ArrowRightIcon } from './Icons';
import type { Persona } from '../types';

export const PersonaPickerView: React.FC = () => {
  const { personas, activePersona, setActivePersona } = useAppContext();
  const navigate = useNavigate();

  const handleSelect = (persona: Persona) => {
    setActivePersona(persona);
    navigate('/home');
  };

  return (
    <div style={{ maxWidth: '850px', margin: '2rem auto', display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '0 1rem' }}>
      <div className="console-panel" style={{ padding: '2rem', textAlign: 'center' }}>
        <div style={{ display: 'inline-flex', padding: '0.75rem', borderRadius: '50%', backgroundColor: 'var(--bg-surface-elevated)', marginBottom: '0.75rem' }}>
          <ShieldIcon size={32} />
        </div>
        <h1 style={{ fontSize: '1.75rem', fontWeight: 700, margin: '0 0 0.5rem 0', color: 'var(--text-primary)' }}>
          Select Your Team Role &amp; Identity
        </h1>
        <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0, maxWidth: '600px', marginInline: 'auto', lineHeight: 1.5 }}>
          FlowMind AI enforces strict server-side Role-Based Access Control (RBAC). Pick a team persona below to see how customer complaints, decisions, and approval boundaries work for each role.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: '1rem' }}>
        {personas.map((persona) => {
          const isCurrent = activePersona?.user_id === persona.user_id;
          return (
            <div
              key={persona.user_id}
              className="console-panel"
              style={{
                padding: '1.5rem',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '1rem',
                border: isCurrent ? '2px solid var(--accent-primary)' : '1px solid var(--border-default)',
                backgroundColor: isCurrent ? 'var(--bg-surface-elevated)' : 'var(--bg-surface)',
                position: 'relative',
              }}
            >
              {isCurrent && (
                <div
                  style={{
                    position: 'absolute',
                    top: '0.75rem',
                    right: '0.75rem',
                    fontSize: '0.675rem',
                    fontWeight: 600,
                    backgroundColor: 'var(--accent-primary)',
                    color: '#ffffff',
                    padding: '0.2rem 0.5rem',
                    borderRadius: 'var(--radius-sm)',
                  }}
                >
                  Active Identity
                </div>
              )}

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                  <UserIcon size={16} />
                  <span style={{ fontWeight: 700, fontSize: '1.1rem', color: 'var(--text-primary)' }}>
                    {persona.name}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                  <span
                    className={`badge ${
                      persona.role === 'admin'
                        ? 'badge-danger'
                        : persona.role === 'manager' || persona.role === 'team_lead'
                        ? 'badge-warning'
                        : 'badge-neutral'
                    }`}
                  >
                    {getRolePlainTitle(persona.role)} ({persona.role})
                  </span>
                  <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                    ID: {persona.user_id}
                  </span>
                </div>

                <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: 1.45, margin: 0 }}>
                  {getRoleCapabilitySummary(persona.role)}
                </p>
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: '0.85rem' }}>
                <button
                  type="button"
                  className={`btn ${isCurrent ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ width: '100%', display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '0.5rem' }}
                  onClick={() => handleSelect(persona)}
                >
                  <span>{isCurrent ? 'Continue as ' + persona.name : 'Switch to ' + persona.name}</span>
                  <ArrowRightIcon size={14} />
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
