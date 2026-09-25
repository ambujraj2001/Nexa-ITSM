# Nexa --- Full-Stack AI-Native ITSM Implementation Specification

## Purpose

You are implementing **Nexa**, an AI-native IT Service Management (ITSM)
platform.

The project already contains a **UI folder with the screens/design code
that was created previously**. Treat that UI implementation as the
visual source of truth.

Your job is to turn the existing UI into a **fully working full-stack
application** without unnecessarily redesigning the screens.

The implementation must connect the existing screens to a real backend,
database, authentication, AI/agent layer, observability, caching, ticket
workflows, knowledge retrieval, assignment, escalation, and role-based
behavior.

### Core product principle

> **AI investigates. Humans resolve.**

Nexa V1 is explicitly **human-in-the-loop**.

The AI may:

-   understand a user's problem
-   classify the request
-   determine priority
-   investigate available context
-   retrieve relevant knowledge
-   inspect historical incidents
-   form a diagnosis/hypotheses
-   explain supporting evidence
-   create a resolution plan
-   suggest next steps
-   recommend assignment
-   summarize progress
-   prepare escalation context
-   summarize a resolved ticket

The AI must **not directly execute production/infrastructure actions in
V1**.

An engineer must perform the actual remediation.

Do not build autonomous infrastructure execution into V1.

------------------------------------------------------------------------

# 1. First Step: Inspect the Existing Project

Before writing new UI code:

1.  Inspect the entire repository.
2.  Locate the existing `UI` folder.
3.  Understand the framework, routing, components, styling system, state
    management, and existing mock data.
4.  Run the existing application.
5.  Inspect all existing screens.
6.  Reuse existing components wherever practical.
7.  Do not replace the UI with a generic dashboard.
8.  Do not redesign the visual system unless required for functionality.
9.  Preserve the existing visual hierarchy, spacing, typography,
    navigation, and layouts.

The existing UI is the design reference.

The goal is:

``` text
Existing UI
     +
Real backend
     +
Real database
     +
Real authentication
     +
Real AI
     +
Real ticket lifecycle
     =
Working Nexa product
```

------------------------------------------------------------------------

# 2. Product Overview

Nexa is an AI-native ITSM platform designed around conversational issue
reporting and AI-assisted investigation.

Traditional ITSM:

``` text
Employee
   ↓
Form
   ↓
Ticket
   ↓
Queue
   ↓
Engineer investigates
```

Nexa:

``` text
Employee
   ↓
Describes problem naturally
   ↓
AI understands + classifies
   ↓
AI investigates
   ↓
AI retrieves knowledge/history
   ↓
AI diagnoses
   ↓
AI creates resolution plan
   ↓
Ticket created
   ↓
Correct engineer/team assigned
   ↓
Engineer executes suggested steps
   ↓
Escalate or resolve
```

------------------------------------------------------------------------

# 3. Primary User Roles

Implement three primary roles.

## Employee

Employees can:

-   sign in
-   interact with the AI assistant
-   describe an IT problem
-   create an incident/request
-   view their tickets
-   view ticket status
-   ask about ticket status
-   see who is handling the issue
-   provide additional information
-   respond to engineer questions
-   see resolution progress
-   see final resolution summary

The employee experience should feel like an AI assistant, not a
traditional ITSM administration dashboard.

------------------------------------------------------------------------

## L1/L2 Engineer

Engineers can:

-   see their operations dashboard
-   see assigned tickets
-   see urgent tickets
-   see due-soon tickets
-   see tickets requiring attention
-   open ticket workspace
-   view user problem
-   view AI diagnosis
-   view evidence
-   view suggested resolution plan
-   execute steps manually
-   mark steps complete
-   edit steps
-   add steps
-   delete steps
-   reorder steps
-   add notes
-   communicate with requester
-   escalate to L2
-   resolve ticket
-   reopen ticket when appropriate
-   view ticket activity/history

L1 and L2 should share the general engineer experience, while L2 can
receive escalations and more complex tickets.

------------------------------------------------------------------------

## Admin

Admins can:

-   manage users
-   manage teams
-   manage assignment rules
-   manage SLA policies
-   manage knowledge sources
-   configure AI behavior
-   configure integrations
-   view audit logs
-   manage services/assets
-   configure automation settings
-   manage system configuration

------------------------------------------------------------------------

# 4. Existing Screens to Wire

The UI folder contains the following screens.

Do not throw them away.

Wire each screen to real data and backend APIs.

## Screen 1 --- Employee AI Assistant

The employee's primary entry point.

Expected experience:

``` text
Login
  ↓
Employee Portal
  ↓
"How can we help you today?"
  ↓
Employee describes problem
  ↓
AI conversation
  ↓
AI analyzes problem
  ↓
Ticket created
  ↓
Ticket status shown
```

The screen should support:

-   conversational messages
-   loading state
-   AI analysis state
-   ticket creation
-   ticket reference
-   ticket status
-   follow-up questions
-   active ticket
-   ticket history

Keep the AI conversation visually dominant.

Recent assistance/ticket history should remain secondary.

------------------------------------------------------------------------

# 5. Screen 2 --- Engineer Operations Dashboard

The engineer dashboard is an operational dispatch view.

The existing UI contains concepts such as:

-   Assigned to me
-   Urgent
-   Due soon
-   Needs Your Attention
-   My Tickets

Wire all of these to real database queries.

The hierarchy should remain:

``` text
Operations Dispatch
       ↓
Key metrics
       ↓
Needs Your Attention
       ↓
My Tickets
```

Do not turn this into a dense analytics dashboard.

