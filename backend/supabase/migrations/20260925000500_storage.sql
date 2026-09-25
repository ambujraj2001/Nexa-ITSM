-- Nexa · Supabase Storage buckets
--
-- Both buckets are private. storage.objects has RLS enabled and we add no client
-- policies, so only the backend (service role) can read or write objects. The
-- API authorises each request and hands out short-lived signed URLs.

insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values
  ('ticket-attachments', 'ticket-attachments', false, 10485760, array[
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    'application/pdf', 'text/plain', 'text/csv', 'application/json',
    'application/zip', 'application/x-zip-compressed'
  ]),
  ('knowledge-attachments', 'knowledge-attachments', false, 26214400, array[
    'image/png', 'image/jpeg', 'image/gif', 'image/webp',
    'application/pdf', 'text/plain', 'text/markdown', 'text/csv'
  ])
on conflict (id) do nothing;
