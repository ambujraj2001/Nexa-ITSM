# Nexa — AI-native IT service management

> **AI investigates. Humans resolve.**

Employees describe a problem in plain language. Nexa's AI classifies it, searches your
knowledge base and resolved-incident history, proposes a diagnosis with evidence, drafts
a resolution plan, and routes the ticket to the right engineer. Engineers execute every
step by hand, escalate to L2 with full context, and resolve. V1 is strictly
human-in-the-loop: the AI never executes infrastructure changes.

```
ui/                      React 19 + TypeScript + Vite + Tailwind (the reference screens, wired up)
  reference/             original static design mockups (visual source of truth)
backend/                 FastAPI + SQLAlchemy (async) + Deep Agents + LiteLLM + OpenTelemetry
  supabase/migrations/   SQL migrations: schema, pgvector, RLS, storage buckets, V1 defaults
```

Each folder is self-contained, with its own dependencies, `.env` and `.gitignore`.

---

## Architecture

```
Browser ──HTTPS──▶ Nexa API (FastAPI) ──▶ Supabase Postgres (+pgvector, RLS)
   │                  │   │   └────────▶ Upstash Redis (rate limits, locks, copilot sessions, caches)
   │                  │   └────────────▶ Deep Agents ──▶ LiteLLM proxy ──▶ model providers
   │                  └────────────────▶ Supabase Auth admin + Storage (service role)
   └── Supabase Auth (anon key, sign-in only)
                                        OpenTelemetry ──OTLP/HTTP──▶ Axiom (traces + logs)
```

* **The browser only talks to the Nexa API** for data. It uses Supabase directly for
  sign-in only, with the public anon key. Service-role, LiteLLM, Upstash and Axiom
  credentials never leave the server; the UI build refuses secret-looking `VITE_*` names.
* **Postgres is the source of truth.** Redis holds transient state only and every
  Redis failure degrades gracefully.
* **Authorization is server-side** (`backend/app/domain/policies.py`), derived from the
  verified Supabase JWT → profile row. RLS on every table mirrors the rules for any direct
  PostgREST access, and clients get read-only, row-scoped access at most.

### The AI investigation pipeline

When a ticket is created, a background job runs these stages. Each stage commits its
name, so the UI shows progress (stages only, never model reasoning):

1. **Understanding**: fast-model triage (category, impact, urgency, signals). Priority
   comes from a deterministic impact × urgency matrix, not the model.
2. **Finding relevant knowledge**: hybrid retrieval (pgvector cosine + Postgres full-text,
   fused with Reciprocal Rank Fusion). It works with full-text only when no embedding
   model is configured.
3. **Reviewing similar incidents**: the same hybrid search over resolved tickets.
4. **Preparing diagnosis**: a strong-model **Deep Agent** with read-only tools
   (`search_knowledge`, `search_historical_incidents`, `get_ticket`, `get_user`,
   `get_asset`, `get_service`, `get_team`, `get_sla_policy`, `recommend_assignment`).
   It returns a typed `DiagnosisReport`. Any evidence reference that the tools never
   returned is dropped, and confidence is capped when that happens.
5. **Building resolution plan**: a second Deep Agent returns a typed `ResolutionPlan`.
   Steps are sanitised so none claims an action was performed, and commands sit in
   `technical_details`, hidden behind "View technical details".
6. **Routing**: assignment rules → service owner → AI-recommended team → service desk,
   then the least-loaded engineer at the right level. The AI-recommended team and the
   actual team are both stored.

If any AI stage fails, the ticket is still routed by rules and shows *"AI investigation
failed. You can continue manually."* Tickets orphaned by a restart are re-queued on
startup.

### Human-in-the-loop guardrails (V1)

| Layer | Enforcement |
| --- | --- |
| Database | `ai_configuration` CHECK constraints: `automatic_actions_enabled = false`, `human_approval_required = true` |
| API | Settings updates that enable automation or disable approval are rejected (`422 policy_violation`) |
| Agent build | `assert_read_only_tools` refuses tools that look like actions (restart/delete/modify/run/execute…) |
| Deep Agents | A harness profile removes the built-in `execute`, filesystem and `task` tools for LiteLLM models |
| Every model/tool call | `HumanExecutionBoundary` middleware allowlists Nexa's tools; hallucinated tool calls are blocked |
| Output | Reasoning-trace markup is stripped; "I restarted X" style claims are rewritten |
| Workflow | Only engineers resolve. The AI drafts resolution summaries and requester updates for a human to approve. |

