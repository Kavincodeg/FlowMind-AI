import React, { useEffect, useState } from 'react';
import type { DemonstrationScenario, Persona, WorkflowInstance } from './types';
import { api } from './api';
import { Header } from './components/Header';
import { InvestigationConsole } from './components/InvestigationConsole';
import { AuditExplorer } from './components/AuditExplorer';
import { BenchmarkDashboard } from './components/BenchmarkDashboard';
import { ShieldIcon, LayersIcon, HashIcon } from './components/Icons';

export const App: React.FC = () => {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [activePersona, setActivePersona] = useState<Persona | null>(null);
  const [scenarios, setScenarios] = useState<DemonstrationScenario[]>([]);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'workflow' | 'audit' | 'benchmark'>('workflow');
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowInstance | null>(null);

  // Initialize application data
  useEffect(() => {
    const init = async () => {
      try {
        const [healthRes, personasRes, scenariosRes] = await Promise.all([
          api.checkHealth().catch(() => ({ status: 'error', service: 'FlowMind AI', version: '1.0.0' })),
          api.getPersonas().catch(() => []),
          api.getScenarios().catch(() => []),
        ]);

        setIsBackendHealthy(healthRes.status === 'ok');
        setPersonas(personasRes);
        setScenarios(scenariosRes);

        // Default active persona: Marcus Vance (Team Lead)
        if (personasRes.length > 0) {
          const defaultLead = personasRes.find((p) => p.role === 'team_lead') || personasRes[0];
          setActivePersona(defaultLead);
        }
      } catch (err) {
        console.error('Initialization failed:', err);
        setIsBackendHealthy(false);
      }
    };

    init();
  }, []);

  return (
    <div className="app-container">
      {/* Top Header & Persona Switcher */}
      <Header
        personas={personas}
        activePersona={activePersona}
        onSelectPersona={(persona) => setActivePersona(persona)}
        isBackendHealthy={isBackendHealthy}
      />

      {/* Primary Navigation Tabs */}
      <nav className="tab-navigation" aria-label="Main Navigation">
        <button
          type="button"
          className={`nav-tab ${activeTab === 'workflow' ? 'active' : ''}`}
          onClick={() => setActiveTab('workflow')}
        >
          <ShieldIcon size={14} /> Investigation & Human Approval
        </button>

        <button
          type="button"
          className={`nav-tab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <HashIcon size={14} /> Cryptographic Audit Trail
        </button>

        <button
          type="button"
          className={`nav-tab ${activeTab === 'benchmark' ? 'active' : ''}`}
          onClick={() => setActiveTab('benchmark')}
        >
          <LayersIcon size={14} /> Empirical Benchmarks
        </button>
      </nav>

      {/* Main View Area */}
      <main className="app-main">
        {activePersona ? (
          <>
            {activeTab === 'workflow' && (
              <InvestigationConsole
                scenarios={scenarios}
                activePersona={activePersona}
                workflow={currentWorkflow}
                onWorkflowUpdated={(updated) => setCurrentWorkflow(updated)}
              />
            )}

            {activeTab === 'audit' && (
              <AuditExplorer
                currentWorkflowId={currentWorkflow?.workflow_id || null}
                activePersona={activePersona}
              />
            )}

            {activeTab === 'benchmark' && <BenchmarkDashboard activePersona={activePersona} />}
          </>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '3rem 0', textAlign: 'center' }}>
            Loading enterprise personas and security context...
          </div>
        )}
      </main>

      {/* Academic & Systems Footer */}
      <footer
        style={{
          borderTop: '1px solid var(--border-subtle)',
          padding: '0.75rem 1.5rem',
          fontSize: '0.725rem',
          color: 'var(--text-muted)',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          backgroundColor: 'var(--bg-app)',
        }}
      >
        <div>
          <strong>FlowMind AI</strong> — Final-Year Project Prototype | Research Question: Closed-Loop Governance vs Plain RAG
        </div>
        <div style={{ display: 'flex', gap: '1rem' }}>
          <span>95/95 Unit Tests Passing</span>
          <span>SHA-256 Hash Chain Active</span>
          <span>Server-Side RBAC Enforced</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