"Needs Your Attention" should remain the dominant work queue.

"My Tickets" should be a compact list/table.

Use real ticket statuses and SLA information.

------------------------------------------------------------------------

# 6. Screen 3 --- Engineer Ticket Workspace

This is one of the most important screens.

The ticket workspace should show:

## User Problem

The original employee request.

Example:

> My VPN isn't connecting since this morning.

## AI Diagnosis

Example:

``` text
Likely cause:
VPN authentication certificate may have expired.

Confidence:
High

Evidence:
- Similar incidents from the previous 30 days
- Knowledge article about VPN certificate expiration
- Authentication failure pattern
```

Do not expose chain-of-thought.

Use concise explainable sections:

-   Diagnosis
-   Evidence
-   Why this was suggested
-   Suggested next steps

Do not expose internal reasoning traces.

------------------------------------------------------------------------

# 7. Resolution Plan

The resolution plan is central to the engineer workflow.

Example:

``` text
1. Check VPN client authentication status
2. Verify certificate validity
3. Check authentication logs
4. Verify VPN gateway connectivity
5. Test user authentication
```

Each step should support:

-   pending
-   in progress
-   completed
-   skipped

The engineer must be able to:

-   complete a step
-   edit a step
-   add a step
-   delete a step
-   reorder a step
-   add a note

The AI-generated plan is only a recommendation.

The engineer controls execution.

Visually distinguish:

-   AI suggested
-   Engineer completed
-   Engineer edited
-   System event

------------------------------------------------------------------------

# 8. Engineer Execution Boundary

This is a core V1 requirement.

The interface should communicate clearly but subtly:

> Human execution required.

Do not make it look like a limitation or warning banner everywhere.

The AI may recommend:

``` text
Run command X
Check service Y
Verify configuration Z
```

But it must not execute those operations in V1.

Technical commands should be hidden behind something like:

``` text
View technical details
```

Do not put raw infrastructure commands in the primary visual workflow.

------------------------------------------------------------------------

# 9. Escalation

An engineer should be able to escalate a ticket from L1 to L2.

When escalating:

-   preserve original user request
-   preserve AI diagnosis
-   preserve evidence
-   preserve resolution plan
-   preserve completed steps
-   preserve engineer notes
-   preserve activity history
-   record escalation reason
-   assign to L2/team

Example:

``` text
L1 Engineer
   ↓
Escalate
   ↓
Select reason
   ↓
Optional note
   ↓
L2 assignment
```

The L2 engineer should receive the entire investigation context.

Do not force L2 to start from zero.

------------------------------------------------------------------------

# 10. Resolution

When the engineer resolves a ticket:

1.  Require/allow resolution summary.
2.  Store resolution details.
3.  Mark ticket resolved.
4.  Record resolver.
5.  Record timestamp.
6.  Add audit event.
7.  Allow AI to summarize the resolution.
8.  Make the final resolution visible to the employee.

Example:

``` text
Resolved

Resolution:
VPN certificate was expired and renewed.

Completed steps:
✓ Checked certificate
✓ Renewed certificate
✓ Tested authentication
```

------------------------------------------------------------------------

# 11. Screen 4 --- AI & Automation Settings

Wire the existing settings UI to actual configuration.

Main settings:

``` text
AI Triage                    ON
AI Diagnosis                 ON
Resolution Plans             ON
Automatic Infrastructure
Actions                      OFF

Human Approval Required      ON
```

For V1:

``` text
Automatic Infrastructure Actions = OFF
Human execution required = TRUE
```

This must be enforced server-side, not just represented visually.

Advanced settings should be collapsed.

Potential advanced configuration:

-   model configuration
-   knowledge/RAG sources
-   confidence thresholds
-   provider configuration
-   integration configuration

Do not show unnecessary technical metrics such as:

-   token counts
-   chain-of-thought
-   internal prompts
-   raw model traces

on the main settings page.

------------------------------------------------------------------------

# 12. Authentication

Implement real authentication using Supabase Auth.

Support:

-   email authentication
-   Google authentication if the existing UI provides it
-   Microsoft authentication if configured
-   session persistence
-   logout
-   protected routes

After authentication, route users according to role:

``` text
employee → Employee AI Assistant
engineer → Engineer Operations Dashboard
admin → Admin/settings area
```

Never trust role information supplied by the frontend.

Authorization must be enforced by the backend/database.

------------------------------------------------------------------------

# 13. Database --- Supabase PostgreSQL

Use **Supabase PostgreSQL** as the primary application database.

Use PostgreSQL for:

-   users
-   teams
-   tickets
-   incidents
-   requests
-   changes
-   services
-   assets
-   ticket steps
-   comments
-   AI analysis
-   knowledge articles
-   embeddings
-   assignment rules
-   SLA policies
-   audit history
-   AI configuration

Do not introduce MongoDB, Elasticsearch, OpenSearch, or another primary
database.

------------------------------------------------------------------------

# 14. PostgreSQL Schema

Implement a production-oriented relational schema.

## profiles

``` text
id
auth_user_id
name
email
role
team_id
avatar_url
created_at
updated_at
```

Roles:

``` text
employee
engineer
admin
```

------------------------------------------------------------------------

## teams

``` text
id
name
description
created_at
updated_at
```

Examples:

``` text
IT Support
Network
Security
Infrastructure
Applications
```

------------------------------------------------------------------------

## tickets

``` text
id
ticket_number
title
description
ticket_type
priority
status
requester_id
assigned_to
assignment_team_id
service_id
source
sla_due_at
created_at
updated_at
resolved_at
closed_at
```

