import React from 'react';
import { ShieldIcon, LockIcon } from './Icons';

export const AdminLandingView: React.FC = () => {
  return (
    <div style={{ maxWidth: '720px', margin: '2rem auto' }}>
      <div className="console-panel" style={{ textAlign: 'center', padding: '3rem 2rem' }}>
        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: '64px',
            height: '64px',
            borderRadius: '50%',
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-default)',
            marginBottom: '1.25rem',
            color: 'var(--brand-primary)',
          }}
        >
          <LockIcon size={32} />
        </div>

        <h1
          id="admin-landing-title"
          style={{
            fontSize: '1.75rem',
            fontWeight: 700,
            color: 'var(--text-primary)',
            marginBottom: '1rem',
          }}
        >
          Account and settings management is coming
        </h1>

        <p
          style={{
            fontSize: '0.95rem',
            color: 'var(--text-secondary)',
            lineHeight: 1.6,
            maxWidth: '540px',
            margin: '0 auto 1.5rem',
          }}
        >
          System Administrators manage system configuration, user accounts, and infrastructure.
          Under company policy and the Approval Authority Matrix, System Administrators have no
          approval authority and no access to customer case data.
        </p>

        <div
          style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.6rem 1rem',
            backgroundColor: 'var(--bg-surface-elevated)',
            border: '1px solid var(--border-default)',
            borderRadius: 'var(--radius-md)',
            fontSize: '0.8rem',
            color: 'var(--text-muted)',
          }}
        >
          <ShieldIcon size={14} />
          <span>Case investigation, audit logs, and workflow decisions are restricted to operational roles.</span>
        </div>
      </div>
    </div>
  );
};
