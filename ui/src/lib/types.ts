/** API contract — mirrors backend/app/schemas. Keep in sync. */

export type Role = "employee" | "engineer" | "admin";
export type Priority = "P1" | "P2" | "P3" | "P4";
export type TicketType = "incident" | "service_request" | "problem" | "change";
export type TicketStatus =
  | "new"
  | "triaging"
  | "assigned"
  | "in_progress"
  | "pending_user"
  | "pending_engineer"
  | "escalated"
  | "resolved"
  | "closed"
  | "reopened";
export type StepStatus = "pending" | "in_progress" | "completed" | "skipped";
export type AiStatus = "pending" | "running" | "completed" | "failed" | "skipped";
export type SlaState = "on_track" | "at_risk" | "due_soon" | "breached" | "met" | "missed" | "none";

export interface PersonRef {
  id: string;
  name: string;
  email?: string | null;
  avatar_url?: string | null;
  job_title?: string | null;
  department?: string | null;
  location?: string | null;
  role?: string | null;
  engineer_level?: string | null;
  team_name?: string | null;
}

export interface TeamRef {
  id: string;
  name: string;
}

export interface ServiceRef {
  id: string;
  name: string;
  criticality: string;
}

export interface SlaInfo {
  state: SlaState;
  label: string;
  due_at: string | null;
  response_due_at: string | null;
  remaining_seconds: number | null;
  policy_name?: string | null;
}

export interface Me {
  id: string;
  name: string;
  email: string;
  role: Role;
  engineer_level: "L1" | "L2" | null;
  team: TeamRef | null;
  job_title: string | null;
  department: string | null;
  location: string | null;
  avatar_url: string | null;
  home_path: string;
}