Ticket types:

``` text
incident
service_request
problem
change
```

Statuses:

``` text
new
triaging
assigned
in_progress
pending_user
pending_engineer
escalated
resolved
closed
reopened
```

Priorities:

``` text
P1
P2
P3
P4
```

------------------------------------------------------------------------

# 15. ticket_ai_analysis

Store the structured AI output.

``` text
id
ticket_id
category
subcategory
priority
summary
diagnosis
confidence
evidence
hypotheses
created_at
updated_at
```

Do not store hidden chain-of-thought.

Only store concise, user/engineer-safe explanations and evidence.

------------------------------------------------------------------------

# 16. ticket_resolution_steps

``` text
id
ticket_id
position
description
status
source
created_by
completed_by
completed_at
created_at
updated_at
```

Source:

``` text
ai
engineer
```

Status:

``` text
pending
in_progress
completed
skipped
```

------------------------------------------------------------------------

# 17. ticket_comments

``` text
id
ticket_id
author_id
content
visibility
created_at
updated_at
```

Visibility:

``` text
internal
requester
```

Internal comments must not be shown to employees.

------------------------------------------------------------------------

# 18. ticket_history / audit_history

``` text
id
ticket_id
actor_id
action
old_value
new_value
metadata
created_at
```

Record important changes:

-   ticket created
-   priority changed
-   status changed
-   assignment changed
-   step added
-   step completed
-   step edited
-   step deleted
-   escalation
-   resolution
-   reopening
-   AI analysis generated

------------------------------------------------------------------------

# 19. knowledge_articles

``` text
id
title
content
category
service_id
status
created_by
created_at
updated_at
```

Use pgvector for embeddings.

------------------------------------------------------------------------

# 20. knowledge_embeddings

Use Supabase's pgvector extension.

``` text
id
knowledge_article_id
embedding
chunk_text
metadata
created_at
```

Create appropriate vector indexes.

Use semantic search for AI investigation.

------------------------------------------------------------------------

# 21. Historical Incidents

Historical tickets/incidents should also be searchable.

Create a suitable embedding representation for resolved incidents.

This allows the AI to answer:

``` text
Have we seen this before?
How was it resolved?
What evidence supported the resolution?
```

Do not blindly copy old resolutions.

Treat historical incidents as supporting evidence.

------------------------------------------------------------------------

# 22. Services

``` text
id
name
description
owner_team_id
criticality
created_at
updated_at
```

------------------------------------------------------------------------

# 23. Assets

``` text
id
name
asset_type
owner_id
service_id
metadata
created_at
updated_at
```

------------------------------------------------------------------------

# 24. Assignment Rules

Create:

``` text
assignment_rules
```

with fields such as:

``` text
id
name
category
priority
team_id
enabled
created_at
updated_at
```

The system should be able to recommend or determine an appropriate
assignment team.

Keep the rules deterministic where possible.

AI can recommend; deterministic rules should be preferred for hard
routing requirements.

------------------------------------------------------------------------

# 25. SLA Policies

Create:

``` text
sla_policies
```

with:

``` text
id
name
priority
response_time_minutes
resolution_time_minutes
enabled
created_at
updated_at
```

Calculate due dates when tickets are created.

Use these values in:

-   dashboard
-   ticket workspace
-   due soon queue
-   urgent queue

------------------------------------------------------------------------

# 26. AI Configuration

Create an organization/system-level configuration.

Example:

``` text
ai_triage_enabled
ai_diagnosis_enabled
resolution_plans_enabled
automatic_actions_enabled
human_approval_required
confidence_threshold
```

V1 defaults:

``` text
ai_triage_enabled = true
ai_diagnosis_enabled = true
resolution_plans_enabled = true
automatic_actions_enabled = false
human_approval_required = true
```

------------------------------------------------------------------------

# 27. Integrations

Create an integrations configuration model so future systems can be
added without redesigning the schema.

Examples:

``` text
Slack
Email
Monitoring
Identity provider
Asset management
```

Do not build every integration now.

Build the abstraction cleanly.

------------------------------------------------------------------------

# 28. Backend Architecture

Use a clean modular backend.

Recommended structure:

``` text
backend/
  app/
    main.py

    api/
      auth.py
      tickets.py
      employees.py
      engineers.py
      admin.py
      knowledge.py
      settings.py
      assignments.py

    services/
      ticket_service.py
      triage_service.py
      diagnosis_service.py
      resolution_service.py
      assignment_service.py
      sla_service.py
      knowledge_service.py
      audit_service.py

    agents/
      nex_agent.py
      triage_agent.py
      diagnosis_agent.py
      resolution_agent.py

    repositories/
      ticket_repository.py
      knowledge_repository.py
      user_repository.py

    models/
      ...

    schemas/
      ...

    infrastructure/
      supabase.py
      redis.py
      litellm.py
      telemetry.py

    utils/
      ...
```

Use dependency injection where useful.

Keep business logic out of route handlers.

------------------------------------------------------------------------

# 29. Deep Agents

Use **Deep Agents** as the high-level agent orchestration layer.

Do not build the entire agent framework manually.

The agent should have tools such as:

``` text
search_knowledge
search_historical_incidents
get_ticket
get_user
get_service
get_asset
get_team
get_sla_policy
create_ticket
update_ticket_analysis
generate_resolution_plan
recommend_assignment
```

V1 tools must respect the human-execution boundary.

Do NOT create tools such as:

``` text
restart_server
delete_resource
modify_production_config
run_production_command
```

for V1.

------------------------------------------------------------------------

