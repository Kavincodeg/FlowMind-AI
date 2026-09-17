/**
 * FlowMind AI - Frontend Data Types (Phase 5)
 * Strict typing aligned with FastAPI Pydantic schemas.
 */

export type UserRole = 'support_agent' | 'team_lead' | 'manager' | 'admin';

export interface Persona {
  user_id: string;
  name: string;
  role: UserRole;
  department: string;
  token: string;
}

export interface DemonstrationScenario {
  id: string;
  title: string;
  category: string;
  badge: string;
  customer_id: string;
  customer_name: string;
  issue_summary: string;
  expected_action: string;
  required_role: string;
}

export interface Citation {
  source: string;
  chunk_id: string;
  score: number;
  text: string;
  metadata?: Record<string, unknown>;
}

export interface Recommendation {
  action_type: string;
  target_team: string;
  priority: string;
  parameters: Record<string, unknown>;
  justification: string;
}

export interface ReasoningOutput {
  status: string;
  abstention_reason: string | null;
  root_cause: string | null;
  rationale: string | null;
  confidence_score: number | null;
  requires_human_approval: boolean | null;
  indirect_injection_detected: boolean | null;
  recommendation: Recommendation | null;
  citations: Citation[];
  retrieval_summary: Record<string, unknown>;
}

export interface ApprovalRecord {
  approver_id: string;
  approver_name?: string;
  approver_role: string;
  decision: 'APPROVE' | 'REJECT' | 'MODIFY';
  notes?: string;
  rejection_reason?: string;
  comments?: string;
  submitted_at?: string;
  timestamp?: string;
  authorized?: boolean;
}

export interface ExecutionRecord {
  dispatched_to: string;
  action_type: string;
  target_id: string;
  parameters: Record<string, unknown>;
  status: string;
  timestamp: string;
  response_payload: Record<string, unknown>;
}

export interface WorkflowInstance {
  workflow_id: string;
  status: 'PENDING_REASONING' | 'PENDING_APPROVAL' | 'APPROVED_EXECUTED' | 'REJECTED' | 'ABSTAINED' | 'FAILED';
  started_at: string;
  completed_at: string | null;
  request: {
    customer_id: string;
    customer_name: string;
    issue_summary: string;
  };
  reasoning: ReasoningOutput | null;
  approval_record: ApprovalRecord | null;
  execution_record: ExecutionRecord | null;
  error_message: string | null;
}

export interface AuditEvent {
  event_id: string;
  stage: string;
  timestamp: string;
  actor: string;
  details: Record<string, unknown>;
  block_hash: string;
  parent_hash: string;
}

export interface AuditTrail {
  audit_id: string;
  workflow_id: string;
  terminal_state: string;
  is_complete: boolean;
  started_at: string;
  completed_at: string | null;
  duration_ms: number;
  // chain_events: real SHA-256 hash chain events from the backend.
  // chain_verified is no longer stored here; it comes from the /audit/verify endpoint.
  chain_events?: AuditEvent[];
}


export interface ChainVerificationResult {
  workflow_id: string;
  chain_length: number;
  valid: boolean;
  failed_at_index: number | null;
  failed_event_id: string | null;
}
export interface AuditListItem {
  audit_id: string;
  workflow_id: string;
  terminal_state: string;
  is_complete: boolean;
  started_at: string;
  completed_at: string | null;
  duration_ms: number;
}

export interface BenchmarkSummary {
  total_cases: number;
  flowmind_task_success_rate: number;
  baseline_task_success_rate: number;
  flowmind_action_accuracy: number;
  baseline_action_accuracy: number;
  flowmind_citation_integrity_rate: number;
  baseline_citation_integrity_rate: number;
  flowmind_injection_defense_rate: number;
  flowmind_approval_compliance_rate: number;
  baseline_injection_defense_rate: number;
  baseline_approval_compliance_rate: number;
  flowmind_mean_latency_ms: number;
  flowmind_audit_completeness_rate: number;
  baseline_mean_latency_ms: number;
  baseline_audit_completeness_rate: number;
  real_provider_latency_sample?: {
    model: string;
    reference_network_latency_ms: number;
    reference_investigation_pipeline_ms: number;
    tested_live: boolean;
    note: string;
  };
}

export interface BenchmarkResultResponse {
  timestamp: string;
  dataset_size: number;
  llm_provider: string;
  retrieval_metrics: RetrievalMetrics;
  comparative_summary: BenchmarkSummary;
  real_provider_latency_sample?: {
    model: string;
    reference_network_latency_ms: number;
    reference_investigation_pipeline_ms: number;
    tested_live: boolean;
    note: string;
  };
}

export interface RetrievalMetrics {
  precision_at_k: number;
  recall_at_k: number;
  mrr: number;
  queries_evaluated: number;
}

export interface PolicyDocument {
  filename: string;
  title: string;
  content: string;
  size_bytes: number;
}

export interface TicketItem {
  ticket_id: string;
  customer_id: string;
  customer_name: string;
  issue_category: string;
  issue_description: string;
  priority: string;
  status: string;
  sla_breach: boolean;
  assigned_team?: string;
  sla_deadline?: string;
}

export interface KnowledgeSearchChunk {
  chunk_id: string;
  source_type: string;
  source_id: string;
  chunk_index: number;
  content: string;
  similarity_score: number;
  citation: string;
  metadata?: Record<string, unknown>;
}

export interface KnowledgeSearchResult {
  query: string;
  latency_ms: number;
  total_retrieved: number;
  chunks: KnowledgeSearchChunk[];
}

export interface ActionPermission {
  action_type: string;
  label: string;
  tier: string;
  sensitive: boolean;
  description: string;
  authorized_roles: string[];
  requires_approval: boolean;
}

export interface SecurityMatrixResponse {
  roles: string[];
  actions: ActionPermission[];
  governance_rules: {
    rejection_rationale_mandatory: boolean;
    parameter_modification_enforced: boolean;
    server_token_resolution: boolean;
    hash_chain_immutability: boolean;
  };
}

export interface UserMeResponse {
  user_id: string;
  name: string;
  role: string;
  department: string;
}

