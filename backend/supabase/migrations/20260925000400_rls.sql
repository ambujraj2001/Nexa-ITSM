-- Nexa · Row Level Security
--
-- Defence in depth. The browser only uses Supabase for authentication; all
-- application reads and writes go through the Nexa API, which enforces the same
-- rules in code (app/domain/policies.py). These policies make sure that a
-- client talking to PostgREST directly with a user's JWT can, at most, *read*
-- rows that user is entitled to see — and can never write anything.

do $$
declare
  t text;
begin
  foreach t in array array[
    'teams', 'profiles', 'services', 'assets', 'sla_policies', 'assignment_rules',
    'ai_configuration', 'integrations', 'knowledge_sources', 'knowledge_articles',
    'knowledge_embeddings', 'conversations', 'tickets', 'ticket_ai_analysis',
    'ticket_resolution_steps', 'ticket_comments', 'ticket_assignments', 'audit_history',
    'conversation_messages', 'attachments', 'incident_embeddings', 'agent_runs'
  ]
  loop
    execute format('alter table public.%I enable row level security', t);
    -- Anonymous visitors get nothing; signed-in clients are read-only.
    execute format('revoke all on table public.%I from anon', t);
    execute format('revoke insert, update, delete, truncate, references, trigger on table public.%I from authenticated', t);
  end loop;
end;
$$;

revoke all on all sequences in schema public from anon, authenticated;

-- ─── Reference data ─────────────────────────────────────────────────────────

create policy teams_read on public.teams
  for select to authenticated using (true);

create policy services_read on public.services
  for select to authenticated using (true);

create policy knowledge_articles_read on public.knowledge_articles
  for select to authenticated
  using (status = 'published' or (select public.auth_role()) in ('engineer', 'admin'));

-- Staff-only configuration.
create policy sla_policies_read on public.sla_policies
  for select to authenticated using ((select public.auth_role()) in ('engineer', 'admin'));

create policy assignment_rules_read on public.assignment_rules
  for select to authenticated using ((select public.auth_role()) in ('engineer', 'admin'));

create policy knowledge_sources_read on public.knowledge_sources
  for select to authenticated using ((select public.auth_role()) in ('engineer', 'admin'));

create policy integrations_read on public.integrations
  for select to authenticated using ((select public.auth_role()) = 'admin');

create policy ai_configuration_read on public.ai_configuration
  for select to authenticated using (true);

-- ─── People ─────────────────────────────────────────────────────────────────

create policy profiles_read on public.profiles
  for select to authenticated
  using (
    auth_user_id = (select auth.uid())
    or (select public.auth_role()) in ('engineer', 'admin')
  );

create policy assets_read on public.assets
  for select to authenticated
  using (
    owner_id = (select public.auth_profile_id())
    or (select public.auth_role()) in ('engineer', 'admin')
  );

-- ─── Tickets and their children ─────────────────────────────────────────────

create policy tickets_read on public.tickets
  for select to authenticated
  using (
    requester_id = (select public.auth_profile_id())
    or (select public.auth_role()) = 'admin'
    or (
      (select public.auth_role()) = 'engineer'
      and (
        assigned_to = (select public.auth_profile_id())
        or assignment_team_id = (select public.auth_team_id())
        or exists (
          select 1 from public.ticket_assignments a
           where a.ticket_id = tickets.id
             and a.assignee_id = (select public.auth_profile_id())
        )
      )
    )
  );

create policy ticket_ai_analysis_read on public.ticket_ai_analysis
  for select to authenticated using (public.can_view_ticket(ticket_id));

create policy ticket_resolution_steps_read on public.ticket_resolution_steps
  for select to authenticated
  using (deleted_at is null and public.can_view_ticket(ticket_id));

-- Internal notes never reach employees.
create policy ticket_comments_read on public.ticket_comments
  for select to authenticated
  using (
    public.can_view_ticket(ticket_id)
    and (visibility = 'requester' or (select public.auth_role()) in ('engineer', 'admin'))
  );

create policy ticket_assignments_read on public.ticket_assignments
  for select to authenticated
  using ((select public.auth_role()) in ('engineer', 'admin') and public.can_view_ticket(ticket_id));

create policy attachments_read on public.attachments
  for select to authenticated
  using (
    (ticket_id is not null and public.can_view_ticket(ticket_id))
    or (knowledge_article_id is not null and (select public.auth_role()) in ('engineer', 'admin'))
    or uploaded_by = (select public.auth_profile_id())
  );

create policy audit_history_read on public.audit_history
  for select to authenticated using ((select public.auth_role()) = 'admin');

-- ─── Conversations ──────────────────────────────────────────────────────────

create policy conversations_read on public.conversations
  for select to authenticated using (user_id = (select public.auth_profile_id()));

create policy conversation_messages_read on public.conversation_messages
  for select to authenticated
  using (
    exists (
      select 1 from public.conversations c
       where c.id = conversation_messages.conversation_id
         and c.user_id = (select public.auth_profile_id())
    )
  );

-- knowledge_embeddings, incident_embeddings and agent_runs intentionally have no
-- policies: with RLS enabled that denies all direct client access.

-- ─── Column-level narrowing ─────────────────────────────────────────────────
-- Employees may see resolution *progress* on their own tickets, but technical
-- commands, engineer notes and evidence (which can reference other people's
-- incidents) are served only through the role-aware API.

revoke select on table public.ticket_resolution_steps from authenticated;
grant select (id, ticket_id, position, description, status, source, completed_at, created_at, updated_at, deleted_at)
  on public.ticket_resolution_steps to authenticated;

revoke select on table public.ticket_ai_analysis from authenticated;
grant select (id, ticket_id, category, subcategory, priority, summary, diagnosis, confidence, created_at, updated_at)
  on public.ticket_ai_analysis to authenticated;