# 30. LiteLLM

Use **LiteLLM** as the model provider abstraction.

The application should not directly couple business logic to a specific
LLM provider.

Architecture:

``` text
Nexa Agent
    ↓
LiteLLM
    ↓
Configured model provider
```

Use LiteLLM for:

-   chat completion
-   agent reasoning
-   structured output where appropriate
-   model routing
-   fallback configuration where useful

Keep model/provider configuration outside application source code.

The actual credentials will be supplied separately through environment
variables.

Do not hard-code credentials.

Do not put credentials into source files.

------------------------------------------------------------------------

# 31. Model Routing

Design the code so different Nexa operations can use different model
configurations.

For example:

``` text
Ticket classification → fast/cheap model
Priority detection → fast/cheap model
Knowledge summarization → fast/cheap model
Diagnosis → stronger model
Resolution planning → stronger model
Complex escalation analysis → stronger model
```

Do not assume one model must perform every task.

Create a model configuration abstraction.

------------------------------------------------------------------------

# 32. AI Ticket Investigation Flow

When an employee reports:

> My VPN isn't working.

The backend should perform a flow similar to:

``` text
Employee message
       ↓
Create conversation state
       ↓
AI triage
       ↓
Extract:
  category
  issue type
  urgency
  service
       ↓
Search knowledge
       ↓
Search historical incidents
       ↓
Collect relevant context
       ↓
AI diagnosis
       ↓
Generate evidence
       ↓
Generate resolution plan
       ↓
Determine assignment recommendation
       ↓
Create/update ticket
       ↓
Assign engineer/team
       ↓
Return structured result to UI
```

The response should be structured rather than an unstructured block of
text.

------------------------------------------------------------------------

# 33. Structured AI Output

Use typed schemas.

Example conceptual output:

``` json
{
  "category": "Network",
  "subcategory": "VPN",
  "priority": "P2",
  "summary": "VPN connection failing during authentication",
  "diagnosis": "Possible expired authentication certificate",
  "confidence": 0.86,
  "evidence": [
    "Matching VPN authentication failures in recent incidents",
    "Relevant VPN certificate knowledge article"
  ],
  "resolution_steps": [
    "Check VPN client authentication status",
    "Verify certificate validity",
    "Check authentication logs",
    "Verify gateway connectivity",
    "Test authentication"
  ],
  "recommended_team": "Network"
}
```

Do not expose internal reasoning traces.

------------------------------------------------------------------------

# 34. AI Confidence

Confidence should be used as a decision-support signal.

It must not automatically authorize infrastructure changes.

For example:

``` text
High confidence
Medium confidence
Low confidence
```

If confidence is low, the AI should make uncertainty explicit and
request more information where appropriate.

------------------------------------------------------------------------

# 35. Knowledge Retrieval / RAG

Use:

``` text
Supabase PostgreSQL
+
pgvector
+
Deep Agents
+
LiteLLM
```

Flow:

``` text
Question/problem
      ↓
Embedding
      ↓
pgvector similarity search
      ↓
Relevant knowledge
      ↓
Relevant historical incidents
      ↓
Agent context
      ↓
Diagnosis
```

Chunk knowledge articles appropriately.

Store metadata with embeddings.

Filter by relevant service/category where possible.

------------------------------------------------------------------------

# 36. Redis --- Upstash

Use **Upstash Redis** for transient state and caching.

Potential uses:

-   conversation/session state
-   agent state where appropriate
-   rate limiting
-   short-lived caches
-   background job coordination
-   temporary workflow state

Do not use Redis as the source of truth for tickets.

PostgreSQL remains authoritative.

------------------------------------------------------------------------

# 37. Observability --- OpenTelemetry + Axiom

Use OpenTelemetry for instrumentation.

Send telemetry to **Axiom**.

Instrument:

-   HTTP requests
-   database calls
-   Redis calls
-   AI/LLM calls
-   agent execution
-   ticket creation
-   ticket updates
-   errors
-   important workflow events

Useful metadata:

``` text
request_id
user_id
ticket_id
agent_run_id
operation
model
duration
status
error
```

Do not log:

-   API keys
-   passwords
-   authentication tokens
-   sensitive secrets
-   unnecessary personal data

The application should have structured logs.

------------------------------------------------------------------------

# 38. Environment Configuration

Create a root `.env` file for local development.

Also create:

``` text
.env.example
```

The actual `.env` must contain placeholders only until the developer
provides credentials.

Do NOT put real credentials in source control.

Expected configuration categories:

``` text
SUPABASE_URL
SUPABASE_ANON_KEY
SUPABASE_SERVICE_ROLE_KEY

UPSTASH_REDIS_REST_URL
UPSTASH_REDIS_REST_TOKEN

LITELLM_BASE_URL
LITELLM_API_KEY

AXIOM_DATASET
AXIOM_TOKEN

APP_ENV
BACKEND_URL
FRONTEND_URL
```

Use names appropriate to the actual libraries/configuration after
inspecting their requirements.

Important:

### Never expose server secrets to the browser.

The following must remain backend-only:

``` text
LiteLLM credentials
Upstash secret token
Axiom token
Supabase service-role key
```

Only intentionally public frontend configuration may use
frontend-exposed environment variables.

For Vite, if frontend variables are required, use the appropriate public
prefix and only expose values that are safe to expose.

------------------------------------------------------------------------

# 39. UI Environment Wiring

The existing UI folder must consume environment configuration rather
than hard-coded backend URLs.

For example, conceptually:

``` text
UI
 ↓
PUBLIC/API base URL
 ↓
Backend
```

