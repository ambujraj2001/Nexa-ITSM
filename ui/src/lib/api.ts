/**
 * The Nexa API client — the only place the UI performs HTTP requests.
 * Attaches the Supabase session token, retries once after refreshing an
 * expired session, and normalises errors into ApiError.
 */
import { config } from "./config";
import { supabase } from "./supabase";
import type {
  ActivityItem,
  AiSettings,
  AiSettingsUpdate,
  Analysis,
  AnyTicketView,
  ArticleDetail,
  ArticleSummary,
  ArticleWrite,
  AssetRow,
  AssignmentRule,
  AssignmentRuleWrite,
  Attachment,
  AuditEvent,
  Comment,
  ConfirmProposalResponse,
  Conversation,
  CopilotReply,
  EmployeeDashboard,
  EngineerDashboard,
  Health,
  Integration,
  KnowledgeSource,
  Me,
  NotificationItem,
  Priority,
  Progress,
  Related,
  ResolutionDraft,
  RoutingPreview,
  SearchResults,
  SendMessageResponse,
  ServiceRow,
  SlaPolicy,
  Step,
  StepStatus,
  Team,
  TicketDetail,
  TicketList,
  TicketStatus,
  TicketType,
  UserRow,
} from "./types";

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details: Record<string, unknown> = {},
    public requestId: string | null = null,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type TokenProvider = () => Promise<string | null>;

let tokenProvider: TokenProvider = async () => {
  if (!supabase) return null;
  const { data } = await supabase.auth.getSession();
  return data.session?.access_token ?? null;
};

let refreshProvider: () => Promise<string | null> = async () => {
  if (!supabase) return null;
  const { data } = await supabase.auth.refreshSession();
  return data.session?.access_token ?? null;
};

/** Test seam: swap how the client obtains access tokens. */
export function setTokenProviders(get: TokenProvider, refresh?: TokenProvider): void {
  tokenProvider = get;
  refreshProvider = refresh ?? get;
}

type Query = Record<string, string | number | boolean | string[] | null | undefined>;

interface RequestOptions {
  body?: unknown;
  query?: Query;
  form?: FormData;
  auth?: boolean;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: Query): string {
  const url = new URL(path, config.apiBaseUrl + "/");
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value === undefined || value === null || value === "") continue;
    if (Array.isArray(value)) value.forEach((v) => url.searchParams.append(key, v));
    else url.searchParams.set(key, String(value));
  }
  return url.toString();
}

