/**
 * FlowMind AI - Typed API Client (Phase 5)
 * Handles token-based session auth and structured error extraction (including RBAC 403s).
 */

import type {
  AuditListItem,
  AuditTrail,
  BenchmarkResultResponse,
  ChainVerificationResult,
  DemonstrationScenario,
  KnowledgeSearchResult,
  Persona,
  PolicyDocument,
  RetrievalMetrics,
  SecurityMatrixResponse,
  TicketItem,
  WorkflowInstance,
} from './types';

export class ApiError extends Error {
  status: number;
  data: unknown;

  constructor(status: number, message: string, data?: unknown) {
    super(message);
    this.status = status;
    this.data = data;
    this.name = 'ApiError';
  }
}

export interface RbacErrorData {
  error: string;
  message: string;
  user_role: string;
  action_type: string;
}

async function request<T>(endpoint: string, options: RequestInit = {}, token?: string): Promise<T> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(endpoint, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errBody: unknown;
    try {
      errBody = await response.json();
    } catch {
      errBody = await response.text();
    }

    let message = `API request failed with status ${response.status}`;
    if (typeof errBody === 'object' && errBody !== null && 'detail' in errBody) {
      const detail = (errBody as { detail: unknown }).detail;
      if (typeof detail === 'string') {
        message = detail;
      } else if (typeof detail === 'object' && detail !== null && 'message' in detail) {
        message = String((detail as { message: unknown }).message);
      }
    }

    throw new ApiError(response.status, message, errBody);
  }

  return response.json() as Promise<T>;
}

export const api = {
  checkHealth: async (): Promise<{ status: string; service: string; version: string }> => {
    return request('/health');
  },

  getPersonas: async (): Promise<Persona[]> => {
    return request('/api/users/personas');
  },

  getMe: async (token: string): Promise<Persona> => {
    return request('/api/users/me', { method: 'GET' }, token);
  },

  getScenarios: async (): Promise<DemonstrationScenario[]> => {
    return request('/api/scenarios');
  },

  investigateComplaint: async (
    payload: { customer_id: string; customer_name: string; issue_summary: string },
    token: string,
  ): Promise<WorkflowInstance> => {
    return request(
      '/api/workflow/investigate',
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      token,
    );
  },

  getWorkflowDetails: async (workflowId: string, token: string): Promise<WorkflowInstance> => {
    return request(`/api/workflow/${workflowId}`, { method: 'GET' }, token);
  },

  submitDecision: async (
    workflowId: string,
    submission: {
      decision: 'APPROVE' | 'REJECT' | 'MODIFY';
      notes?: string;
      rejection_reason?: string;
      modified_action?: Record<string, unknown>;
      comments?: string;
    },
    token: string,
  ): Promise<WorkflowInstance> => {
    const payload: Record<string, unknown> = {
      decision: submission.decision,
      comments: submission.comments || submission.notes || '',
    };
    if (submission.decision === 'REJECT') {
      payload.rejection_reason = submission.rejection_reason || submission.notes || 'Action rejected by reviewer.';
    } else if (submission.decision === 'MODIFY') {
      payload.modified_action = submission.modified_action;
    }
    return request(
      `/api/workflow/${workflowId}/decision`,
      {
        method: 'POST',
        body: JSON.stringify(payload),
      },
      token,
    );
  },

  getWorkflowAudit: async (workflowId: string, token: string): Promise<AuditTrail> => {
    return request(`/api/workflow/${workflowId}/audit`, { method: 'GET' }, token);
  },

  verifyAuditChain: async (workflowId: string, token: string): Promise<ChainVerificationResult> => {
    return request(`/api/workflow/${workflowId}/audit/verify`, { method: 'GET' }, token);
  },

  listAudits: async (token: string): Promise<AuditListItem[]> => {
    return request('/api/audits', { method: 'GET' }, token);
  },

  getBenchmarkResults: async (token: string): Promise<BenchmarkResultResponse> => {
    return request('/api/evaluation/benchmark', { method: 'GET' }, token);
  },

  getRetrievalMetrics: async (token: string): Promise<RetrievalMetrics> => {
    return request('/api/evaluation/retrieval', { method: 'GET' }, token);
  },

  getPolicies: async (token: string): Promise<PolicyDocument[]> => {
    return request('/api/knowledge/policies', { method: 'GET' }, token);
  },

  getTickets: async (
    category?: string,
    limit: number = 50,
    token?: string
  ): Promise<{ tickets: TicketItem[]; total: number; total_corpus: number; categories: string[] }> => {
    const params = new URLSearchParams();
    if (category) params.append('category', category);
    params.append('limit', String(limit));
    return request(`/api/knowledge/tickets?${params.toString()}`, { method: 'GET' }, token);
  },

  searchKnowledge: async (
    query: string,
    topK: number = 5,
    scoreThreshold: number = 0.0,
    token?: string
  ): Promise<KnowledgeSearchResult> => {
    return request(
      '/api/knowledge/search',
      {
        method: 'POST',
        body: JSON.stringify({ query, top_k: topK, score_threshold: scoreThreshold }),
      },
      token
    );
  },

  getSecurityMatrix: async (token: string): Promise<SecurityMatrixResponse> => {
    return request('/api/security/matrix', { method: 'GET' }, token);
  },
};
