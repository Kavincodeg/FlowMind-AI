import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAppContext } from '../context/AppContext';
import { getRoleCapabilitySummary, getRolePlainTitle } from './Header';
import { ShieldIcon, UserIcon, ArrowRightIcon } from './Icons';
import { Button, Badge } from './ui';
import type { Persona } from '../types';

export const PersonaPickerView: React.FC = () => {
  const { personas, activePersona, setActivePersona } = useAppContext();
  const navigate = useNavigate();

  const handleSelect = (persona: Persona) => {
    setActivePersona(persona);
    navigate('/home');
  };

  return (
    <div className="page-container" style={{ maxWidth: '850px' }}>
      <div className="console-panel" style={{ padding: 'var(--space-8)', textAlign: 'center' }}>
        <div style={{ display: 'inline-flex', padding: 'var(--space-3)', borderRadius: '50%', backgroundColor: 'var(--bg-surface-elevated)', marginBottom: 'var(--space-3)' }}>
          <ShieldIcon size={32} />
        </div>
        <h1 className="page-title" style={{ textAlign: 'center', marginBottom: 'var(--space-2)' }}>
          Select Your Team Role &amp; Identity
        </h1>
        <p className="page-subtitle" style={{ maxWidth: '600px', marginInline: 'auto', lineHeight: 1.5 }}>
          FlowMind AI enforces strict server-side Role-Based Access Control (RBAC). Pick a team persona below to see how customer complaints, decisions, and approval boundaries work for each role.
        </p>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(360px, 1fr))', gap: 'var(--space-4)' }}>
        {personas.map((persona) => {
          const isCurrent = activePersona?.user_id === persona.user_id;
          const badgeVariant =
            persona.role === 'admin'
              ? 'danger'
              : persona.role === 'manager' || persona.role === 'team_lead'
              ? 'warning'
              : 'neutral';

          return (
            <div
              key={persona.user_id}
              className={`console-panel ${isCurrent ? 'card-elevated' : ''}`}
              style={{
                padding: 'var(--space-6)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: 'var(--space-4)',
                border: isCurrent ? '2px solid var(--accent-primary)' : '1px solid var(--border-default)',
                position: 'relative',
              }}
            >
              {isCurrent && (
                <div style={{ position: 'absolute', top: 'var(--space-3)', right: 'var(--space-3)' }}>
                  <Badge variant="primary" size="sm">
                    Active Identity
                  </Badge>
                </div>
              )}

              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-1)' }}>
                  <UserIcon size={16} />
                  <span style={{ fontWeight: 700, fontSize: 'var(--text-lg)', color: 'var(--text-primary)' }}>
                    {persona.name}
                  </span>
                </div>

                <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                  <Badge variant={badgeVariant}>
                    {getRolePlainTitle(persona.role)} ({persona.role})
                  </Badge>
                  <span style={{ fontSize: 'var(--text-xs)', color: 'var(--text-muted)' }}>
                    ID: {persona.user_id}
                  </span>
                </div>

                <p style={{ fontSize: 'var(--text-sm)', color: 'var(--text-secondary)', lineHeight: 1.45, margin: 0 }}>
                  {getRoleCapabilitySummary(persona.role)}
                </p>
              </div>

              <div style={{ borderTop: '1px solid var(--border-subtle)', paddingTop: 'var(--space-3)' }}>
                <Button
                  type="button"
                  variant={isCurrent ? 'primary' : 'secondary'}
                  style={{ width: '100%' }}
                  onClick={() => handleSelect(persona)}
                  icon={<ArrowRightIcon size={14} />}
                >
                  {isCurrent ? 'Continue as ' + persona.name : 'Switch to ' + persona.name}
                </Button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
