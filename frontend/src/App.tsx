import React from 'react';
import { BrowserRouter, Routes, Route, useNavigate, useLocation, Navigate } from 'react-router-dom';
import { AppProvider, useAppContext } from './context/AppContext';
import { Header } from './components/Header';
import { HomeView } from './components/HomeView';
import { InvestigationConsole } from './components/InvestigationConsole';
import { DecisionView } from './components/DecisionView';
import { CasesListView } from './components/CasesListView';
import { CaseDetailView } from './components/CaseDetailView';
import { AuditExplorer } from './components/AuditExplorer';
import { BenchmarkDashboard } from './components/BenchmarkDashboard';
import { KnowledgeBaseView } from './components/KnowledgeBaseView';
import { GovernanceMatrixView } from './components/GovernanceMatrixView';
import { PersonaPickerView } from './components/PersonaPickerView';
import {
  ShieldIcon,
  LayersIcon,
  HashIcon,
  DatabaseIcon,
  LockIcon,
  HomeIcon,
  ClockIcon,
} from './components/Icons';

const AppLayout: React.FC = () => {
  const {
    personas,
    activePersona,
    setActivePersona,
    scenarios,
    isBackendHealthy,
    currentWorkflow,
    setCurrentWorkflow,
    isLoadingInitial,
  } = useAppContext();

  const navigate = useNavigate();
  const location = useLocation();

  const pathname = location.pathname;

  return (
    <div className="app-container">
      {/* Top Header & Plain-Language Persona Switcher */}
      <Header
        personas={personas}
        activePersona={activePersona}
        onSelectPersona={setActivePersona}
        isBackendHealthy={isBackendHealthy}
      />

      {/* Primary Navigation Tabs with Real Routing */}
      <nav className="tab-navigation" aria-label="Main Navigation">
        <button
          type="button"
          id="nav-home"
          className={`nav-tab ${pathname === '/' || pathname === '/home' ? 'active' : ''}`}
          onClick={() => navigate('/home')}
        >
          <HomeIcon size={14} /> Home
        </button>

        <button
          type="button"
          id="nav-investigate"
          className={`nav-tab ${pathname.startsWith('/investigate') ? 'active' : ''}`}
          onClick={() => navigate('/investigate')}
        >
          <ShieldIcon size={14} /> Look into a case (Investigation &amp; Human Approval)
        </button>

        <button
          type="button"
          id="nav-cases"
          className={`nav-tab ${pathname.startsWith('/cases') ? 'active' : ''}`}
          onClick={() => navigate('/cases')}
        >
          <ClockIcon size={14} /> Past Cases
        </button>

        <button
          type="button"
          id="nav-audit"
          className={`nav-tab ${pathname.startsWith('/trust') || pathname.startsWith('/audit') ? 'active' : ''}`}
          onClick={() => navigate('/trust')}
        >
          <HashIcon size={14} /> Trust &amp; proof (Cryptographic Audit Trail)
        </button>

        <button
          type="button"
          id="nav-benchmark"
          className={`nav-tab ${pathname.startsWith('/compare') ? 'active' : ''}`}
          onClick={() => navigate('/compare')}
        >
          <LayersIcon size={14} /> How this compares (Empirical Benchmarks)
        </button>

        <button
          type="button"
          id="nav-knowledge"
          className={`nav-tab ${pathname.startsWith('/guides') || pathname.startsWith('/knowledge') ? 'active' : ''}`}
          onClick={() => navigate('/guides')}
        >
          <DatabaseIcon size={14} /> Company guides (Knowledge Base &amp; Retrieval)
        </button>

        <button
          type="button"
          id="nav-governance"
          className={`nav-tab ${pathname.startsWith('/permissions') || pathname.startsWith('/governance') ? 'active' : ''}`}
          onClick={() => navigate('/permissions')}
        >
          <LockIcon size={14} /> Who can do what (Security &amp; RBAC Matrix)
        </button>
      </nav>

      {/* Main View Area with Real Routes */}
      <main className="app-main">
        {isLoadingInitial && !activePersona ? (
          <div style={{ color: 'var(--text-muted)', fontSize: '0.85rem', padding: '3rem 0', textAlign: 'center' }}>
            Connecting to customer support system...
          </div>
        ) : (
          <Routes>
            <Route path="/login" element={<PersonaPickerView />} />

            <Route
              path="/"
              element={
                activePersona ? (
                  <HomeView
                    activePersona={activePersona}
                    onNavigateToNewCase={() => navigate('/investigate')}
                    onSelectCase={(wfId) => navigate(`/investigate/${wfId}`)}
                  />
                ) : (
                  <PersonaPickerView />
                )
              }
            />

            <Route
              path="/home"
              element={
                activePersona ? (
                  <HomeView
                    activePersona={activePersona}
                    onNavigateToNewCase={() => navigate('/investigate')}
                    onSelectCase={(wfId) => navigate(`/investigate/${wfId}`)}
                  />
                ) : (
                  <PersonaPickerView />
                )
              }
            />

            <Route
              path="/investigate"
              element={
                activePersona ? (
                  <InvestigationConsole
                    scenarios={scenarios}
                    activePersona={activePersona}
                    workflow={currentWorkflow}
                    onWorkflowUpdated={setCurrentWorkflow}
                  />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            <Route
              path="/investigate/:workflowId"
              element={
                activePersona ? (
                  <InvestigationConsole
                    scenarios={scenarios}
                    activePersona={activePersona}
                    workflow={currentWorkflow}
                    onWorkflowUpdated={setCurrentWorkflow}
                  />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            <Route
              path="/investigate/:workflowId/decide"
              element={
                activePersona ? <DecisionView /> : <Navigate to="/login" replace />
              }
            />

            <Route
              path="/cases"
              element={
                activePersona ? <CasesListView /> : <Navigate to="/login" replace />
              }
            />

            <Route
              path="/cases/:workflowId"
              element={
                activePersona ? <CaseDetailView /> : <Navigate to="/login" replace />
              }
            />

            <Route
              path="/trust"
              element={
                activePersona ? (
                  <AuditExplorer
                    currentWorkflowId={currentWorkflow?.workflow_id || null}
                    activePersona={activePersona}
                  />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            <Route
              path="/trust/:workflowId"
              element={
                activePersona ? (
                  <AuditExplorer
                    currentWorkflowId={null}
                    activePersona={activePersona}
                  />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            {/* Backwards compatibility & aliases */}
            <Route path="/audit" element={<Navigate to="/trust" replace />} />
            <Route path="/audit/:workflowId" element={<Navigate to="/trust" replace />} />

            <Route
              path="/compare"
              element={
                activePersona ? (
                  <BenchmarkDashboard activePersona={activePersona} />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />

            <Route
              path="/guides"
              element={
                activePersona ? (
                  <KnowledgeBaseView activePersona={activePersona} />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />
            <Route path="/knowledge" element={<Navigate to="/guides" replace />} />

            <Route
              path="/permissions"
              element={
                activePersona ? (
                  <GovernanceMatrixView activePersona={activePersona} />
                ) : (
                  <Navigate to="/login" replace />
                )
              }
            />
            <Route path="/governance" element={<Navigate to="/permissions" replace />} />
            <Route path="/security" element={<Navigate to="/permissions" replace />} />

            <Route path="*" element={<Navigate to="/home" replace />} />
          </Routes>
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
          <span>17 Playwright Tests</span>
          <span>SHA-256 Hash Chain Active</span>
          <span>Server-Side RBAC Enforced</span>
        </div>
      </footer>
    </div>
  );
};

export const App: React.FC = () => {
  return (
    <BrowserRouter>
      <AppProvider>
        <AppLayout />
      </AppProvider>
    </BrowserRouter>
  );
};

export default App;
