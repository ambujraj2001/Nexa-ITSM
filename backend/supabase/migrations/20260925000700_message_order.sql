-- Nexa · stable conversation order
-- now() is the transaction start time, so messages written in one request (the user's
-- message and the assistant's reply) shared a timestamp and could sort either way.
-- clock_timestamp() advances within the transaction.
alter table public.conversation_messages alter column created_at set default clock_timestamp();
