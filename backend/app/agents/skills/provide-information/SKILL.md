---
name: provide-information
description: The employee is answering a question IT asked on one of their tickets, or adding detail to an existing ticket.
---

# Provide information

1. Call `list_my_tickets`. A ticket "waiting on you" means IT asked them something.
2. If the message answers that question or adds detail to a specific open ticket, return
   `action: "add_information"` with that ticket in `target_ticket_number`. Nexa adds the
   message to the ticket verbatim and notifies the engineer.
3. If it is actually a new, unrelated problem, use the report-issue skill instead.
