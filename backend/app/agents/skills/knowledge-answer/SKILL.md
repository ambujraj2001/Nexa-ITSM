---
name: knowledge-answer
description: A how-to or policy question that documentation can answer ("How do I set up MFA?", "How do I connect to Wi-Fi?").
---

# Knowledge answer

1. Call `search_knowledge` with specific terms from the question.
2. Answer ONLY from the returned articles, in 2–5 short sentences or numbered steps.
   List every article you used in `knowledge_sources` (their KB references).
3. If nothing relevant came back, say you could not find it in the knowledge base and
   offer to raise a ticket (`action: "knowledge"`, empty `knowledge_sources`).
4. Answer the latest question only — do not bring up the employee's tickets.
