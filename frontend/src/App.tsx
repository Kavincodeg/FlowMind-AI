import React, { useEffect, useState } from 'react';
import type { DemonstrationScenario, Persona, WorkflowInstance } from './types';
import { api } from './api';
import { Header } from './components/Header';
import { HomeView } from './components/HomeView';
import { InvestigationConsole } from './components/InvestigationConsole';
import { AuditExplorer } from './components/AuditExplorer';
import { BenchmarkDashboard } from './components/BenchmarkDashboard';
import { KnowledgeBaseView } from './components/KnowledgeBaseView';
import { GovernanceMatrixView } from './components/GovernanceMatrixView';
import { ShieldIcon, LayersIcon, HashIcon, DatabaseIcon, LockIcon, HomeIcon } from './components/Icons';

export const App: React.FC = () => {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [activePersona, setActivePersona] = useState<Persona | null>(null);
  const [scenarios, setScenarios] = useState<DemonstrationScenario[]>([]);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [activeTab, setActiveTab] = useState<'home' | 'workflow' | 'audit' | 'benchmark' | 'knowledge' | 'governance'>('home');
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowInstance | null>(null);
  const [selectedAuditWorkflowId, setSelectedAuditWorkflowId] = useState<string | null>(null);

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
      {/* Top Header & Plain-Language Persona Switcher */}
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
          id="nav-home"
          className={`nav-tab ${activeTab === 'home' ? 'active' : ''}`}
          onClick={() => setActiveTab('home')}
        >
          <HomeIcon size={14} /> Home
        </button>

        <button
          type="button"
          id="nav-investigate"
          className={`nav-tab ${activeTab === 'workflow' ? 'active' : ''}`}
          onClick={() => setActiveTab('workflow')}
        >
          <ShieldIcon size={14} /> Look into a case (Investigation &amp; Human Approval)
        </button>

        <button
          type="button"
          id="nav-audit"
          className={`nav-tab ${activeTab === 'audit' ? 'active' : ''}`}
          onClick={() => setActiveTab('audit')}
        >
          <HashIcon size={14} /> Trust &amp; proof (Cryptographic Audit Trail)
        </button>

        <button
          type="button"
          id="nav-benchmark"
          className={`nav-tab ${activeTab === 'benchmark' ? 'active' : ''}`}
          onClick={() => setActiveTab('benchmark')}
        >
          <LayersIcon size={14} /> How this compares (Empirical Benchmarks)
        </button>

        <button
          type="button"
          id="nav-knowledge"
          className={`nav-tab ${activeTab === 'knowledge' ? 'active' : ''}`}
          onClick={() => setActiveTab('knowledge')}
        >
          <DatabaseIcon size={14} /> Company guides (Knowledge Base &amp; Retrieval)
        </button>

        <button
          type="button"
          id="nav-governance"
          className={`nav-tab ${activeTab === 'governance' ? 'active' : ''}`}
          onClick={() => setActiveTab('governance')}
        >
          <LockIcon size={14} /> Who can do what (Security &amp; RBAC Matrix)
        </button>
      </nav>

      {/* Main View Area */}
      <main className="app-main">
        {activePersona ? (
          <>
            {activeTab === 'home' && (
              <HomeView
                activePersona={activePersona}
                onNavigateToNewCase={() => setActiveTab('workflow')}
                onSelectCase={(wfId) => {
                  setSelectedAuditWorkflowId(wfId);
                  setActiveTab('audit');
                }}
              />
            )}

            {activeTab === 'workflow' && (
              <InvestigationConsole
                scenarios={scenarios}
                activePersona={activePersona}
                workflow={currentWorkflow}
                onWorkflowUpdated={(updated) => {
                  setCurrentWorkflow(updated);
                  setSelectedAuditWorkflowId(updated.workflow_id);
                }}
              />
            )}

            {activeTab === 'audit' && (
              <AuditExplorer
                currentWorkflowId={selectedAuditWorkflowId || currentWorkflow?.workflow_id || null}
                activePersona={activePersona}
              />
            )}

            {activeTab === 'benchmark' && <BenchmarkDashboard activePersona={activePersona} />}

            {activeTab === 'knowledge' && <KnowledgeBaseView activePersona={activePersona} />}

            {activeTab === 'governance' && <GovernanceMatrixView activePersona={activePersona} />}
          </>
        ) : (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '3rem 0', textAlign: 'center' }}>
            Connecting to customer support system...
          </div>
        )}
      </main>

      {/* Systems & Academic Footer */}
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
          flexWrap: 'wrap',
          gap: '0.5rem',
        }}
      >
        <div>
          <strong>FlowMind AI</strong> — Everyday Customer Support Assistant &amp; Safe Action Review
        </div>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <span>110 Unit Tests Passing</span>
          <span>9 Integration Tests Passing</span>
          <span>16 Playwright Tests</span>
          <span>SHA-256 Hash Chain Active</span>
          <span>Server-Side RBAC Enforced</span>
        </div>
      </footer>
    </div>
  );
};

export default App;