Do not hard-code:

``` text
http://localhost:8000
```

throughout the UI.

Create a single API client/configuration layer.

Example conceptual structure:

``` text
ui/
  src/
    lib/
      api.ts
      config.ts
```

The exact implementation should match the existing UI framework.

------------------------------------------------------------------------

# 40. API Client

Create a centralized frontend API client.

It should handle:

-   authentication/session
-   tickets
-   conversations
-   comments
-   resolution steps
-   dashboard metrics
-   settings
-   knowledge
-   assignment
-   escalation

Do not scatter raw `fetch()` calls throughout components.

------------------------------------------------------------------------

# 41. API Endpoints

Implement sensible REST endpoints.

Example:

``` text
POST   /api/conversations
POST   /api/conversations/{id}/messages

POST   /api/tickets
GET    /api/tickets
GET    /api/tickets/{id}
PATCH  /api/tickets/{id}

GET    /api/tickets/{id}/analysis

GET    /api/tickets/{id}/steps
POST   /api/tickets/{id}/steps
PATCH  /api/tickets/{id}/steps/{step_id}
DELETE /api/tickets/{id}/steps/{step_id}
POST   /api/tickets/{id}/steps/reorder

POST   /api/tickets/{id}/comments
GET    /api/tickets/{id}/comments

POST   /api/tickets/{id}/escalate
POST   /api/tickets/{id}/resolve
POST   /api/tickets/{id}/reopen

GET    /api/dashboard/engineer
GET    /api/dashboard/employee

GET    /api/settings/ai
PATCH  /api/settings/ai

GET    /api/knowledge
POST   /api/knowledge
PATCH  /api/knowledge/{id}
```

Adjust endpoint names to the existing architecture if needed.

------------------------------------------------------------------------

# 42. Role-Based API Authorization

Every protected endpoint must verify:

1.  authenticated user
2.  user role
3.  resource ownership/access

Examples:

Employee:

``` text
Can view own tickets
Cannot view another employee's private tickets
Cannot modify AI configuration
Cannot modify another user's resolution steps
```

Engineer:

``` text
Can view assigned/team tickets
Can update assigned tickets
Can execute resolution steps
Can escalate
Can resolve
```

Admin:

``` text
Can manage configuration
Can manage users/teams
Can inspect audit history
```

Never rely only on UI hiding.

------------------------------------------------------------------------

# 43. Ticket Assignment

When AI recommends a team:

``` text
AI recommendation
       ↓
Assignment rules
       ↓
Team
       ↓
Available engineer
       ↓
Ticket assignment
```

The system should preserve both:

``` text
AI recommended team
Actual assigned team
```

This helps auditing and future optimization.

------------------------------------------------------------------------

# 44. Dashboard Metrics

Engineer dashboard metrics should be calculated from actual database
state.

Examples:

### Assigned to me

Tickets assigned to current engineer and not resolved/closed.

### Urgent

Tickets with appropriate high priority.

### Due soon

Tickets approaching SLA deadline.

### Needs Your Attention

Tickets requiring immediate engineer action, such as:

-   new assignment
-   waiting for engineer
-   escalation
-   failed/uncertain AI diagnosis
-   pending action
-   SLA risk

Do not hard-code counts.

------------------------------------------------------------------------

# 45. Employee Ticket Experience

Employees should be able to ask:

``` text
What's happening with my ticket?
Who is handling it?
What do you need from me?
Why is it taking time?
```

The backend should retrieve actual ticket state.

Do not let the AI invent ticket status.

Use structured database data as the source of truth.

------------------------------------------------------------------------

# 46. AI Safety / Hallucination Rules

The AI must not invent:

-   ticket status
-   engineer assignment
-   SLA dates
-   completed steps
-   infrastructure changes
-   incidents
-   knowledge articles
-   resolution results

If information is unavailable:

``` text
I don't have enough information to confirm that.
```

AI-generated diagnosis must be distinguishable from confirmed facts.

Example:

``` text
Likely cause:
...

Evidence:
...

Confirmed:
...
```

------------------------------------------------------------------------

# 47. Auditability

Every meaningful state change should be auditable.

Audit events should include:

``` text
who
what
when
ticket
old value
new value
metadata
```

AI events should identify:

``` text
AI-generated
```

Engineer actions should identify:

``` text
Engineer
```

System events should identify:

``` text
System
```

------------------------------------------------------------------------

# 48. Error Handling

Implement proper loading/error/empty states in every screen.

Examples:

``` text
Loading tickets...
Unable to load tickets.
No tickets assigned.
AI investigation in progress...
AI investigation failed. You can continue manually.
```

Do not leave the UI blank on API failure.

------------------------------------------------------------------------

# 49. AI Processing UX

When AI is investigating a ticket, show a concise progress state such
as:

``` text
Understanding request
Finding relevant knowledge
Reviewing similar incidents
Preparing diagnosis
Building resolution plan
```

Do not display hidden chain-of-thought.

This is a UI representation of workflow stages, not internal reasoning.

------------------------------------------------------------------------

# 50. Visual Design Requirements

The existing UI is the source of truth.

Preserve:

-   light theme
-   minimal design
-   professional enterprise SaaS feel
-   whitespace
-   clean typography
-   subtle borders
-   restrained indigo/electric-blue accent
-   calm visual hierarchy

Design inspiration:

``` text
Linear
Vercel
Stripe
Ramp
Notion
modern AI products
```

The landing page can use a more editorial, design-led style inspired by
modern AI startup sites such as GetCrux.

Do not copy another company's branding, text, assets, or exact layout.

