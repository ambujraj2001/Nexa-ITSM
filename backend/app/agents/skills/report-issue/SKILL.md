---
name: report-issue
description: The employee describes something broken or not working (an incident) and needs IT to fix it.
---

# Report an issue

1. If the description is too vague to act on (e.g. "my laptop is weird") and you have
   not already asked in this conversation, return `action: "clarify"` with ONE short,
   specific question in `clarifying_question` (what happens, any error text, since when).
2. Check `search_knowledge` for a self-service fix only if the problem sounds like a
   common how-to (password reset, Wi-Fi). Even then, offer to file a ticket.
3. Otherwise return `action: "propose_ticket"`. Nexa builds the proposal card (category,
   priority, routing) deterministically; the employee must confirm before a ticket is
   created. Put a one-sentence empathetic lead-in in `reply`.
4. Never promise a fix, a time, or claim you (or Nexa) changed anything.
