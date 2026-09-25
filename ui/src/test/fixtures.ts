import type { Me, Message, Progress, TicketDetail } from "@/lib/types";

export const employeeMe: Me = {
  id: "u-emp", name: "Elena Rostova", email: "elena@example.com", role: "employee", engineer_level: null, team: null,
  job_title: "Product Designer", department: "Product Design", location: "London HQ", avatar_url: null, home_path: "/assistant",
};

export const engineerMe: Me = {
  ...employeeMe, id: "u-eng", name: "Rahul Sharma", email: "rahul@example.com", role: "engineer", engineer_level: "L1",
  team: { id: "t-net", name: "Network" }, job_title: "Network Support Engineer", department: "IT", home_path: "/dispatch",
};

export const adminMe: Me = { ...engineerMe, id: "u-adm", name: "Jordan Blake", role: "admin", engineer_level: null, home_path: "/settings/ai" };

const now = new Date().toISOString();

export function ticketDetail(overrides: Partial<TicketDetail> = {}): TicketDetail {
  return {
    view: "engineer",
    id: "tk-1",
    ticket_number: "INC-10234",
    title: "VPN Connection Failure",
    ticket_type: "incident",
    type_label: "Incident",
    priority: "P2",
    status: "in_progress",
    status_label: "In Progress",
    category: "Network",
    subcategory: "VPN",
    requester: { id: "u-emp", name: "Elena Rostova", department: "Product Design", location: "London HQ" },
    assignee: { id: "u-eng", name: "Rahul Sharma", engineer_level: "L1", team_name: "Network" },
    team: { id: "t-net", name: "Network" },
    support_level: "L1",
    sla: { state: "on_track", label: "2h 15m left", due_at: now, response_due_at: now, remaining_seconds: 8100, policy_name: null },
    ai_status: "completed",
    ai_headline: "VPN authentication certificate may have expired.",
    summary: "VPN fails with a certificate error.",
    steps_done: 1,
    steps_total: 3,
    created_at: now,
    updated_at: now,
    resolved_at: null,
    description: "My VPN stopped working this morning right after updating my Mac. Getting certificate errors.",
    impact: "individual",
    urgency: "critical",
    source: "assistant",
    service: { id: "s-vpn", name: "VPN", criticality: "high" },
    sla_response_due_at: now,
    first_response_at: now,
    ai_error: null,
    ai_stage: "done",
    ai_recommended_team: { id: "t-net", name: "Network" },
    assignment_reason: "rule:VPN issues → Network",
    analysis: {
      category: "Network", subcategory: "VPN", priority: "P2", summary: "VPN fails with a certificate error.",
      diagnosis: "VPN authentication certificate may have expired.", confidence: 0.86, confidence_label: "high", below_threshold: false,
      rationale: "The error matches the certificate-expiry runbook.",
      evidence: [
        { source_type: "knowledge_article", reference: "KB-102", title: "VPN certificate expiration and renewal", summary: "Describes CERT_AUTHORITY_INVALID.", ref_id: "a1" },
        { source_type: "historical_incident", reference: "INC-10111", title: "VPN fails after macOS update", summary: "Resolved by re-pushing the certificate.", ref_id: "t0" },
      ],
      hypotheses: [{ cause: "Cached credentials", likelihood: "low", how_to_verify: "Check the auth log" }],
      signals: [{ label: "Error", value: "CERT_AUTHORITY_INVALID", kind: "error" }],
      missing_information: [], recommended_team: { id: "t-net", name: "Network" }, handoff: null, updated_at: now,
    },
    steps: [
      { id: "st-1", position: 0, description: "Check VPN client status", details: null, technical_details: null, status: "completed", source: "ai", edited: false, notes: null, created_by: null, completed_by: { id: "u-eng", name: "Rahul Sharma" }, completed_at: now, updated_at: now, is_current: false },
      { id: "st-2", position: 1, description: "Renew VPN certificate", details: "Re-push the certificate profile via MDM.", technical_details: "security find-certificate -a -c vpn-client", status: "pending", source: "ai", edited: false, notes: null, created_by: null, completed_by: null, completed_at: null, updated_at: now, is_current: true },
      { id: "st-3", position: 2, description: "Test VPN connection", details: null, technical_details: null, status: "pending", source: "ai", edited: false, notes: null, created_by: null, completed_by: null, completed_at: null, updated_at: now, is_current: false },
    ],
    escalation: null,
    resolution: null,
    permissions: { can_work: true, can_self_assign: false, can_reassign: true, can_escalate: true, can_resolve: true, can_reopen: false, can_close: false, can_comment_internal: true, can_reply: true, can_retry_ai: false },
    escalation_count: 0,
    reopen_count: 0,
    ...overrides,
  };
}

export function message(overrides: Partial<Message>): Message {
  return { id: crypto.randomUUID(), role: "assistant", content: "", message_type: "text", payload: {}, ticket_id: null, created_at: new Date().toISOString(), ...overrides };
}

export const proposalMessage = message({
  id: "m-proposal",
  content: "Sorry your VPN is down. I can create an incident and route it to Network.",
  message_type: "triage_proposal",
  payload: {
    proposal_id: "p1", status: "proposed", ticket_type: "incident", type_label: "Incident", title: "VPN connection failure", summary: null,
    category: "Network", subcategory: "VPN", priority: "P2", priority_label: "High", likely_cause: "VPN authentication certificate may have expired.",
    confidence_label: "medium", team_name: "Network", service_name: "VPN", signals: [], ticket_id: null, ticket_number: null,
  },
});

export const completedProgress: Progress = {
  ticket_id: "tk-1", ticket_number: "INC-10234", status: "assigned", ai_status: "completed", ai_stage: "done",
  stages: [{ key: "understanding", label: "Understanding request", state: "done" }],
  error: null, team: { id: "t-net", name: "Network" }, assignee: { id: "u-eng", name: "Rahul Sharma" },
};
