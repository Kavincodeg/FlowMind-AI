import React, { createContext, useContext, useEffect, useState } from 'react';
import type { DemonstrationScenario, Persona, WorkflowInstance } from '../types';
import { api } from '../api';

interface AppContextType {
  personas: Persona[];
  activePersona: Persona | null;
  setActivePersona: (persona: Persona) => void;
  scenarios: DemonstrationScenario[];
  isBackendHealthy: boolean;
  isDatabaseUp: boolean;
  isDemoMode: boolean;
  currentWorkflow: WorkflowInstance | null;
  setCurrentWorkflow: (workflow: WorkflowInstance | null) => void;
  isLoadingInitial: boolean;
}

const AppContext = createContext<AppContextType | undefined>(undefined);

const STORAGE_KEY_PERSONA_ID = 'flowmind_active_persona_id';

export const AppProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [activePersona, setActivePersonaState] = useState<Persona | null>(null);
  const [scenarios, setScenarios] = useState<DemonstrationScenario[]>([]);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [isDatabaseUp, setIsDatabaseUp] = useState<boolean>(true);
  const [isDemoMode, setIsDemoMode] = useState<boolean>(false);
  const [currentWorkflow, setCurrentWorkflow] = useState<WorkflowInstance | null>(null);
  const [isLoadingInitial, setIsLoadingInitial] = useState<boolean>(true);

  // Set active persona and persist to localStorage
  const setActivePersona = (persona: Persona) => {
    setActivePersonaState(persona);
    try {
      localStorage.setItem(STORAGE_KEY_PERSONA_ID, persona.user_id);
    } catch (e) {
      console.warn('Could not save persona to localStorage:', e);
    }
  };

  useEffect(() => {
    let isMounted = true;

    const init = async () => {
      try {
        const [healthRes, personasRes, scenariosRes] = await Promise.all([
          api.checkHealth().catch(() => ({ status: 'error', service: 'FlowMind AI', version: '1.0.0', database: 'down' as const, demo_mode: false })),
          api.getPersonas().catch(() => []),
          api.getScenarios().catch(() => []),
        ]);

        if (!isMounted) return;

        setIsBackendHealthy(healthRes.status === 'ok');
        setIsDatabaseUp(healthRes.database === 'up');
        setIsDemoMode(Boolean(healthRes.demo_mode));
        setPersonas(personasRes);
        setScenarios(scenariosRes);

        // Restore persona from localStorage if available
        let savedPersonaId: string | null = null;
        try {
          savedPersonaId = localStorage.getItem(STORAGE_KEY_PERSONA_ID);
        } catch (e) {
          console.warn('Could not read persona from localStorage:', e);
        }

        if (personasRes.length > 0) {
          let chosen: Persona | undefined;
          if (savedPersonaId) {
            chosen = personasRes.find((p) => p.user_id === savedPersonaId);
          }
          // Default fallback: Marcus Vance (Team Lead, USR-002)
          if (!chosen) {
            chosen = personasRes.find((p) => p.role === 'team_lead') || personasRes[0];
          }
          setActivePersonaState(chosen);
        }
      } catch (err) {
        console.error('Initialization failed:', err);
        if (isMounted) setIsBackendHealthy(false);
      } finally {
        if (isMounted) setIsLoadingInitial(false);
      }
    };

    init();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <AppContext.Provider
      value={{
        personas,
        activePersona,
        setActivePersona,
        scenarios,
        isBackendHealthy,
        isDatabaseUp,
        isDemoMode,
        currentWorkflow,
        setCurrentWorkflow,
        isLoadingInitial,
      }}
    >
      {children}
    </AppContext.Provider>
  );
};

export const useAppContext = (): AppContextType => {
  const context = useContext(AppContext);
  if (!context) {
    throw new Error('useAppContext must be used within an AppProvider');
  }
  return context;
};