------------------------------------------------------------------------

# 51. Avoid These UI Problems

Do NOT introduce:

-   legacy ServiceNow-style dense interfaces
-   excessive cards
-   excessive badges
-   excessive gradients
-   generic AI robot graphics
-   glowing brains
-   giant technical dashboards
-   fake customer logos
-   fake testimonials
-   fake statistics
-   fake certifications
-   fake integrations
-   feature-grid overload
-   unnecessary charts
-   raw AI chain-of-thought
-   token counters
-   model latency dashboards in the main product UI

The product should feel like:

``` text
AI-native enterprise software
```

not:

``` text
old ITSM software with an AI button
```

------------------------------------------------------------------------

# 52. Landing Page

If the existing UI folder contains the landing page, preserve its design
direction.

Core message:

> **IT support that understands the problem before your team touches
> it.**

Supporting statement:

> **AI investigates. Humans resolve.**

The visitor should understand Nexa within approximately 5--10 seconds.

Narrative structure can include:

``` text
Hero
↓
The problem with traditional IT support
↓
How Nexa works
↓
Employee experience
↓
AI investigation
↓
Engineer workspace
↓
Human-in-the-loop execution
↓
Knowledge + historical incidents
↓
Operations
↓
AI configuration
↓
Final CTA
```

Avoid a traditional feature-matrix landing page.

------------------------------------------------------------------------

# 53. Login Page

Use the existing login design if present.

Concept:

``` text
Nexa

Welcome back.

Sign in to your IT workspace.

Work email
[ Continue ]

Continue with Google
Continue with Microsoft

Don't have an account?
Get started
```

Connect this to real authentication.

------------------------------------------------------------------------

# 54. Data Seeding

Create a development seed process.

Seed:

### Teams

``` text
IT Support
Network
Security
Infrastructure
Applications
```

### Users

Create representative development users for:

``` text
Employee
L1 Engineer
L2 Engineer
Admin
```

### Knowledge

Seed realistic IT knowledge articles:

``` text
VPN troubleshooting
Password reset
Email access
Laptop performance
MFA troubleshooting
Wi-Fi connectivity
Certificate expiration
```

### Historical incidents

Seed several resolved incidents that the AI can retrieve during
development.

Use fictional development data.

------------------------------------------------------------------------

# 55. Example Demo Scenario

Make sure this scenario works end-to-end.

Employee enters:

> My VPN isn't working since this morning.

Expected flow:

``` text
Employee AI Assistant
       ↓
AI responds
       ↓
Classifies:
Network / VPN
       ↓
Determines priority
       ↓
Searches knowledge
       ↓
Searches historical incidents
       ↓
Produces diagnosis
       ↓
Produces evidence
       ↓
Produces resolution plan
       ↓
Creates ticket
       ↓
Assigns Network / IT Support
       ↓
Engineer sees ticket
       ↓
Engineer sees AI diagnosis
       ↓
Engineer sees suggested steps
       ↓
Engineer completes steps manually
       ↓
Engineer can modify plan
       ↓
Engineer resolves
       ↓
AI summarizes resolution
       ↓
Employee sees resolution
```

This should be the primary acceptance test.

------------------------------------------------------------------------

# 56. Second Demo Scenario --- Escalation

Employee:

> I cannot access the production deployment system.

Flow:

``` text
Employee
   ↓
AI triage
   ↓
Security/Application classification
   ↓
L1 assignment
   ↓
L1 investigates
   ↓
AI suggests resolution plan
   ↓
L1 performs manual checks
   ↓
Issue requires elevated expertise
   ↓
L1 escalates
   ↓
L2 receives full context
   ↓
L2 continues investigation
   ↓
L2 resolves
```

No information should be lost during escalation.

------------------------------------------------------------------------

# 57. Backend Security

Implement:

-   authentication
-   authorization
-   input validation
-   server-side role checks
-   database constraints
-   safe error responses
-   secret management
-   audit logging
-   rate limiting where appropriate

Never trust:

``` text
role
user_id
ticket ownership
permissions
```

from frontend input.

------------------------------------------------------------------------

# 58. Database Security

Use Supabase Row Level Security where appropriate.

Examples:

Employees:

``` text
Can access their own tickets.
```

Engineers:

``` text
Can access tickets belonging to their permitted teams/assignments.
```

Admins:

``` text
Can access administrative data.
```

Use backend authorization as an additional layer.

------------------------------------------------------------------------

# 59. Performance

Avoid unnecessary database calls.

Use:

-   indexed foreign keys
-   indexes for ticket status/priority/assignment
-   pgvector indexes
-   pagination
-   Redis caching where useful
-   asynchronous AI processing where appropriate

Do not block the entire HTTP request unnecessarily for long-running
agent workflows if the existing architecture supports background
processing.

A ticket can move through:

``` text
triaging
→ diagnosis
→ resolution planning
```

while the UI displays progress.

------------------------------------------------------------------------

# 60. Frontend State

Use the existing UI framework's state approach if reasonable.

Do not introduce a large state-management framework unnecessarily.

Separate:

``` text
server state
UI state
authentication state
conversation state
```

Keep components maintainable.

------------------------------------------------------------------------

# 61. Type Safety

Use typed schemas throughout.

Frontend:

``` text
TypeScript
```

Backend:

Use typed request/response models.

Keep API contracts explicit.

Avoid `any` unless genuinely necessary.

------------------------------------------------------------------------

# 62. Testing

Add tests for important business logic.

Minimum coverage:

### Backend

