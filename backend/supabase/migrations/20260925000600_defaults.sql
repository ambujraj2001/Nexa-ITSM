-- Nexa · configuration every environment needs (not demo data — see backend/scripts/seed.py)

-- V1 AI behaviour: AI triages, diagnoses and plans; humans execute and resolve.
insert into public.ai_configuration (
  id, ai_triage_enabled, ai_diagnosis_enabled, resolution_plans_enabled,
  automatic_actions_enabled, human_approval_required, confidence_threshold
)
values (1, true, true, true, false, true, 0.80)
on conflict (id) do nothing;

-- Calendar-time SLAs (24×7). Admins can tune them in Settings → SLA Policies.
insert into public.sla_policies (name, priority, response_time_minutes, resolution_time_minutes)
select v.name, v.priority, v.response, v.resolution
  from (values
    ('P1 · Critical', 'P1', 15, 240),
    ('P2 · High', 'P2', 60, 480),
    ('P3 · Normal', 'P3', 240, 1440),
    ('P4 · Low', 'P4', 480, 4320)
  ) as v(name, priority, response, resolution)
 where not exists (select 1 from public.sla_policies s where s.priority = v.priority);

insert into public.knowledge_sources (name, source_type, description, enabled)
values
  ('Nexa knowledge base', 'internal_articles', 'Published articles and runbooks written by your IT team.', true),
  ('Resolved incident history', 'incident_history', 'Resolved tickets with their diagnosis, steps and resolution.', true)
on conflict (name) do nothing;

-- Integration catalogue. Nothing is connected until an admin configures it.
insert into public.integrations (provider, display_name, category, description, enabled, status, secret_ref)
values
  ('supabase_auth', 'Supabase Auth', 'identity', 'Email, magic-link and OAuth sign-in for your workspace.', true, 'connected', null),
  ('slack', 'Slack', 'notifications', 'Ticket updates and assignment notifications in Slack channels.', false, 'not_configured', 'SLACK_BOT_TOKEN'),
  ('email', 'Email notifications', 'notifications', 'Status and resolution emails to requesters.', false, 'not_configured', 'SMTP_PASSWORD'),
  ('monitoring_webhook', 'Monitoring webhooks', 'monitoring', 'Create incidents from monitoring alerts via signed webhooks.', false, 'not_configured', 'MONITORING_WEBHOOK_SECRET'),
  ('asset_management', 'Asset management', 'asset_management', 'Sync devices and owners from your asset register.', false, 'not_configured', 'ASSET_SYNC_TOKEN')
on conflict (provider) do nothing;