export interface TicketSummary {
  id: string;
  ticket_number: string;
  title: string;
  ticket_type: TicketType;
  type_label: string;
  priority: Priority;
  status: TicketStatus;
  status_label: string;
  category: string | null;
  subcategory: string | null;
  requester: PersonRef;
  assignee: PersonRef | null;
  team: TeamRef | null;
  support_level: "L1" | "L2";
  sla: SlaInfo;
  ai_status: AiStatus;
  ai_headline: string | null;
  summary: string | null;
  steps_done: number;
  steps_total: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export interface EvidenceItem {
  source_type: "knowledge_article" | "historical_incident" | "user_report" | "asset" | "service";
  reference: string | null;
  title: string | null;
  summary: string;
  ref_id: string | null;
}

export interface Hypothesis {
  cause: string;
  likelihood: "high" | "medium" | "low";
  how_to_verify: string | null;
}

export interface Signal {
  label: string;
  value: string;
  kind: string;
}

export interface Handoff {
  summary: string;
  completed_checks: string[];
  ruled_out: string[];
  open_questions: string[];
  suggested_next: string[];
  generated_at: string | null;
}

export interface Analysis {
  category: string | null;
  subcategory: string | null;
  priority: Priority | null;
  summary: string | null;
  diagnosis: string | null;
  confidence: number | null;
  confidence_label: "high" | "medium" | "low" | null;
  below_threshold: boolean;
  rationale: string | null;
  evidence: EvidenceItem[];
  hypotheses: Hypothesis[];
  signals: Signal[];
  missing_information: string[];
  recommended_team: TeamRef | null;
  handoff: Handoff | null;
  updated_at: string | null;
}

export interface Step {
  id: string;
  position: number;
  description: string;
  details: string | null;
  technical_details: string | null;
  status: StepStatus;
  source: "ai" | "engineer";
  edited: boolean;
  notes: string | null;
  created_by: PersonRef | null;
  completed_by: PersonRef | null;
  completed_at: string | null;
  updated_at: string;
  is_current: boolean;
}

export interface Permissions {
  can_work: boolean;
  can_self_assign: boolean;
  can_reassign: boolean;
  can_escalate: boolean;
  can_resolve: boolean;
  can_reopen: boolean;
  can_close: boolean;
  can_comment_internal: boolean;
  can_reply: boolean;
  can_retry_ai: boolean;
}

export interface EscalationInfo {
  escalated_at: string;
  from_person: PersonRef | null;
  to_team: TeamRef | null;
  reason: string;
  reason_label: string;
  note: string | null;
}

export interface Resolution {
  summary: string | null;
  employee_summary: string | null;
  code: string | null;
  resolved_by: PersonRef | null;
  resolved_at: string | null;
  completed_steps: string[];
}

export interface TicketDetail extends TicketSummary {
  view: "engineer";
  description: string;
  impact: string | null;
  urgency: string | null;
  source: string;
  service: ServiceRef | null;
  sla_response_due_at: string | null;
  first_response_at: string | null;
  ai_error: string | null;
  ai_stage: string | null;
  ai_recommended_team: TeamRef | null;
  assignment_reason: string | null;
  analysis: Analysis | null;
  steps: Step[];
  escalation: EscalationInfo | null;
  resolution: Resolution | null;
  permissions: Permissions;
  escalation_count: number;
  reopen_count: number;
}

export interface EmployeeStep {
  id: string;
  position: number;
  description: string;
  status: StepStatus;
  completed_at: string | null;
}

export interface EmployeeTicketDetail {
  view: "employee";
  id: string;
  ticket_number: string;
  title: string;
  description: string;
  ticket_type: TicketType;
  type_label: string;
  priority: Priority;
  status: TicketStatus;
  status_label: string;
  category: string | null;
  subcategory: string | null;
  likely_cause: string | null;
  summary: string | null;
  assignee: PersonRef | null;
  team: TeamRef | null;
  ai_status: AiStatus;
  waiting_on: "you" | "it_team" | null;
  steps: EmployeeStep[];
  steps_done: number;
  steps_total: number;
  resolution: Resolution | null;
  permissions: Permissions;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

export type AnyTicketView = TicketDetail | EmployeeTicketDetail;

export interface TicketList {
  items: TicketSummary[];
  total: number;
  limit: number;
  offset: number;
}

export interface Comment {
  id: string;
  author: PersonRef | null;
  author_type: "user" | "ai" | "system";
  author_label: string;
  content: string;
  visibility: "internal" | "requester";
  kind: string;
  created_at: string;
}

export interface ActivityItem {
  id: string;
  at: string;
  actor_type: "user" | "ai" | "system";
  actor_label: string;
  action: string;
  summary: string;
  detail: string | null;
}

export interface ProgressStage {
  key: string;
  label: string;
  state: "done" | "active" | "pending" | "failed" | "skipped";
}

export interface Progress {
  ticket_id: string;
  ticket_number: string;
  status: TicketStatus;
  ai_status: AiStatus;
  ai_stage: string | null;
  stages: ProgressStage[];
  error: string | null;
  team: TeamRef | null;
  assignee: PersonRef | null;
}

export interface RelatedIncident {
  ticket_id: string;
  ticket_number: string;
  title: string;
  resolution_summary: string | null;
  resolved_in: string | null;
  similarity: number | null;
}

export interface RelatedArticle {
  article_id: string;
  article_number: string;
  title: string;
  excerpt: string | null;
  updated_at: string;
  similarity: number | null;
}

export interface Related {
  similar_incidents: RelatedIncident[];
  knowledge: RelatedArticle[];
}

export interface Attachment {
  id: string;
  file_name: string;
  content_type: string | null;
  size_bytes: number | null;
  uploaded_by: PersonRef | null;
  created_at: string;
  url: string | null;
}

export interface CopilotReply {
  answer: string;
  references: string[];
  draft_message: string | null;
  model: string | null;
}

export interface ResolutionDraft {
  resolution_summary: string;
  employee_summary: string;
  generated: boolean;
}

// ── conversations ──────────────────────────────────────────────────────────

export type MessageType =
  | "text"
  | "triage_proposal"
  | "ticket_created"
  | "ticket_status"
  | "knowledge_answer"
  | "clarification"
  | "error";

export interface ProposalPayload {
  proposal_id: string;
  status: "proposed" | "created" | "dismissed" | "superseded";
  ticket_type: TicketType;
  type_label: string;
  title: string;
  summary: string | null;
  category: string | null;
  subcategory: string | null;
  priority: Priority;
  priority_label: string;
  likely_cause: string | null;
  confidence_label: "high" | "medium" | "low" | null;
  team_name: string | null;
  service_name: string | null;
  signals: Signal[];
  ticket_id: string | null;
  ticket_number: string | null;
  manual?: boolean;
  suggestions?: string[];
}

export interface StatusCard {
  ticket_id: string;
  ticket_number: string;
  title: string;
  status: TicketStatus;
  status_label: string;
  priority: Priority;
  assignee_name: string | null;
  team_name: string | null;
  waiting_on: "you" | "it_team" | null;
  steps_done: number;
  steps_total: number;
  sla_label: string | null;
  updated_at: string;
}

export interface Message {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  message_type: MessageType;
  payload: Record<string, unknown> & { suggestions?: string[] };
  ticket_id: string | null;
  created_at: string;
}

export interface Conversation {
  id: string;
  title: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  messages: Message[];
}

export interface SendMessageResponse {
  conversation_id: string;
  messages: Message[];
}

export interface ConfirmProposalResponse {
  ticket: TicketSummary;
  messages: Message[];
}

// ── dashboards ─────────────────────────────────────────────────────────────

export interface AttentionItem {
  ticket: TicketSummary;
  reasons: { code: string; label: string }[];
  ai: { kind: "diagnosis" | "needs_info" | "failed" | "running" | "plan_ready" | "disabled" | "none"; label: string; text: string | null };
  action_label: string;
}

export interface EngineerDashboard {
  metrics: { assigned_to_me: number; urgent: number; urgent_at_risk: number; due_soon: number; team_queue: number };
  needs_attention: AttentionItem[];
  my_tickets: TicketSummary[];
  team_queue: TicketSummary[];
  shift_label: string;
  generated_at: string;
}

export interface EmployeeDashboard {
  active: TicketSummary[];
  recent: TicketSummary[];
  waiting_on_you: number;
  open_count: number;
}

// ── settings & admin ───────────────────────────────────────────────────────

export interface KnowledgeSource {
  id: string;
  name: string;
  source_type: string;
  description: string | null;
  enabled: boolean;
  item_count: number;
  indexed_count: number;
  last_indexed_at: string | null;
}

export interface Integration {
  id: string;
  provider: string;
  display_name: string;
  category: string;
  description: string | null;
  enabled: boolean;
  status: "not_configured" | "connected" | "error" | "disabled";
  config: Record<string, unknown>;
  secret_ref: string | null;
  secret_present: boolean;
  available: boolean;
  status_detail: string | null;
  last_checked_at: string | null;
  last_error: string | null;
}

export interface AiSettings {
  ai_triage_enabled: boolean;
  ai_diagnosis_enabled: boolean;
  resolution_plans_enabled: boolean;
  automatic_actions_enabled: boolean;
  human_approval_required: boolean;
  confidence_threshold: number;
  policy: { automatic_actions_locked: boolean; human_approval_locked: boolean; statement: string };
  models: {
    gateway: string;
    configured: boolean;
    fast_model: string | null;
    strong_model: string | null;
    embedding_model: string | null;
    fallback_models: string[];
    routes: Record<string, string | null>;
  };
  knowledge_sources: KnowledgeSource[];
  integrations: Integration[];
  updated_at: string;
  updated_by: PersonRef | null;
  can_edit: boolean;
}

export type AiSettingsUpdate = Partial<
  Pick<AiSettings, "ai_triage_enabled" | "ai_diagnosis_enabled" | "resolution_plans_enabled" | "confidence_threshold">
>;

export interface SlaPolicy {
  id: string;
  name: string;
  priority: Priority;
  response_time_minutes: number;
  resolution_time_minutes: number;
  enabled: boolean;
  updated_at: string;
}

export interface AssignmentRule {
  id: string;
  name: string;
  category: string | null;
  subcategory: string | null;
  priority: Priority | null;
  ticket_type: TicketType | null;
  service: ServiceRef | null;
  team: TeamRef;
  support_level: "L1" | "L2";
  sort_order: number;
  enabled: boolean;
  updated_at: string;
}

export interface AssignmentRuleWrite {
  name: string;
  category?: string | null;
  subcategory?: string | null;
  priority?: Priority | null;
  ticket_type?: TicketType | null;
  service_id?: string | null;
  team_id: string;
  support_level: "L1" | "L2";
  sort_order: number;
  enabled: boolean;
}

export interface RoutingPreview {
  team: TeamRef | null;
  support_level: string;
  reason: string;
  rule_name: string | null;
  engineer: PersonRef | null;
}

export interface UserRow {
  id: string;
  name: string;
  email: string;
  role: Role;
  engineer_level: "L1" | "L2" | null;
  team: TeamRef | null;
  job_title: string | null;
  department: string | null;
  location: string | null;
  is_active: boolean;
  has_login: boolean;
  created_at: string;
}

export interface Team {
  id: string;
  name: string;
  description: string | null;
  is_service_desk: boolean;
  member_count: number;
  l1_count: number;
  l2_count: number;
}

export interface AuditEvent {
  id: string;
  created_at: string;
  actor_type: "user" | "ai" | "system";
  actor_label: string;
  actor_role: string | null;
  action: string;
  summary: string;
  entity_type: string;
  entity_id: string | null;
  ticket_id: string | null;
  ticket_number: string | null;
  old_value: unknown;
  new_value: unknown;
  metadata: Record<string, unknown>;
}

// ── knowledge & catalogue ──────────────────────────────────────────────────

export interface ArticleSummary {
  id: string;
  article_number: string;
  title: string;
  summary: string | null;
  category: string | null;
  subcategory: string | null;
  status: "draft" | "published" | "archived";
  embedding_status: "pending" | "indexed" | "failed" | "skipped";
  service: ServiceRef | null;
  updated_at: string;
}

export interface ArticleDetail extends ArticleSummary {
  content: string;
  created_by: PersonRef | null;
  updated_by: PersonRef | null;
  created_at: string;
}

export interface ArticleWrite {
  title: string;
  summary?: string | null;
  content: string;
  category?: string | null;
  subcategory?: string | null;
  service_id?: string | null;
  status: "draft" | "published" | "archived";
}

export interface ServiceRow {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  criticality: "low" | "medium" | "high" | "critical";
  owner_team: TeamRef | null;
  open_tickets: number;
  asset_count: number;
  updated_at: string;
}

export interface AssetRow {
  id: string;
  name: string;
  asset_type: string;
  owner: PersonRef | null;
  service: ServiceRef | null;
  metadata: Record<string, unknown>;
  updated_at: string;
}

export interface SearchResults {
  tickets: TicketSummary[];
  articles: ArticleSummary[];
}

export interface NotificationItem {
  id: string;
  at: string;
  ticket_id: string | null;
  ticket_number: string | null;
  ticket_title: string | null;
  summary: string;
  unread: boolean;
}

export interface Health {
  status: string;
  version: string;
  environment: string;
  configured: { database: boolean; auth: boolean; ai: boolean; embeddings: boolean; redis: string; telemetry: boolean };
}