-   ticket creation
-   ticket assignment
-   priority
-   SLA calculation
-   authorization
-   resolution step updates
-   escalation
-   resolution
-   reopening
-   AI structured output validation

### Frontend

-   login routing
-   employee ticket creation
-   engineer ticket view
-   step completion
-   step editing
-   escalation
-   resolution

### Integration

Test:

``` text
Employee creates ticket
→ AI investigation
→ assignment
→ engineer update
→ resolution
```

------------------------------------------------------------------------

# 63. Observability Acceptance Criteria

Verify that:

-   backend requests generate traces/logs
-   AI calls are observable
-   ticket IDs can be correlated
-   errors are visible
-   secrets are not logged
-   agent runs have useful identifiers

Use OpenTelemetry instrumentation and send telemetry to Axiom.

------------------------------------------------------------------------

# 64. Environment / Deployment Structure

Recommended:

``` text
nexa/
  ui/
  backend/
  supabase/
  .env
  .env.example
  README.md
```

If the existing repository uses a different structure, preserve it
rather than forcing this exact layout.

------------------------------------------------------------------------

# 65. Database Migrations

Do not manually create tables only through the Supabase UI.

Create reproducible migrations.

Include:

-   schema
-   indexes
-   RLS policies
-   vector extension/configuration
-   seed data where appropriate

A fresh environment should be able to recreate the database.

------------------------------------------------------------------------

# 66. README

Create/update the README with:

``` text
Project overview
Architecture
Prerequisites
Environment variables
Local development
Database setup
Migrations
Seed data
Running frontend
Running backend
AI configuration
Observability
Testing
Deployment
```

Do not put actual secrets in README.

------------------------------------------------------------------------

# 67. `.env` Rules

Create:

``` text
.env
.env.example
```

`.env.example` should contain variable names and placeholder values
only.

`.env` should be ignored by Git.

Update `.gitignore` accordingly.

Never commit:

``` text
API keys
service-role keys
Redis tokens
Axiom tokens
LLM provider secrets
```

------------------------------------------------------------------------

# 68. Important LiteLLM Rule

Do not make the frontend call LiteLLM directly if doing so would expose
a secret credential.

The correct flow is:

``` text
Browser
   ↓
Nexa Backend
   ↓
Deep Agents
   ↓
LiteLLM
   ↓
LLM provider
```

The browser should only communicate with Nexa's authenticated API.

------------------------------------------------------------------------

# 69. Important Supabase Rule

The browser may use the appropriate public Supabase client configuration
for authentication/data access where safe and intended.

Never expose:

``` text
SUPABASE_SERVICE_ROLE_KEY
```

to the browser.

Use server-side access for privileged operations.

------------------------------------------------------------------------

# 70. Important Upstash Rule

Upstash credentials are backend-only.

Frontend:

``` text
Browser → Nexa API
```

Backend:

``` text
Nexa API → Upstash
```

Never:

``` text
Browser → Upstash directly
```

with a secret token.

------------------------------------------------------------------------

# 71. Important Axiom Rule

Axiom credentials are backend-only.

The frontend should not directly send telemetry using a secret Axiom
credential.

Preferred:

``` text
Frontend/backend instrumentation
        ↓
appropriate telemetry pipeline
        ↓
Axiom
```

Use OpenTelemetry for standardized instrumentation where practical.

------------------------------------------------------------------------

# 72. Architecture Summary

Final architecture should resemble:

``` text
                         ┌─────────────────────┐
                         │       Nexa UI       │
                         │ React + TypeScript  │
                         └──────────┬──────────┘
                                    │
                                    │ HTTPS
                                    ▼
                         ┌─────────────────────┐
                         │     Nexa Backend    │
                         │      FastAPI        │
                         └──────────┬──────────┘
                                    │
              ┌─────────────────────┼─────────────────────┐
              │                     │                     │
              ▼                     ▼                     ▼
      ┌──────────────┐      ┌──────────────┐      ┌──────────────┐
      │   Supabase   │      │   Upstash    │      │ Deep Agents  │
      │ PostgreSQL   │      │    Redis     │      │              │
      │   pgvector   │      │              │      └──────┬───────┘
      │    Storage   │      └──────────────┘             │
      └──────────────┘                                   ▼
                                                 ┌──────────────┐
                                                 │   LiteLLM    │
                                                 └──────┬───────┘
                                                        │
                                                        ▼
                                                  LLM Providers

                         Observability
                              │
                              ▼
                      OpenTelemetry
                              │
                              ▼
                           Axiom
```

------------------------------------------------------------------------

# 73. Storage

Use Supabase Storage for:

-   knowledge attachments
-   ticket attachments
-   user-uploaded files
-   future documentation files

Do not add S3 for V1 unless a concrete requirement appears.

------------------------------------------------------------------------

# 74. What NOT to Add in V1

Do not introduce unnecessary infrastructure.

Avoid:

``` text
MongoDB
Elasticsearch
OpenSearch
Kafka
Kubernetes
separate vector database
S3
complex event bus
microservice architecture
```

Keep V1 modular but simple.

Preferred:

``` text
React
FastAPI
Supabase
Upstash
Deep Agents
LiteLLM
OpenTelemetry
Axiom
```

------------------------------------------------------------------------

# 75. Product Philosophy

Every implementation decision should follow these principles.

## 1. AI investigates, humans resolve.

## 2. The employee should describe the problem, not fill out a giant form.

## 3. The engineer should receive context, not just a ticket title.

## 4. AI recommendations must be explainable without exposing chain-of-thought.

## 5. Humans remain responsible for production execution in V1.

## 6. Database state is the source of truth.

