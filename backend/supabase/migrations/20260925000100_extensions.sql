-- Nexa · extensions and shared helpers
-- pgvector powers semantic retrieval over knowledge articles and resolved incidents.

create extension if not exists vector with schema extensions;
create extension if not exists pg_trgm with schema extensions;

-- Keeps updated_at honest on every table that has one.
create or replace function public.set_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;
