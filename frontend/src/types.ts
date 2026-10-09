/**
 * FlowMind AI - Frontend Data Types (Phase 5)
 * Types aligned with the FastAPI/Pydantic backend schemas.
 *
 * Key mapping corrections (Task 3):
 *   ExecutionRecord: uses executed_at / transaction_id / connector_name
 *     (NOT timestamp / target_id / dispatched_to)
 *   ReasoningOutput recommendation: uses rationale field
 *   WorkflowStatus: matches the backend WorkflowStatus enum exactly
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
  /** Backend field: rationale (not justification) */
  rationale: string;
  escalation_level?: string;
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

/**
 * ExecutionRecord – matches ExecutionResult from backend/connectors/base.py
 *
 * Backend sends: executed_at, transaction_id, connector_name
 * (Previous hand-written type incorrectly used: timestamp, target_id, dispatched_to)
 */
export interface ExecutionRecord {
  workflow_id: string;
  /** Unique transaction identifier for the dispatched action */
  transaction_id: string;
  /** Name of the connector that executed the action */
  connector_name: string;
  action_type: string;
  status: string;
  details: Record<string, unknown>;
  /** ISO-8601 timestamp when the action was executed */
  executed_at: string;
  latency_ms: number;
  is_idempotent_replay: boolean;
}

/**
 * WorkflowStatus – mirrors the backend WorkflowStatus enum exactly.
 * Add safe fallback handling via statusLabel() utility below.
 */
export type WorkflowStatus =
  | 'SUBMITTED'
  | 'INVESTIGATING'
  | 'PENDING_APPROVAL'
  | 'APPROVED'
  | 'MODIFIED'
  | 'REJECTED'
  | 'AUTO_EXECUTED'
  | 'EXECUTING'
  | 'COMPLETED'
  | 'FAILED'
  | 'ABSTAINED';

export interface WorkflowInstance {
  workflow_id: string;
  status: WorkflowStatus;
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
  retrieval_source?: string;
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
  retrieval_source?: string;
  precision_at_3?: number;
  precision_at_5?: number;
  precision_at_k?: number;
  recall_at_5?: number;
  recall_at_k?: number;
  mrr: number;
  mean_latency_ms?: number;
  total_queries?: number;
  queries_evaluated?: number;
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

export interface HealthCheckResponse {
  status: 'ok' | 'degraded';
  service: string;
  version: string;
  database: {
    status: 'up' | 'down';
    error?: string;
  };
}

// ---------------------------------------------------------------------------
// Shared utility functions (Task 3)
// ---------------------------------------------------------------------------

/**
 * statusLabel – maps the backend WorkflowStatus enum value to a plain-language
 * label for display in staff-facing screens.
 *
 * Unknown values return "In progress" as a safe fallback, never the raw code.
 */
export function statusLabel(status: string | null | undefined): string {
  switch (status) {
    case 'SUBMITTED':        return 'Received';
    case 'INVESTIGATING':    return 'Investigating';
    case 'PENDING_APPROVAL': return 'Awaiting review';
    case 'APPROVED':         return 'Approved';
    case 'MODIFIED':         return 'Modified';
    case 'REJECTED':         return 'Turned down';
    case 'AUTO_EXECUTED':    return 'Auto-handled';
    case 'EXECUTING':        return 'Processing';
    case 'COMPLETED':        return 'Sorted and finished';
    case 'FAILED':           return 'Could not complete';
    case 'ABSTAINED':        return 'No action taken';
    default:                 return 'In progress';
  }
}

/**
 * formatDateTime – parse and format an ISO-8601 date string for display.
 *
 * Returns "—" for missing, null, undefined, or invalid input; never "Invalid Date".
 */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleString();
}

/**
 * formatTime – like formatDateTime but shows time only.
 * Returns "—" for invalid input.
 */
export function formatTime(value: string | null | undefined): string {
  if (!value) return '—';
  const d = new Date(value);
  if (isNaN(d.getTime())) return '—';
  return d.toLocaleTimeString();
}

/**
 * getPlainActionLabel – maps raw action type codes (e.g. ISSUE_REFUND_RECOMMENDATION)
 * to human-friendly phrases for support staff. Never exposes raw SCREAMING_SNAKE_CASE.
 */
export function getPlainActionLabel(actionType?: string | null): string {
  if (!actionType) return 'Recommended action';
  const norm = actionType.toUpperCase();
  if (norm.includes('REFUND')) return 'Issue a refund recommendation';
  if (norm.includes('TRANSFER')) return 'Transfer case to a specialist team';
  if (norm.includes('ESCALATE')) return 'Escalate to higher-level review';
  if (norm.includes('REQUEST')) return 'Ask customer for additional details';
  if (norm.includes('RESOLVE')) return 'Send standard helpful resolution';
  return actionType.replace(/_/g, ' ').toLowerCase();
}

export { getPolicyDisplayTitle, POLICY_TITLE_MAP } from './utils/policyTitles';