## 7. AI must not invent system state.

## 8. Progressive disclosure over information overload.

## 9. Show the next useful action, not every possible piece of information.

## 10. Keep the interface calm and modern.

------------------------------------------------------------------------

# 76. Final Implementation Checklist

Before considering the implementation complete, verify:

### UI

-   [ ] Existing UI folder inspected
-   [ ] Existing screens preserved
-   [ ] Employee AI Assistant wired
-   [ ] Engineer Operations Dashboard wired
-   [ ] Engineer Ticket Workspace wired
-   [ ] AI & Automation Settings wired
-   [ ] Login wired
-   [ ] Landing page preserved/improved only where necessary
-   [ ] Loading states implemented
-   [ ] Empty states implemented
-   [ ] Error states implemented
-   [ ] Responsive behavior works

### Authentication

-   [ ] Supabase Auth connected
-   [ ] Session persistence
-   [ ] Role routing
-   [ ] Protected routes
-   [ ] Logout
-   [ ] Server-side authorization

### Database

-   [ ] PostgreSQL schema
-   [ ] Migrations
-   [ ] RLS
-   [ ] Indexes
-   [ ] pgvector
-   [ ] Seed data
-   [ ] Storage buckets

### Tickets

-   [ ] Ticket creation
-   [ ] Ticket listing
-   [ ] Ticket details
-   [ ] Assignment
-   [ ] Priority
-   [ ] SLA
-   [ ] Comments
-   [ ] History
-   [ ] Resolution
-   [ ] Reopening
-   [ ] Escalation

### AI

-   [ ] Deep Agents
-   [ ] LiteLLM
-   [ ] AI triage
-   [ ] AI diagnosis
-   [ ] Knowledge retrieval
-   [ ] Historical incident retrieval
-   [ ] Resolution plan generation
-   [ ] Assignment recommendation
-   [ ] Structured output
-   [ ] No chain-of-thought exposed
-   [ ] No autonomous infrastructure actions

### Engineer workflow

-   [ ] View diagnosis
-   [ ] View evidence
-   [ ] View resolution plan
-   [ ] Complete step
-   [ ] Edit step
-   [ ] Add step
-   [ ] Delete step
-   [ ] Reorder step
-   [ ] Add notes
-   [ ] Escalate
-   [ ] Resolve

### Infrastructure

-   [ ] Supabase
-   [ ] Upstash
-   [ ] LiteLLM
-   [ ] OpenTelemetry
-   [ ] Axiom
-   [ ] Environment configuration
-   [ ] Secrets protected
-   [ ] No credentials committed

### Quality

-   [ ] Backend tests
-   [ ] Frontend tests
-   [ ] Integration tests
-   [ ] Error handling
-   [ ] Logging
-   [ ] Tracing
-   [ ] README
-   [ ] `.env.example`

------------------------------------------------------------------------

# 77. Most Important Acceptance Test

The application is not complete just because all screens render.

The following must work end-to-end:

``` text
Employee logs in
        ↓
Employee describes:
"My VPN isn't working"
        ↓
AI investigates
        ↓
Relevant knowledge is retrieved
        ↓
Historical incidents are considered
        ↓
Diagnosis is generated
        ↓
Evidence is shown
        ↓
Resolution plan is generated
        ↓
Ticket is created
        ↓
Ticket is assigned
        ↓
Engineer sees it on Operations Dispatch
        ↓
Engineer opens ticket
        ↓
Engineer sees diagnosis + evidence + resolution plan
        ↓
Engineer manually performs a step
        ↓
Engineer marks step complete
        ↓
Engineer edits/adds a step
        ↓
Engineer can escalate if required
        ↓
Engineer resolves ticket
        ↓
Resolution is stored
        ↓
Audit history is recorded
        ↓
Employee sees updated status/resolution
```

Implement this path first and use it as the reference workflow for the
rest of the system.

------------------------------------------------------------------------

# 78. Implementation Priority

Work in this order:

``` text
1. Inspect existing repository/UI
2. Establish environment configuration
3. Establish backend
4. Configure Supabase
5. Create migrations/schema
6. Configure authentication
7. Create API layer
8. Implement ticket lifecycle
9. Implement engineer dashboard APIs
10. Implement ticket workspace APIs
11. Implement Deep Agents
12. Integrate LiteLLM
13. Implement knowledge retrieval / pgvector
14. Implement AI diagnosis + resolution plan
15. Wire employee assistant
16. Wire engineer dashboard
17. Wire engineer workspace
18. Wire settings
19. Implement Redis
20. Implement OpenTelemetry + Axiom
21. Add authorization/RLS hardening
22. Add tests
23. Run end-to-end acceptance test
24. Fix UX/integration issues
25. Update README
```

Do not spend the majority of implementation time polishing UI before the
core end-to-end workflow works.

------------------------------------------------------------------------

# 79. Final Instruction

Build this as a **real working product**, not a static prototype.

Use the existing UI folder as the visual reference and wire it to real
backend functionality.

Do not replace working screens simply because a different implementation
is easier.

Do not invent fake API responses once the backend exists.

Do not hard-code ticket data, dashboard metrics, users, AI diagnoses, or
statuses into the UI.

Use:

``` text
Supabase
Upstash
Deep Agents
LiteLLM
OpenTelemetry
Axiom
```

as the core infrastructure described above.

Keep V1 human-in-the-loop.

The AI investigates and recommends.

The human engineer executes and resolves.

Prioritize a clean, maintainable architecture and a working end-to-end
ticket lifecycle over unnecessary infrastructure complexity.