Ticket facts in the employee assistant (status, assignee, what's needed, SLA) are composed
deterministically from the database. The model never states them.

---

## Prerequisites

* Node.js 20+ and npm
* Python 3.12 and [uv](https://docs.astral.sh/uv/)
* A **Supabase** project (hosted), for Postgres + Auth + Storage
* A **LiteLLM proxy** (or provider keys for the LiteLLM SDK)
* Optional: **Upstash Redis** and **Axiom**

## Environment variables

Each app has its own git-ignored `.env`, copied from the `.env.example` next to it:
`backend/.env` holds everything server-side (including all secrets); `ui/.env` holds only
the three public `VITE_*` values.

| Variable | Where | Purpose |
| --- | --- | --- |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | backend | Auth verification, JWKS |
| `SUPABASE_SERVICE_ROLE_KEY` | backend only | Auth admin (invites, seed), Storage |
| `SUPABASE_DB_URL` | backend only | Postgres connection. Use the **Session pooler** string (port 5432, IPv4) |
| `SUPABASE_JWT_SECRET` | backend only | Only for legacy HS256 projects. Leave empty for asymmetric signing keys |
| `VITE_API_BASE_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` | ui (browser) | Public config only |
| `LITELLM_BASE_URL`, `LITELLM_API_KEY` | backend only | Your LiteLLM proxy. Calls go out as `litellm_proxy/<alias>` |
| `NEXA_MODEL_FAST` | backend | Alias for triage, classification, chat, summaries |
| `NEXA_MODEL_STRONG` | backend | Alias for diagnosis, planning, escalation briefs, copilot |
| `NEXA_MODEL_EMBEDDING` | backend | Embedding alias. Empty means full-text retrieval only |
| `NEXA_MODEL_FALLBACKS`, `NEXA_MODEL_<TASK>` | backend | Optional fallbacks and per-task overrides (`TRIAGE`, `DIAGNOSIS`, `RESOLUTION_PLAN`, `ESCALATION_ANALYSIS`, `ASSISTANT`, `COPILOT`, `SUMMARY`) |
| `UPSTASH_REDIS_REST_URL`, `UPSTASH_REDIS_REST_TOKEN` | backend only | Empty means an in-process store (single instance) |
| `AXIOM_TOKEN`, `AXIOM_DATASET`, `AXIOM_DOMAIN` | backend only | Empty means telemetry isn't exported |
| `SEED_USER_PASSWORD` | backend | Password for demo accounts. Empty means a random one is printed once |

Embeddings are stored as `vector(1536)`. Smaller models are zero-padded, which leaves
cosine similarity unchanged. Larger Matryoshka models (e.g. `text-embedding-3-large`) are
requested at 1536 dimensions.

## Local development

Backend (terminal 1):

```bash
cd backend
uv sync                                            # install dependencies
cp .env.example .env                               # then fill in real values
uv run python -m scripts.migrate                   # apply supabase/migrations to SUPABASE_DB_URL
uv run python -m scripts.seed                      # fictional teams, users, knowledge, resolved incidents
uv run uvicorn app.main:app --reload --port 8000   # http://localhost:8000  (OpenAPI docs at /docs)
```

UI (terminal 2):

```bash
cd ui
npm install
cp .env.example .env                               # public values: API URL, Supabase URL + anon key
npm run dev                                        # http://localhost:5173
```

In Supabase → Authentication → URL configuration, set the **Site URL** to your UI origin
and add `http://localhost:5173/auth/callback` to the redirect URLs. Google and Microsoft
buttons light up automatically when those providers are enabled in Supabase. Email
sign-in supports passwords and magic links. SAML SSO is tried first for the email's
domain when it's configured.

### Database & migrations

* Migrations live in `backend/supabase/migrations/` and are the only way the schema changes.
  They cover extensions, core schema, auth→profile trigger with RLS helpers, RLS
  policies, storage buckets, and V1 defaults (AI config, SLA policies, knowledge sources,
  integration catalogue).
* `uv run python -m scripts.migrate` (from `backend/`) records versions in
  `supabase_migrations.schema_migrations`, the same table the Supabase CLI uses, so
  `npx supabase db push --db-url "$SUPABASE_DB_URL"` (also from `backend/`) works
  interchangeably. Add `--status` to list applied and pending migrations.
* New sign-ups always get the **employee** role. Promote people in
  Settings → Teams & Users (admin), or set the role on their `profiles` row.

### Seed data

`uv run python -m scripts.seed` (from `backend/`) is idempotent. It creates five teams, six services, routing rules, and
eleven fictional people (`@example.com`, never deliverable): an admin, L1/L2 engineers
across Network, IT Support, Applications, Security and Infrastructure, and three
employees. It also adds nine knowledge articles (VPN, certificates, passwords, MFA,
email, laptops, Wi-Fi, production access) and eight resolved historical incidents,
indexed for retrieval. Add `--demo-queue` to also file open tickets through the live AI
pipeline.

### Demo logins

| Role | Email | Password |
| --- | --- | --- |
| Employee | `elena.rostova@example.com` | `Nexa-2v0XhNqra0XMm7!9` |
| Engineer (L1 Network) | `rahul.sharma@example.com` | `Nexa-2v0XhNqra0XMm7!9` |
| Admin | `jordan.blake@example.com` | `Nexa-2v0XhNqra0XMm7!9` |
| Engineer (L1 IT Support) | `engineer@example.com` | `engineer` |
| Admin | `admin@example.com` | `admin1` |

The seeded demo accounts share one password; `engineer@example.com` and `admin@example.com` have their own.

Sign in as `elena.rostova@example.com` (employee) to try the assistant,
`rahul.sharma@example.com` (L1 Network) for dispatch, `daniel.okafor@example.com` (L2
Network) for escalations, and `jordan.blake@example.com` for admin settings.

## AI configuration

* **Model routing** is per task (`backend/app/config.py: TASK_TIERS`). Fast tier: triage,
  assistant, summaries. Strong tier: diagnosis, resolution planning, escalation analysis,
  copilot. Override any task with `NEXA_MODEL_<TASK>`.
* **Structured output**: direct calls use JSON-schema response formats with Pydantic
  validation and one repair attempt, falling back to JSON mode. Deep Agents use
  LangChain's `ToolStrategy`, so it works with any tool-calling model behind the proxy.
* **Settings → AI & Automation** (admin) toggles triage, diagnosis and plans, and sets the
  confidence threshold. Diagnoses below it are flagged "AI unsure" on the dashboard.
  Confidence never authorises anything.
* **Fallbacks**: configure them on the LiteLLM proxy (recommended) or via
  `NEXA_MODEL_FALLBACKS` for direct calls.

## Observability

OpenTelemetry traces and logs go to Axiom over OTLP/HTTP (`/v1/traces`, `/v1/logs`) with
`X-Axiom-Dataset`. The following are instrumented:

* HTTP requests (FastAPI), SQL (SQLAlchemy), and outbound HTTP (httpx). The httpx layer
  covers Supabase, the LiteLLM proxy and Upstash REST.
* `ticket.create`, `ticket.update`, `ticket.escalate`, `ticket.resolve`,
  `investigation.run`, `agent.run`, `agent.tool`, `llm.call`, `ai.structured_completion`,
  `ai.embedding`, `knowledge.search` and `redis.command`.
* Correlation attributes: `request_id`, `enduser.id`, `nexa.ticket_id`,
  `nexa.agent_run_id`, `gen_ai.request.model`, duration, status and error type.
* Every agent run is also recorded in `agent_runs`, with ids, model, status, tool-call
  count, tokens and duration.

**Never recorded:** prompts, completions, message bodies, credentials. Logs are
structured JSON, and a redaction pass removes JWTs, bearer tokens, API keys and DSN
passwords. LiteLLM message logging is off. Set `OTEL_CONSOLE_EXPORT=true` to print spans
locally.

## Testing

```bash
cd backend && uv run pytest -q     # unit tests always; integration tests need SUPABASE_DB_URL (or TEST_DATABASE_URL)
cd ui && npm test                  # Vitest + Testing Library
cd ui && npm run build             # type-check + production build
```

* **Backend unit tests** cover priority, SLA, lifecycle, routing rules, authorization
  policy, JWT verification (HS256 + ES256/JWKS), redaction, retrieval helpers, model
  routing, and AI guardrails. The guardrail tests run real Deep Agents graphs to prove
  that only Nexa's read-only tools reach the model and that a hallucinated `execute` call
  is blocked.
* **Backend integration tests** run the full VPN acceptance scenario (spec §77):
  assistant → proposal → ticket → investigation → assignment → step edits → requester
  question/answer → L2 escalation with handoff → resolution → employee confirmation. They
  also cover authorization, the V1 policy (API and DB constraint), AI-failure fallback,
  and hybrid search. They use deterministic fake models and run inside a transaction
  that is rolled back, so nothing persists.
* **Frontend tests** cover role-based login routing, employee ticket creation, the
  engineer ticket view, step completion and editing, escalation and resolution.

## Deployment

* **Backend**: `uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 2` behind
  HTTPS. Set `APP_ENV=production`, `FRONTEND_URL` / `CORS_ORIGINS`, and the backend-only
  secrets. AI jobs run in-process as asyncio tasks. Stuck investigations are recovered on
  startup, and a Redis lock ensures one run per ticket across workers. Configure Upstash
  so rate limits and locks are shared across instances.
* **Frontend**: `cd ui && npm run build` → static `ui/dist/`. Serve it with an SPA fallback to
  `index.html`, and build with the production `VITE_*` values.
* **Supabase**: run migrations against the production database, set the Auth Site URL and
  redirect URLs, and enable the OAuth/SAML providers you need.

## V1 scope notes

* SLA timers are calendar time (24×7). Business-hours calendars are a later addition.
* Integrations are modelled (`integrations` table, provider registry). Supabase Auth is
  live, and Slack, email, monitoring webhooks and asset sync report "not configured"
  until their connectors ship.
* Resolved tickets aren't auto-closed. The employee confirms ("Yes, it's fixed"), or an
  engineer closes them.
