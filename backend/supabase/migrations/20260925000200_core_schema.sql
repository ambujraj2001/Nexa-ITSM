-- Nexa · core relational schema
-- PostgreSQL is the source of truth for all ticket state. Redis only ever holds
-- transient copies (locks, rate limits, short caches).

-- ─── Organisation ───────────────────────────────────────────────────────────

create table public.teams (
  id               uuid primary key default gen_random_uuid(),
  name             text not null,
  description      text,
  -- The intake queue that receives tickets no rule or owner claims.
  is_service_desk  boolean not null default false,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint teams_name_key unique (name)
);
create unique index teams_single_service_desk_idx on public.teams (is_service_desk) where is_service_desk;

create table public.profiles (
  id                     uuid primary key default gen_random_uuid(),
  -- Nullable so non-login requesters (e.g. monitoring bots) can exist.
  auth_user_id           uuid unique references auth.users (id) on delete set null,
  name                   text not null,
  email                  text not null,
  role                   text not null default 'employee' check (role in ('employee', 'engineer', 'admin')),
  engineer_level         text check (engineer_level in ('L1', 'L2')),
  team_id                uuid references public.teams (id) on delete set null,
  avatar_url             text,
  job_title              text,
  department             text,
  location               text,
  is_active              boolean not null default true,
  notifications_seen_at  timestamptz,
  created_at             timestamptz not null default now(),
  updated_at             timestamptz not null default now(),
  constraint profiles_engineer_level_requires_staff check (engineer_level is null or role in ('engineer', 'admin'))
);
create unique index profiles_email_key on public.profiles (lower(email));
create index profiles_team_id_idx on public.profiles (team_id);
create index profiles_assignable_idx on public.profiles (team_id, engineer_level) where is_active and engineer_level is not null;

-- ─── Service catalogue ──────────────────────────────────────────────────────

create table public.services (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  description    text,
  category       text,
  owner_team_id  uuid references public.teams (id) on delete set null,
  criticality    text not null default 'medium' check (criticality in ('low', 'medium', 'high', 'critical')),
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now(),
  constraint services_name_key unique (name)
);
create index services_owner_team_id_idx on public.services (owner_team_id);

