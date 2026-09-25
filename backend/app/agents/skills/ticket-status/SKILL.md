---
name: ticket-status
description: The employee asks about one of their tickets — status, who is handling it, why it is slow, what is needed from them. Includes bare numbers like "ticket 10227" or "#10227".
---

# Ticket status

1. Identify which ticket they mean:
   - A number in the message ("10227", "#10227", "INC-10227") → call `get_my_ticket` with it.
   - "it" / "my ticket" with no number → the ticket discussed most recently in the
     conversation; if unclear, call `list_my_tickets` and pick the open one they are
     most likely asking about.
2. `get_my_ticket` only returns tickets this employee raised. If it says the ticket was
   not found, do NOT guess or describe another ticket — return `action: "status"` with
   the number in `requested_refs` and no `ticket_numbers`.
3. Return `action: "status"` with the verified ticket number(s) in `ticket_numbers`.
   Nexa writes the actual status sentence from the database, so keep `reply` to a short
   lead-in (or leave it empty). Never state status, assignee, SLA or step counts yourself.