async function send<T>(method: string, path: string, options: RequestOptions = {}, retried = false): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (options.auth !== false) {
    const token = await tokenProvider();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  let body: BodyInit | undefined;
  if (options.form) body = options.form;
  else if (options.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(options.body);
  }

  let response: Response;
  try {
    response = await fetch(buildUrl(path, options.query), { method, headers, body, signal: options.signal });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError(0, "network_error", "Can't reach Nexa right now. Check your connection and try again.");
  }

  if (response.status === 401 && options.auth !== false && !retried) {
    const refreshed = await refreshProvider().catch(() => null);
    if (refreshed) return send<T>(method, path, options, true);
  }

  const requestId = response.headers.get("x-request-id");
  if (!response.ok) {
    let code = "http_error";
    let message = `Request failed (${response.status}).`;
    let details: Record<string, unknown> = {};
    try {
      const data = (await response.json()) as { error?: { code?: string; message?: string; details?: Record<string, unknown> } };
      code = data.error?.code ?? code;
      message = data.error?.message ?? message;
      details = data.error?.details ?? {};
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(response.status, code, message, details, requestId);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

const get = <T>(path: string, query?: Query, opts?: Partial<RequestOptions>) => send<T>("GET", path, { query, ...opts });
const post = <T>(path: string, body?: unknown) => send<T>("POST", path, { body });
const patch = <T>(path: string, body: unknown) => send<T>("PATCH", path, { body });
const put = <T>(path: string, body: unknown) => send<T>("PUT", path, { body });
const del = <T>(path: string) => send<T>("DELETE", path);
const upload = <T>(path: string, file: File) => {
  const form = new FormData();
  form.append("file", file);
  return send<T>("POST", path, { form });
};

export interface TicketListQuery {
  scope?: "visible" | "assigned" | "team" | "requested";
  ticket_type?: TicketType;
  status?: TicketStatus[];
  priority?: Priority;
  open_only?: boolean;
  q?: string;
  sort?: "updated" | "sla" | "priority" | "created";
  limit?: number;
  offset?: number;
}

const t = (ref: string) => `/api/tickets/${encodeURIComponent(ref)}`;

export const api = {
  health: () => get<Health>("/health", undefined, { auth: false }),

  me: {
    get: () => get<Me>("/api/me"),
    update: (body: Partial<Pick<Me, "name" | "job_title" | "department" | "location">>) => patch<Me>("/api/me", body),
  },

  conversations: {
    current: () => get<Conversation>("/api/conversations/current"),
    create: () => post<Conversation>("/api/conversations"),
    get: (id: string) => get<Conversation>(`/api/conversations/${id}`),
    send: (id: string, content: string) => post<SendMessageResponse>(`/api/conversations/${id}/messages`, { content }),
    confirm: (id: string, messageId: string) => post<ConfirmProposalResponse>(`/api/conversations/${id}/proposals/${messageId}/confirm`),
    dismiss: (id: string, messageId: string) => post<SendMessageResponse>(`/api/conversations/${id}/proposals/${messageId}/dismiss`),
    upload: (id: string, file: File) => upload<{ id: string; file_name: string; size_bytes: number }>(`/api/conversations/${id}/attachments`, file),
  },

  tickets: {
    list: (query: TicketListQuery = {}) => get<TicketList>("/api/tickets", query as Query),
    get: (ref: string) => get<AnyTicketView>(t(ref)),
    create: (body: { description: string; title?: string; ticket_type?: TicketType }) => post<AnyTicketView>("/api/tickets", body),
    update: (ref: string, body: Partial<{ priority: Priority; status: TicketStatus; title: string; category: string; subcategory: string }>) =>
      patch<AnyTicketView>(t(ref), body),
    progress: (ref: string) => get<Progress>(`${t(ref)}/progress`),
    analysis: (ref: string) => get<Analysis | null>(`${t(ref)}/analysis`),
    investigate: (ref: string) => post<Progress>(`${t(ref)}/investigate`),
    assignToMe: (ref: string) => post<TicketDetail>(`${t(ref)}/assign-to-me`),
    reassign: (ref: string, body: { assignee_id?: string; team_id?: string; note?: string }) => post<TicketDetail>(`${t(ref)}/reassign`, body),
    escalate: (ref: string, body: { reason: string; note?: string; target_team_id?: string }) => post<TicketDetail>(`${t(ref)}/escalate`, body),
    resolve: (ref: string, body: { resolution_summary: string; resolution_code?: string }) => post<AnyTicketView>(`${t(ref)}/resolve`, body),
    reopen: (ref: string, reason: string) => post<AnyTicketView>(`${t(ref)}/reopen`, { reason }),
    close: (ref: string) => post<AnyTicketView>(`${t(ref)}/close`),
    resolutionDraft: (ref: string) => post<ResolutionDraft>(`${t(ref)}/resolution-draft`),
    steps: {
      list: (ref: string) => get<Step[]>(`${t(ref)}/steps`),
      add: (ref: string, body: { description: string; details?: string; technical_details?: string; position?: number }) => post<Step[]>(`${t(ref)}/steps`, body),
      update: (ref: string, stepId: string, body: Partial<{ description: string; details: string | null; technical_details: string | null; status: StepStatus; notes: string | null }>) =>
        patch<Step[]>(`${t(ref)}/steps/${stepId}`, body),
      remove: (ref: string, stepId: string) => del<Step[]>(`${t(ref)}/steps/${stepId}`),
      reorder: (ref: string, stepIds: string[]) => post<Step[]>(`${t(ref)}/steps/reorder`, { step_ids: stepIds }),
      restore: (ref: string) => post<Step[]>(`${t(ref)}/steps/restore`),
    },
    comments: {
      list: (ref: string) => get<Comment[]>(`${t(ref)}/comments`),
      add: (ref: string, body: { content: string; visibility?: "internal" | "requester"; request_info?: boolean }) => post<Comment[]>(`${t(ref)}/comments`, body),
    },
    activity: (ref: string) => get<ActivityItem[]>(`${t(ref)}/activity`),
    related: (ref: string) => get<Related>(`${t(ref)}/related`),
    attachments: {
      list: (ref: string) => get<Attachment[]>(`${t(ref)}/attachments`),
      upload: (ref: string, file: File) => upload<Attachment>(`${t(ref)}/attachments`, file),
    },
    copilot: {
      history: (ref: string) => get<{ role: "user" | "assistant"; content: string }[]>(`${t(ref)}/copilot`),
      ask: (ref: string, message: string) => post<CopilotReply>(`${t(ref)}/copilot`, { message }),
    },
  },

  dashboard: {
    engineer: () => get<EngineerDashboard>("/api/dashboard/engineer"),
    employee: () => get<EmployeeDashboard>("/api/dashboard/employee"),
  },

  engineers: (teamId?: string) => get<UserRow[]>("/api/engineers", { team_id: teamId }),

  settings: {
    ai: () => get<AiSettings>("/api/settings/ai"),
    updateAi: (body: AiSettingsUpdate) => patch<AiSettings>("/api/settings/ai", body),
    slaPolicies: () => get<SlaPolicy[]>("/api/settings/sla-policies"),
    updateSla: (id: string, body: Partial<Pick<SlaPolicy, "name" | "response_time_minutes" | "resolution_time_minutes" | "enabled">>) =>
      patch<SlaPolicy>(`/api/settings/sla-policies/${id}`, body),
    updateKnowledgeSource: (id: string, enabled: boolean) => patch<KnowledgeSource[]>(`/api/settings/knowledge-sources/${id}`, { enabled }),
    reindex: () => post<{ articles: number; incidents: number }>("/api/settings/knowledge-sources/reindex"),
    updateIntegration: (id: string, body: { enabled?: boolean; config?: Record<string, unknown> }) => patch<Integration>(`/api/settings/integrations/${id}`, body),
  },

  rules: {
    list: () => get<AssignmentRule[]>("/api/assignment-rules"),
    create: (body: AssignmentRuleWrite) => post<AssignmentRule>("/api/assignment-rules", body),
    update: (id: string, body: AssignmentRuleWrite) => put<AssignmentRule>(`/api/assignment-rules/${id}`, body),
    remove: (id: string) => del<{ ok: boolean }>(`/api/assignment-rules/${id}`),
    preview: (body: { category?: string; subcategory?: string; priority?: Priority; ticket_type?: TicketType }) => post<RoutingPreview>("/api/assignment-rules/preview", body),
  },

  admin: {
    users: (query: { role?: string; team_id?: string; q?: string } = {}) => get<UserRow[]>("/api/admin/users", query),
    updateUser: (id: string, body: Record<string, unknown>) => patch<UserRow>(`/api/admin/users/${id}`, body),
    invite: (body: { email: string; name: string; role: string; engineer_level?: string | null; team_id?: string | null }) => post<UserRow>("/api/admin/users/invite", body),
    teams: () => get<Team[]>("/api/admin/teams"),
    createTeam: (body: { name: string; description?: string | null; is_service_desk: boolean }) => post<Team>("/api/admin/teams", body),
    updateTeam: (id: string, body: { name: string; description?: string | null; is_service_desk: boolean }) => put<Team>(`/api/admin/teams/${id}`, body),
    audit: (query: { entity_type?: string; actor_type?: string; action?: string; before?: string; limit?: number } = {}) => get<AuditEvent[]>("/api/admin/audit", query),
  },

  knowledge: {
    list: (query: { q?: string; category?: string; status?: string } = {}) => get<ArticleSummary[]>("/api/knowledge", query),
    get: (ref: string) => get<ArticleDetail>(`/api/knowledge/${encodeURIComponent(ref)}`),
    create: (body: ArticleWrite) => post<ArticleDetail>("/api/knowledge", body),
    update: (id: string, body: Partial<ArticleWrite>) => patch<ArticleDetail>(`/api/knowledge/${id}`, body),
  },

  catalog: {
    services: () => get<ServiceRow[]>("/api/services"),
    assets: (query: { service_id?: string; mine?: boolean } = {}) => get<AssetRow[]>("/api/assets", query),
  },

  search: (q: string) => get<SearchResults>("/api/search", { q }),

  notifications: {
    list: () => get<{ items: NotificationItem[]; unread: number }>("/api/notifications"),
    seen: () => post<{ ok: boolean }>("/api/notifications/seen"),
  },
};

export function errorMessage(error: unknown, fallback = "Something went wrong."): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}