create table public.assets (
  id          uuid primary key default gen_random_uuid(),
  name        text not null,
  asset_type  text not null check (asset_type in ('laptop', 'desktop', 'mobile', 'peripheral', 'server', 'application', 'network_device', 'other')),
  owner_id    uuid references public.profiles (id) on delete set null,
  service_id  uuid references public.services (id) on delete set null,
  metadata    jsonb not null default '{}'::jsonb,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index assets_owner_id_idx on public.assets (owner_id);
create index assets_service_id_idx on public.assets (service_id);

-- ─── Policy & configuration ─────────────────────────────────────────────────

create table public.sla_policies (
  id                       uuid primary key default gen_random_uuid(),
  name                     text not null,
  priority                 text not null check (priority in ('P1', 'P2', 'P3', 'P4')),
  response_time_minutes    integer not null check (response_time_minutes > 0),
  resolution_time_minutes  integer not null check (resolution_time_minutes > 0),
  enabled                  boolean not null default true,
  created_at               timestamptz not null default now(),
  updated_at               timestamptz not null default now(),
  constraint sla_policies_response_before_resolution check (response_time_minutes <= resolution_time_minutes)
);
-- At most one active policy per priority, so due dates are unambiguous.
create unique index sla_policies_one_active_per_priority on public.sla_policies (priority) where enabled;

create table public.assignment_rules (
  id             uuid primary key default gen_random_uuid(),
  name           text not null,
  -- Null conditions are wildcards; the most specific enabled match wins.
  category       text,
  subcategory    text,
  priority       text check (priority in ('P1', 'P2', 'P3', 'P4')),
  ticket_type    text check (ticket_type in ('incident', 'service_request', 'problem', 'change')),
  service_id     uuid references public.services (id) on delete cascade,
  team_id        uuid not null references public.teams (id) on delete cascade,
  support_level  text not null default 'L1' check (support_level in ('L1', 'L2')),
  sort_order     integer not null default 100,
  enabled        boolean not null default true,
  created_at     timestamptz not null default now(),
  updated_at     timestamptz not null default now()
);
create index assignment_rules_enabled_idx on public.assignment_rules (enabled, sort_order);

-- Organisation-wide AI behaviour. Exactly one row (id = 1).
create table public.ai_configuration (
  id                         smallint primary key default 1 check (id = 1),
  ai_triage_enabled          boolean not null default true,
  ai_diagnosis_enabled       boolean not null default true,
  resolution_plans_enabled   boolean not null default true,
  automatic_actions_enabled  boolean not null default false,
  human_approval_required    boolean not null default true,
  confidence_threshold       numeric(3, 2) not null default 0.80 check (confidence_threshold between 0.50 and 0.98),
  updated_by                 uuid references public.profiles (id) on delete set null,
  created_at                 timestamptz not null default now(),
  updated_at                 timestamptz not null default now(),
  -- V1 is human-in-the-loop. The database itself refuses to store anything else,
  -- so no API bug or direct write can switch on autonomous execution.
  constraint ai_configuration_v1_no_automatic_actions check (automatic_actions_enabled = false),
  constraint ai_configuration_v1_human_approval_required check (human_approval_required = true)
);

-- Pluggable integrations. Only non-secret configuration is stored here;
-- credentials live in the environment / secret manager named by secret_ref.
create table public.integrations (
  id               uuid primary key default gen_random_uuid(),
  provider         text not null,
  display_name     text not null,
  category         text not null check (category in ('notifications', 'monitoring', 'identity', 'asset_management', 'ticketing', 'other')),
  description      text,
  enabled          boolean not null default false,
  status           text not null default 'not_configured' check (status in ('not_configured', 'connected', 'error', 'disabled')),
  config           jsonb not null default '{}'::jsonb,
  secret_ref       text,
  last_checked_at  timestamptz,
  last_error       text,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint integrations_provider_key unique (provider)
);

-- ─── Knowledge ──────────────────────────────────────────────────────────────

create table public.knowledge_sources (
  id               uuid primary key default gen_random_uuid(),
  name             text not null,
  source_type      text not null check (source_type in ('internal_articles', 'incident_history', 'runbooks', 'external')),
  description      text,
  enabled          boolean not null default true,
  config           jsonb not null default '{}'::jsonb,
  last_indexed_at  timestamptz,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint knowledge_sources_name_key unique (name)
);

create sequence public.knowledge_article_number_seq start with 100;

create table public.knowledge_articles (
  id                uuid primary key default gen_random_uuid(),
  article_number    text not null default ('KB-' || nextval('public.knowledge_article_number_seq')),
  title             text not null check (char_length(title) between 1 and 200),
  summary           text,
  content           text not null,
  category          text,
  subcategory       text,
  service_id        uuid references public.services (id) on delete set null,
  source_id         uuid references public.knowledge_sources (id) on delete set null,
  status            text not null default 'draft' check (status in ('draft', 'published', 'archived')),
  embedding_status  text not null default 'pending' check (embedding_status in ('pending', 'indexed', 'failed', 'skipped')),
  created_by        uuid references public.profiles (id) on delete set null,
  updated_by        uuid references public.profiles (id) on delete set null,
  search_vector     tsvector generated always as (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(summary, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(content, '')), 'C')
  ) stored,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  constraint knowledge_articles_article_number_key unique (article_number)
);
create index knowledge_articles_status_category_idx on public.knowledge_articles (status, category);
create index knowledge_articles_search_idx on public.knowledge_articles using gin (search_vector);

-- Chunked article text for retrieval. Embeddings are 1536-d; smaller models are
-- zero-padded (cosine similarity is unchanged), larger ones are requested at 1536.
create table public.knowledge_embeddings (
  id                    uuid primary key default gen_random_uuid(),
  knowledge_article_id  uuid not null references public.knowledge_articles (id) on delete cascade,
  chunk_index           integer not null check (chunk_index >= 0),
  chunk_text            text not null,
  embedding             extensions.vector(1536),
  embedding_model       text,
  metadata              jsonb not null default '{}'::jsonb,
  search_vector         tsvector generated always as (to_tsvector('english', chunk_text)) stored,
  created_at            timestamptz not null default now(),
  constraint knowledge_embeddings_chunk_key unique (knowledge_article_id, chunk_index)
);
create index knowledge_embeddings_vector_idx on public.knowledge_embeddings using hnsw (embedding extensions.vector_cosine_ops);
create index knowledge_embeddings_search_idx on public.knowledge_embeddings using gin (search_vector);

-- ─── Conversations (employee assistant) ─────────────────────────────────────

