/**
 * AI & Automation (reference: ai_automation_settings_clean_settings_layout).
 * V1 guardrails are shown locked because the server (and a database
 * constraint) enforce them — the UI can't switch on autonomous execution.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { useToast } from "@/components/Toast";
import { ErrorState, Icon, LoadingState, Spinner, Toggle } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { relative } from "@/lib/format";
import type { AiSettings } from "@/lib/types";
import { SettingsHeader } from "./SettingsLayout";

type Draft = Pick<AiSettings, "ai_triage_enabled" | "ai_diagnosis_enabled" | "resolution_plans_enabled" | "confidence_threshold">;

function ToggleRow({ title, description, checked, onChange, disabled }: { title: string; description: string; checked: boolean; onChange?: (v: boolean) => void; disabled?: boolean }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-surface-container-lowest p-space-lg shadow-sm transition-shadow hover:shadow">
      <div className="flex max-w-lg flex-col pr-space-md">
        <span className="font-headline-sm text-headline-sm font-medium text-on-surface">{title}</span>
        <span className="mt-0.5 font-body-md text-body-md text-on-surface-variant">{description}</span>
      </div>
      <Toggle checked={checked} onChange={onChange} disabled={disabled} label={title} />
    </div>
  );
}

function LockedRow({ title, description, checked, note }: { title: string; description: string; checked: boolean; note: string }) {
  return (
    <div className="flex items-center justify-between rounded-xl bg-surface-container-low/60 p-space-lg opacity-90 shadow-sm">
      <div className="flex max-w-lg flex-col pr-space-md">
        <div className="flex flex-wrap items-center gap-space-xs">
          <span className="font-headline-sm text-headline-sm font-medium text-on-surface">{title}</span>
          <span className="inline-flex items-center rounded bg-surface-container-highest px-2 py-0.5 font-label-code text-[10px] font-medium text-on-surface-variant">Enforced Policy</span>
        </div>
        <span className="mt-0.5 font-body-md text-body-md text-on-surface-variant">{description}</span>
        <div className="mt-2 flex items-center gap-1.5 font-body-sm text-[11px] text-on-surface-variant">
          <Icon name="lock" className="text-[14px] text-error" />
          <span>{note}</span>
        </div>
      </div>
      <Toggle checked={checked} disabled label={title} />
    </div>
  );
}

function Accordion({ icon, title, subtitle, children }: { icon: string; title: string; subtitle: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm transition-all duration-200">
      <button type="button" onClick={() => setOpen((v) => !v)} aria-expanded={open} className="flex w-full items-center justify-between p-space-lg text-left transition-colors hover:bg-surface-container-low">
        <div className="flex items-center gap-space-md">
          <Icon name={icon} className="text-[20px] text-secondary" />
          <div className="flex flex-col">
            <span className="font-headline-sm text-headline-sm font-medium text-on-surface">{title}</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant">{subtitle}</span>
          </div>
        </div>
        <Icon name="expand_more" className={clsx("text-[20px] text-on-surface-variant transition-transform duration-200", open && "rotate-180")} />
      </button>
      {open && <div className="flex flex-col gap-space-md px-space-lg pb-space-lg pt-space-xs">{children}</div>}
    </div>
  );
}

function Row({ title, detail, chip, chipTone = "active", action }: { title: string; detail: ReactNode; chip?: string; chipTone?: "active" | "standby" | "off"; action?: ReactNode }) {
  return (
    <div className="flex items-center justify-between gap-space-md rounded-lg bg-surface-container-low p-space-md">
      <div className="flex min-w-0 flex-col">
        <span className="font-body-md text-body-md font-medium text-on-surface">{title}</span>
        <span className="font-body-sm text-body-sm text-on-surface-variant">{detail}</span>
      </div>
      <div className="flex shrink-0 items-center gap-space-sm">
        {chip && (
          <span className={clsx("rounded px-2 py-0.5 font-label-code text-label-code", chipTone === "active" ? "bg-surface-container-highest text-on-surface" : chipTone === "standby" ? "bg-surface-container text-on-surface-variant" : "bg-surface-container text-outline")}>{chip}</span>
        )}
        {action}
      </div>
    </div>
  );
}

export function AiSettingsPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const query = useQuery({ queryKey: ["settings", "ai"], queryFn: api.settings.ai });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false, staleTime: 60_000 });
  const [draft, setDraft] = useState<Draft | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    if (query.data && !draft) {
      const { ai_triage_enabled, ai_diagnosis_enabled, resolution_plans_enabled, confidence_threshold } = query.data;
      setDraft({ ai_triage_enabled, ai_diagnosis_enabled, resolution_plans_enabled, confidence_threshold });
    }
  }, [query.data, draft]);

  const dirty = useMemo(() => {
    if (!query.data || !draft) return false;
    return (Object.keys(draft) as (keyof Draft)[]).some((k) => draft[k] !== query.data[k]);
  }, [query.data, draft]);

  const save = useMutation({
    mutationFn: () => api.settings.updateAi(draft!),
    onSuccess: (s) => {
      queryClient.setQueryData(["settings", "ai"], s);
      setDraft(null);
      setSavedAt(Date.now());
      toast("AI settings saved");
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const reindex = useMutation({ mutationFn: api.settings.reindex, onSuccess: (r) => toast(`Re-indexing ${r.articles} articles and ${r.incidents} incidents`), onError: (e) => toast(errorMessage(e), "error") });
  const toggleSource = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) => api.settings.updateKnowledgeSource(id, enabled),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["settings", "ai"] }),
    onError: (e) => toast(errorMessage(e), "error"),
  });

  useEffect(() => {
    if (!savedAt) return;
    const id = window.setTimeout(() => setSavedAt(null), 2500);
    return () => window.clearTimeout(id);
  }, [savedAt]);

  if (query.isLoading || (query.data && !draft)) return <LoadingState label="Loading settings…" />;
  if (query.isError || !query.data || !draft) return <ErrorState title="Unable to load AI settings." message={errorMessage(query.error)} onRetry={() => void query.refetch()} />;
  const s = query.data;
  const editable = s.can_edit;
  const set = <K extends keyof Draft>(k: K, v: Draft[K]) => setDraft((d) => (d ? { ...d, [k]: v } : d));
  const m = s.models;
  const pct = Math.round(draft.confidence_threshold * 100);

  return (
    <main className="flex w-full flex-col pb-space-xl">
      <SettingsHeader
        eyebrow={`Human-in-the-loop${health.data ? ` • Nexa ${health.data.version}` : ""}`}
        title="AI & Automation"
        description="Configure AI triage, diagnostic boundaries, and the safeguard policies that keep engineers in control."
      />
      <div className="flex flex-col gap-space-xl">
        <div className="flex items-center gap-space-md rounded-xl border border-outline-variant/30 bg-surface-container-low p-space-md text-on-surface">
          <Icon name="verified_user" className="shrink-0 text-[20px] text-secondary" />
          <div className="flex flex-col">
            <span className="font-headline-sm text-headline-sm font-medium">V1 Autonomous Guardrails</span>
            <p className="mt-0.5 font-body-sm text-body-sm text-on-surface-variant">AI analyzes reports and drafts resolution steps. Human engineers review and execute all infrastructure remediations.</p>
          </div>
        </div>

        {!editable && <p className="rounded-lg bg-surface-container-low px-space-md py-2 font-body-sm text-body-sm text-on-surface-variant">View only — workspace admins can change these settings.</p>}
        {!m.configured && <p className="rounded-lg bg-error-container px-space-md py-2 font-body-sm text-body-sm text-on-error-container">No AI model is configured. Set NEXA_MODEL_FAST / NEXA_MODEL_STRONG (and LITELLM_BASE_URL) — until then tickets are routed by rules only.</p>}

        <section className="flex flex-col gap-space-md">
          <div className="pb-space-xs">
            <h3 className="font-headline-md text-headline-md font-semibold text-on-surface">Core Governance</h3>
            <p className="font-body-md text-body-md text-on-surface-variant">Configure primary triage pipelines, diagnostic boundaries, and safety policies.</p>
          </div>
          <div className="flex flex-col gap-space-sm">
            <ToggleRow title="AI Triage" description="Automatically categorize incoming tickets, assess incident priority, and assign initial routing tags." checked={draft.ai_triage_enabled} onChange={(v) => set("ai_triage_enabled", v)} disabled={!editable} />
            <ToggleRow title="AI Diagnosis" description="Correlate knowledge articles and historical resolutions to identify probable root causes." checked={draft.ai_diagnosis_enabled} onChange={(v) => set("ai_diagnosis_enabled", v)} disabled={!editable} />
            <ToggleRow title="Resolution Plans" description="Generate step-by-step diagnostic checklists and remediation plans for responding engineers." checked={draft.resolution_plans_enabled} onChange={(v) => set("resolution_plans_enabled", v)} disabled={!editable} />
            <LockedRow title="Automatic Infrastructure Actions" description="Execute commands or scripts directly in production without manual verification." checked={s.automatic_actions_enabled} note="Human execution required in V1. Policy locked by the platform." />
            <LockedRow title="Human Approval Required" description="Require explicit engineer confirmation before applying suggested workarounds or closing incidents." checked={s.human_approval_required} note="Required in V1 — only engineers resolve tickets." />
          </div>
        </section>

        <section className="flex flex-col gap-space-md pt-space-sm">
          <div className="pb-space-xs">
            <h3 className="font-headline-md text-headline-md font-semibold text-on-surface">Advanced Configuration</h3>
            <p className="font-body-md text-body-md text-on-surface-variant">Models, knowledge sources, confidence limits, and connectors.</p>
          </div>
          <div className="flex flex-col gap-space-sm">
            <Accordion icon="memory" title="Model configuration" subtitle={`Routed through ${m.gateway === "litellm_proxy" ? "your LiteLLM proxy" : "the LiteLLM SDK"} · set in the server environment`}>
              <Row title="Fast tier" detail={`Triage, priority, chat, summaries · ${m.fast_model ?? "not configured"}`} chip={m.fast_model ? "Active" : "Not set"} chipTone={m.fast_model ? "active" : "off"} />
              <Row title="Strong tier" detail={`Diagnosis, resolution planning, escalation briefs, copilot · ${m.strong_model ?? "falls back to fast tier"}`} chip={m.strong_model ? "Active" : "Fallback"} chipTone={m.strong_model ? "active" : "standby"} />
              <Row title="Embeddings" detail={m.embedding_model ? `${m.embedding_model} · semantic + full-text retrieval` : "Not configured — full-text retrieval only"} chip={m.embedding_model ? "Active" : "Off"} chipTone={m.embedding_model ? "active" : "off"} />
              <Row title="Secondary failover" detail={m.fallback_models.length ? m.fallback_models.join(", ") : "None (configure fallbacks on the proxy or NEXA_MODEL_FALLBACKS)"} chip={m.fallback_models.length ? "Standby" : undefined} chipTone="standby" />
            </Accordion>
            <Accordion icon="database" title="Knowledge & RAG sources" subtitle="Knowledge base articles and resolved incident history">
              {s.knowledge_sources.map((k) => (
                <Row
                  key={k.id}
                  title={k.name}
                  detail={`${k.item_count} item${k.item_count === 1 ? "" : "s"} · ${k.indexed_count} indexed${k.last_indexed_at ? ` · ${relative(k.last_indexed_at)}` : ""}`}
                  action={<Toggle checked={k.enabled} disabled={!editable || toggleSource.isPending} onChange={(v) => toggleSource.mutate({ id: k.id, enabled: v })} label={`${k.name} enabled`} />}
                />
              ))}
              {editable && (
                <button type="button" className="btn-ghost h-8 self-start px-3" disabled={reindex.isPending} onClick={() => reindex.mutate()}>
                  {reindex.isPending ? <Spinner /> : <Icon name="sync" className="text-[16px]" />} Re-index missing items
                </button>
              )}
            </Accordion>
            <Accordion icon="tune" title="Confidence thresholds" subtitle="Diagnoses below this confidence are flagged as uncertain">
              <div className="flex flex-col gap-space-sm rounded-lg bg-surface-container-low p-space-md">
                <div className="flex items-center justify-between">
                  <label htmlFor="threshold-range" className="font-body-md text-body-md font-medium text-on-surface">Diagnosis Confidence Floor</label>
                  <span className="rounded bg-surface-container px-2 py-0.5 font-label-code text-label-code font-semibold text-on-surface">{pct}%</span>
                </div>
                <input id="threshold-range" type="range" min={50} max={98} value={pct} disabled={!editable} onChange={(e) => set("confidence_threshold", Number(e.target.value) / 100)} className="h-1.5 w-full cursor-pointer appearance-none rounded-lg bg-surface-container accent-primary" />
                <div className="flex justify-between font-label-code text-[10px] text-on-surface-variant">
                  <span>50% (Permissive)</span>
                  <span>80% (Recommended)</span>
                  <span>98% (Strict)</span>
                </div>
                <p className="font-body-sm text-body-sm text-on-surface-variant">Confidence is a decision-support signal only — it never authorises changes.</p>
              </div>
            </Accordion>
            <Accordion icon="extension" title="Integrations" subtitle="Notification channels, monitoring and identity">
              {s.integrations.map((i) => (
                <Row
                  key={i.id}
                  title={i.display_name}
                  detail={i.status_detail ?? i.description ?? ""}
                  chip={i.status === "connected" ? "Connected" : i.available ? "Not configured" : "Later release"}
                  chipTone={i.status === "connected" ? "active" : "off"}
                />
              ))}
            </Accordion>
          </div>
        </section>

        {editable && (
          <div className="sticky bottom-4 z-20 mt-space-lg flex items-center justify-between rounded-xl bg-surface-container-lowest p-space-md shadow-xl">
            <div className="flex items-center gap-space-sm px-space-xs">
              <div className={clsx("h-2 w-2 rounded-full transition-colors", dirty ? "bg-secondary" : savedAt ? "bg-on-tertiary-container" : "bg-surface-container-highest")} />
              <span className={clsx("font-body-sm text-body-sm", dirty ? "font-medium text-on-surface" : "text-on-surface-variant")}>
                {dirty ? "Unsaved changes" : savedAt ? "Changes saved successfully" : "All settings up to date"}
              </span>
            </div>
            <div className="flex items-center gap-space-sm">
              {dirty && (
                <button type="button" className="rounded-lg px-space-md py-2 font-body-sm text-body-sm text-on-surface-variant transition-colors hover:bg-surface-container-low" onClick={() => setDraft(null)}>
                  Discard
                </button>
              )}
              <button type="button" disabled={!dirty || save.isPending} onClick={() => save.mutate()} className="flex items-center gap-space-xs rounded-lg bg-primary px-space-lg py-2 font-body-sm text-body-sm font-medium text-on-primary shadow-sm transition-all hover:bg-inverse-surface disabled:opacity-60">
                {save.isPending ? <Spinner className="border-t-white" /> : <span>Save Changes</span>}
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
