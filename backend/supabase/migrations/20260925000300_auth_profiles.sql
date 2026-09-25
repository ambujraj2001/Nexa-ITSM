-- Nexa · Supabase Auth → application profile
--
-- Every new auth user gets a profile with the *employee* role. Roles are never
-- read from user-supplied metadata (users control that at sign-up); only an
-- admin, through the API, can promote someone to engineer or admin.

create or replace function public.handle_new_auth_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  display_name text := coalesce(
    nullif(trim(new.raw_user_meta_data ->> 'full_name'), ''),
    nullif(trim(new.raw_user_meta_data ->> 'name'), ''),
    split_part(new.email, '@', 1)
  );
begin
  -- Link a pre-provisioned profile (created by an admin invite or seed) by email.
  update public.profiles
     set auth_user_id = new.id,
         avatar_url = coalesce(avatar_url, new.raw_user_meta_data ->> 'avatar_url')
   where lower(email) = lower(new.email)
     and auth_user_id is null;

  if not found then
    insert into public.profiles (auth_user_id, email, name, avatar_url)
    values (new.id, lower(new.email), display_name, new.raw_user_meta_data ->> 'avatar_url')
    on conflict do nothing;
  end if;
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_auth_user();

-- Keep the profile email in sync when a user changes it in Supabase Auth.
create or replace function public.handle_auth_user_email_change()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
begin
  if new.email is distinct from old.email then
    update public.profiles set email = lower(new.email) where auth_user_id = new.id;
  end if;
  return new;
end;
$$;

create trigger on_auth_user_email_changed
  after update of email on auth.users
  for each row execute function public.handle_auth_user_email_change();

-- ─── RLS helpers ────────────────────────────────────────────────────────────
-- SECURITY DEFINER so policies can consult profiles without recursive RLS.
-- Each returns facts about the *calling* user only.

create or replace function public.auth_profile_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select p.id from public.profiles p where p.auth_user_id = auth.uid() and p.is_active
$$;

create or replace function public.auth_role()
returns text
language sql
stable
security definer
set search_path = ''
as $$
  select p.role from public.profiles p where p.auth_user_id = auth.uid() and p.is_active
$$;

create or replace function public.auth_team_id()
returns uuid
language sql
stable
security definer
set search_path = ''
as $$
  select p.team_id from public.profiles p where p.auth_user_id = auth.uid() and p.is_active
$$;

-- Mirrors the backend's ticket visibility policy (app/domain/policies.py).
create or replace function public.can_view_ticket(p_ticket_id uuid)
returns boolean
language sql
stable
security definer
set search_path = ''
as $$
  select exists (
    select 1
      from public.tickets t
      join public.profiles me on me.auth_user_id = auth.uid() and me.is_active
     where t.id = p_ticket_id
       and (
         t.requester_id = me.id
         or me.role = 'admin'
         or (
           me.role = 'engineer'
           and (
             t.assigned_to = me.id
             or (me.team_id is not null and t.assignment_team_id = me.team_id)
             or exists (
               select 1 from public.ticket_assignments a
                where a.ticket_id = t.id and a.assignee_id = me.id
             )
           )
         )
       )
  )
$$;

revoke execute on function public.handle_new_auth_user() from public, anon, authenticated;
revoke execute on function public.handle_auth_user_email_change() from public, anon, authenticated;
revoke execute on function public.auth_profile_id() from public, anon;
revoke execute on function public.auth_role() from public, anon;
revoke execute on function public.auth_team_id() from public, anon;
revoke execute on function public.can_view_ticket(uuid) from public, anon;
grant execute on function public.auth_profile_id() to authenticated;
grant execute on function public.auth_role() to authenticated;
grant execute on function public.auth_team_id() to authenticated;
grant execute on function public.can_view_ticket(uuid) to authenticated;