create table public.conversations (
  id          uuid primary key default gen_random_uuid(),
  user_id     uuid not null references public.profiles (id) on delete cascade,
  title       text,
  status      text not null default 'active' check (status in ('active', 'archived')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);
create index conversations_user_id_idx on public.conversations (user_id, updated_at desc);

-- ─── Tickets ────────────────────────────────────────────────────────────────

create sequence public.ticket_number_incident_seq start with 10200;
create sequence public.ticket_number_request_seq start with 9000;
create sequence public.ticket_number_problem_seq start with 1000;
create sequence public.ticket_number_change_seq start with 2000;

create table public.tickets (
  id                      uuid primary key default gen_random_uuid(),
  ticket_number           text not null,
  title                   text not null check (char_length(title) between 1 and 200),
  description             text not null,
  ticket_type             text not null default 'incident' check (ticket_type in ('incident', 'service_request', 'problem', 'change')),
  priority                text not null default 'P3' check (priority in ('P1', 'P2', 'P3', 'P4')),
  status                  text not null default 'new' check (status in (
                            'new', 'triaging', 'assigned', 'in_progress', 'pending_user',
                            'pending_engineer', 'escalated', 'resolved', 'closed', 'reopened')),
  category                text,
  subcategory             text,
  impact                  text check (impact in ('individual', 'team', 'department', 'organization')),
  urgency                 text check (urgency in ('low', 'medium', 'high', 'critical')),
  requester_id            uuid not null references public.profiles (id) on delete restrict,
  assigned_to             uuid references public.profiles (id) on delete set null,
  assignment_team_id      uuid references public.teams (id) on delete set null,
  -- Kept separate from the actual team so routing quality can be audited.
  ai_recommended_team_id  uuid references public.teams (id) on delete set null,
  assignment_reason       text,
  support_level           text not null default 'L1' check (support_level in ('L1', 'L2')),
  service_id              uuid references public.services (id) on delete set null,
  source                  text not null default 'assistant' check (source in ('assistant', 'portal', 'email', 'api', 'manual')),
  conversation_id         uuid references public.conversations (id) on delete set null,
  sla_policy_id           uuid references public.sla_policies (id) on delete set null,
  sla_response_due_at     timestamptz,
  sla_due_at              timestamptz,
  first_response_at       timestamptz,
  -- AI investigation progress (the UI shows stages, never reasoning).
  ai_status               text not null default 'pending' check (ai_status in ('pending', 'running', 'completed', 'failed', 'skipped')),
  ai_stage                text check (ai_stage in ('understanding', 'knowledge', 'similar_incidents', 'diagnosis', 'planning', 'assignment', 'done')),
  ai_error                text,
  resolution_summary      text,
  resolution_code         text check (resolution_code in ('fixed', 'workaround', 'no_fault_found', 'user_guidance', 'duplicate', 'other')),
  resolution_ai_summary   text,
  resolved_by             uuid references public.profiles (id) on delete set null,
  escalation_count        integer not null default 0,
  reopen_count            integer not null default 0,
  search_vector           tsvector generated always as (
    setweight(to_tsvector('english', coalesce(title, '')), 'A') ||
    setweight(to_tsvector('english', coalesce(description, '')), 'B') ||
    setweight(to_tsvector('english', coalesce(resolution_summary, '')), 'B')
  ) stored,
  created_at              timestamptz not null default now(),
  updated_at              timestamptz not null default now(),
  resolved_at             timestamptz,
  closed_at               timestamptz,
  constraint tickets_ticket_number_key unique (ticket_number)
);
create index tickets_assigned_to_status_idx on public.tickets (assigned_to, status);
create index tickets_team_status_idx on public.tickets (assignment_team_id, status);
create index tickets_requester_idx on public.tickets (requester_id, created_at desc);
create index tickets_status_priority_idx on public.tickets (status, priority);
create index tickets_type_created_idx on public.tickets (ticket_type, created_at desc);
create index tickets_open_sla_idx on public.tickets (sla_due_at) where status not in ('resolved', 'closed');
create index tickets_service_id_idx on public.tickets (service_id);
create index tickets_search_idx on public.tickets using gin (search_vector);

create or replace function public.assign_ticket_number()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if new.ticket_number is null or new.ticket_number = '' then
    new.ticket_number := case new.ticket_type
      when 'incident'        then 'INC-' || nextval('public.ticket_number_incident_seq')
      when 'service_request' then 'REQ-' || nextval('public.ticket_number_request_seq')
      when 'problem'         then 'PRB-' || nextval('public.ticket_number_problem_seq')
      when 'change'          then 'CHG-' || nextval('public.ticket_number_change_seq')
    end;
  end if;
  return new;
end;
$$;

create trigger tickets_assign_number
  before insert on public.tickets
  for each row execute function public.assign_ticket_number();

-- Structured AI output. Concise, engineer-safe explanations only — no
-- reasoning traces, prompts or raw model output are ever stored.
create table public.ticket_ai_analysis (
  id                   uuid primary key default gen_random_uuid(),
  ticket_id            uuid not null references public.tickets (id) on delete cascade,
  category             text,
  subcategory          text,
  priority             text check (priority in ('P1', 'P2', 'P3', 'P4')),
  summary              text,
  diagnosis            text,
  confidence           numeric(4, 3) check (confidence between 0 and 1),
  rationale            text,
  evidence             jsonb not null default '[]'::jsonb,
  hypotheses           jsonb not null default '[]'::jsonb,
  signals              jsonb not null default '[]'::jsonb,
  missing_information  jsonb not null default '[]'::jsonb,
  recommended_team_id  uuid references public.teams (id) on delete set null,
  handoff_summary      jsonb,
  triage_model         text,
  diagnosis_model      text,
  plan_model           text,
  created_at           timestamptz not null default now(),
  updated_at           timestamptz not null default now(),
  constraint ticket_ai_analysis_ticket_key unique (ticket_id)
);

create table public.ticket_resolution_steps (
  id                 uuid primary key default gen_random_uuid(),
  ticket_id          uuid not null references public.tickets (id) on delete cascade,
  position           integer not null check (position >= 0),
  description        text not null check (char_length(description) between 1 and 300),
  details            text,
  -- Commands/paths for the engineer to run by hand. Never executed by Nexa.
  technical_details  text,
  status             text not null default 'pending' check (status in ('pending', 'in_progress', 'completed', 'skipped')),
  source             text not null check (source in ('ai', 'engineer')),
  edited             boolean not null default false,
  -- The AI's original wording, kept so "restore AI suggestions" is lossless.
  ai_original        jsonb,
  notes              text,
  created_by         uuid references public.profiles (id) on delete set null,
  updated_by         uuid references public.profiles (id) on delete set null,
  completed_by       uuid references public.profiles (id) on delete set null,
  completed_at       timestamptz,
  deleted_at         timestamptz,
  deleted_by         uuid references public.profiles (id) on delete set null,
  created_at         timestamptz not null default now(),
  updated_at         timestamptz not null default now(),
  constraint ticket_resolution_steps_completion check ((status = 'completed') = (completed_at is not null))
);
create index ticket_resolution_steps_ticket_idx on public.ticket_resolution_steps (ticket_id, position) where deleted_at is null;

create table public.ticket_comments (
  id           uuid primary key default gen_random_uuid(),
  ticket_id    uuid not null references public.tickets (id) on delete cascade,
  author_id    uuid references public.profiles (id) on delete set null,
  author_type  text not null default 'user' check (author_type in ('user', 'ai', 'system')),
  content      text not null check (char_length(content) between 1 and 10000),
  -- internal = engineers only; requester = visible to the employee.
  visibility   text not null check (visibility in ('internal', 'requester')),
  kind         text not null default 'comment' check (kind in ('comment', 'question', 'escalation_note', 'handoff_summary', 'resolution', 'system')),
  created_at   timestamptz not null default now(),
  updated_at   timestamptz not null default now()
);
create index ticket_comments_ticket_idx on public.ticket_comments (ticket_id, created_at);

-- Every (re)assignment, so escalation history and "previously handled" access survive.
create table public.ticket_assignments (
  id             uuid primary key default gen_random_uuid(),
  ticket_id      uuid not null references public.tickets (id) on delete cascade,
  team_id        uuid references public.teams (id) on delete set null,
  assignee_id    uuid references public.profiles (id) on delete set null,
  support_level  text not null check (support_level in ('L1', 'L2')),
  reason         text not null,
  assigned_by    uuid references public.profiles (id) on delete set null,
  created_at     timestamptz not null default now()
);
create index ticket_assignments_ticket_idx on public.ticket_assignments (ticket_id, created_at);
create index ticket_assignments_assignee_idx on public.ticket_assignments (assignee_id);

-- Append-only audit trail: who, what, when, old → new, and whether a person,
-- the AI or the system did it.
create table public.audit_history (
  id           uuid primary key default gen_random_uuid(),
  ticket_id    uuid references public.tickets (id) on delete set null,
  entity_type  text not null default 'ticket',
  entity_id    uuid,
  actor_id     uuid references public.profiles (id) on delete set null,
  actor_type   text not null check (actor_type in ('user', 'ai', 'system')),
  actor_role   text,
  action       text not null,
  old_value    jsonb,
  new_value    jsonb,
  metadata     jsonb not null default '{}'::jsonb,
  created_at   timestamptz not null default now()
);
create index audit_history_ticket_idx on public.audit_history (ticket_id, created_at);
create index audit_history_entity_idx on public.audit_history (entity_type, created_at desc);
create index audit_history_actor_idx on public.audit_history (actor_id, created_at desc);
create index audit_history_created_idx on public.audit_history (created_at desc);

create or replace function public.audit_history_append_only()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'DELETE' then
    raise exception 'audit_history is append-only';
  end if;
  -- The only permitted update is the FK nulling ticket_id when a ticket is removed.
  if (to_jsonb(new) - 'ticket_id') = (to_jsonb(old) - 'ticket_id') and new.ticket_id is null then
    return new;
  end if;
  raise exception 'audit_history is append-only';
end;
$$;

create trigger audit_history_immutable
  before update or delete on public.audit_history
  for each row execute function public.audit_history_append_only();

create table public.conversation_messages (
  id               uuid primary key default gen_random_uuid(),
  conversation_id  uuid not null references public.conversations (id) on delete cascade,
  role             text not null check (role in ('user', 'assistant', 'system')),
  content          text not null default '',
  message_type     text not null default 'text' check (message_type in (
                     'text', 'triage_proposal', 'ticket_created', 'ticket_status',
                     'knowledge_answer', 'clarification', 'error')),
  payload          jsonb not null default '{}'::jsonb,
  ticket_id        uuid references public.tickets (id) on delete set null,
  created_at       timestamptz not null default now()
);
create index conversation_messages_conversation_idx on public.conversation_messages (conversation_id, created_at);

create table public.attachments (
  id                    uuid primary key default gen_random_uuid(),
  bucket                text not null,
  storage_path          text not null,
  file_name             text not null,
  content_type          text,
  size_bytes            bigint check (size_bytes >= 0),
  ticket_id             uuid references public.tickets (id) on delete cascade,
  conversation_id       uuid references public.conversations (id) on delete set null,
  knowledge_article_id  uuid references public.knowledge_articles (id) on delete cascade,
  uploaded_by           uuid references public.profiles (id) on delete set null,
  created_at            timestamptz not null default now(),
  constraint attachments_storage_path_key unique (bucket, storage_path)
);
create index attachments_ticket_idx on public.attachments (ticket_id);
create index attachments_conversation_idx on public.attachments (conversation_id);

-- Retrieval representation of resolved tickets ("have we seen this before?").
create table public.incident_embeddings (
  id               uuid primary key default gen_random_uuid(),
  ticket_id        uuid not null references public.tickets (id) on delete cascade,
  content          text not null,
  embedding        extensions.vector(1536),
  embedding_model  text,
  metadata         jsonb not null default '{}'::jsonb,
  search_vector    tsvector generated always as (to_tsvector('english', content)) stored,
  created_at       timestamptz not null default now(),
  updated_at       timestamptz not null default now(),
  constraint incident_embeddings_ticket_key unique (ticket_id)
);
create index incident_embeddings_vector_idx on public.incident_embeddings using hnsw (embedding extensions.vector_cosine_ops);
create index incident_embeddings_search_idx on public.incident_embeddings using gin (search_vector);

-- Operational record of each agent run (identifiers, model, outcome, timing).
-- Deliberately stores no prompts, messages or reasoning.
create table public.agent_runs (
  id               uuid primary key default gen_random_uuid(),
  ticket_id        uuid references public.tickets (id) on delete set null,
  conversation_id  uuid references public.conversations (id) on delete set null,
  agent_name       text not null,
  operation        text not null,
  model            text,
  status           text not null default 'running' check (status in ('running', 'completed', 'failed')),
  error_code       text,
  tool_calls       integer not null default 0,
  input_tokens     integer,
  output_tokens    integer,
  started_at       timestamptz not null default now(),
  completed_at     timestamptz,
  duration_ms      integer,
  metadata         jsonb not null default '{}'::jsonb
);
create index agent_runs_ticket_idx on public.agent_runs (ticket_id, started_at desc);

-- ─── updated_at triggers ────────────────────────────────────────────────────

do $$
declare
  t text;
begin
  foreach t in array array[
    'teams', 'profiles', 'services', 'assets', 'sla_policies', 'assignment_rules',
    'ai_configuration', 'integrations', 'knowledge_sources', 'knowledge_articles',
    'conversations', 'tickets', 'ticket_ai_analysis', 'ticket_resolution_steps',
    'ticket_comments', 'incident_embeddings'
  ]
  loop
    execute format(
      'create trigger %I before update on public.%I for each row execute function public.set_updated_at()',
      t || '_set_updated_at', t
    );
  end loop;
end;
$$;
