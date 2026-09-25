/**
 * Engineer Operations Dispatch (reference: engineer_operations_dashboard_calm_focused).
 * Hierarchy: context → 3 metrics → Needs Your Attention (dominant) → My Tickets.
 * Every number is a live query; nothing is hard-coded.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router";
import { useToast } from "@/components/Toast";
import { EmptyState, ErrorState, Icon, LoadingState, PriorityDot, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { slaTone } from "@/lib/format";
import type { AttentionItem, Priority, TicketSummary } from "@/lib/types";

const FILTERS = [
  { key: "all", label: "All" },
  { key: "urgent", label: "Urgent" },
  { key: "waiting-me", label: "Waiting on Me" },
  { key: "waiting-user", label: "Waiting on User" },
] as const;
type FilterKey = (typeof FILTERS)[number]["key"];

const PRIORITY_TEXT: Record<Priority, string> = { P1: "P1 Urgent", P2: "P2 High", P3: "P3 Normal", P4: "P4 Low" };

function iconFor(ticket: TicketSummary): { icon: string; tone: string } {
  if (ticket.priority === "P1") return { icon: "crisis_alert", tone: "bg-error-container text-error" };
  const sub = `${ticket.category ?? ""} ${ticket.subcategory ?? ""}`.toLowerCase();
  const tone = ticket.priority === "P2" ? "bg-secondary-fixed text-on-secondary-fixed-variant" : "bg-surface-container-high text-on-surface-variant";
  if (sub.includes("vpn")) return { icon: "vpn_key", tone };
  if (sub.includes("wi-fi") || sub.includes("network")) return { icon: "wifi", tone };
  if (sub.includes("email") || sub.includes("calendar")) return { icon: "mark_email_read", tone };
  if (sub.includes("mfa") || sub.includes("password") || sub.includes("access")) return { icon: "key", tone };
  if (sub.includes("security")) return { icon: "shield", tone };
  if (sub.includes("hardware") || sub.includes("laptop")) return { icon: "laptop_mac", tone };
  if (sub.includes("infrastructure") || sub.includes("deployment")) return { icon: "dns", tone };
  return { icon: "confirmation_number", tone };
}

function slaClass(ticket: TicketSummary): string {
  const tone = slaTone(ticket.sla);
  return tone === "error" ? "text-error" : tone === "accent" ? "text-secondary" : "text-on-surface-variant";
}

function statusTone(ticket: TicketSummary): string {
  if (ticket.status === "pending_engineer" || ticket.status === "reopened" || ticket.sla.state === "breached") return "bg-error-container text-on-error-container";
  if (ticket.status === "in_progress" || ticket.status === "escalated") return "bg-secondary-fixed text-on-secondary-fixed";
  return "bg-surface-container-high text-on-surface-variant";
}

function matches(filter: FilterKey, t: TicketSummary): boolean {
  if (filter === "urgent") return t.priority === "P1" || t.priority === "P2" || t.sla.state === "breached";
  if (filter === "waiting-me") return t.status !== "pending_user";
  if (filter === "waiting-user") return t.status === "pending_user";
  return true;
}

function Metric({ label, value, sub, tone }: { label: string; value: number; sub: string; tone: "default" | "error" | "accent" }) {
  const color = tone === "error" ? "text-error" : tone === "accent" ? "text-secondary" : "text-on-surface";
  return (
    <div className="flex min-w-[120px] flex-col justify-center rounded-xl bg-surface-container-lowest px-space-lg py-space-sm shadow-sm">
      <span className={clsx("font-label-caps text-label-caps uppercase", tone === "default" ? "text-on-surface-variant" : color)}>{label}</span>
      <div className="mt-0.5 flex items-baseline gap-space-xs">
        <span className={clsx("font-display-lg text-display-lg font-semibold tracking-tight", color)}>{value}</span>
        <span className={clsx("font-label-code text-label-code", tone === "error" ? "text-error" : "text-on-surface-variant")}>{sub}</span>
      </div>
    </div>
  );
}

function AttentionCard({ item }: { item: AttentionItem }) {
  const t = item.ticket;
  const { icon, tone } = iconFor(t);
  const aiIcon = item.ai.kind === "failed" ? "error" : item.ai.kind === "running" ? "hourglass_top" : item.ai.kind === "plan_ready" ? "task_alt" : "auto_awesome";
  const aiTone = item.ai.kind === "failed" ? "text-error" : item.ai.kind === "plan_ready" ? "text-on-tertiary-container" : "text-secondary";
  return (
    <div className="group relative flex flex-col justify-between gap-space-lg rounded-xl bg-surface-container-lowest p-space-lg shadow-sm transition-all hover:shadow-md md:flex-row md:items-center">
      <div className="flex min-w-0 items-start gap-space-md">
        <div className={clsx("mt-0.5 flex h-10 w-10 flex-shrink-0 flex-col items-center justify-center rounded-xl", tone)}>
          <Icon name={icon} className="text-[20px]" />
        </div>
        <div className="flex min-w-0 flex-col gap-space-xs">
          <div className="flex flex-wrap items-center gap-space-sm font-label-code text-label-code">
            <span className="font-semibold text-on-surface">{t.ticket_number}</span>
            <span className="h-1 w-1 rounded-full bg-outline-variant" />
            <span className={clsx("flex items-center gap-1 rounded px-1.5 py-0.5 font-medium", t.priority === "P1" ? "bg-error-container text-on-error-container" : t.priority === "P2" ? "bg-secondary-fixed text-on-secondary-fixed" : "bg-surface-container-high text-on-surface")}>
              <span className={clsx("h-1.5 w-1.5 rounded-full", t.priority === "P1" ? "bg-error" : t.priority === "P2" ? "bg-secondary" : "bg-outline")} />
              {PRIORITY_TEXT[t.priority]}
            </span>
            <span className="h-1 w-1 rounded-full bg-outline-variant" />
            <span className={clsx("flex items-center gap-1 font-medium", slaClass(t))}>
              {(t.sla.state === "breached" || t.sla.state === "due_soon") && <Icon name="timer" className="text-[14px]" />}
              SLA: {t.sla.label}
            </span>
            {item.reasons
              .filter((r) => !r.code.startsWith("sla") && r.code !== "p1")
              .map((r) => (
                <span key={r.code} className="rounded bg-surface-container-low px-1.5 py-0.5 text-on-surface-variant">{r.label}</span>
              ))}
          </div>
          <h2 className="truncate font-headline-sm text-headline-sm font-medium text-on-surface">{t.title}</h2>
          <div className="mt-0.5 flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
            <Icon name={aiIcon} className={clsx("text-[15px]", aiTone)} />
            <span>
              {item.ai.label} {item.ai.text && <span className="font-medium text-on-surface">{item.ai.text}</span>}
            </span>
          </div>
        </div>
      </div>
      <div className="flex flex-shrink-0 items-center gap-space-sm self-end md:self-center">
        <Link to={`/tickets/${t.id}`} className="flex items-center gap-space-xs rounded bg-primary px-space-md py-1.5 font-body-sm text-body-sm font-medium text-on-primary shadow-sm transition-colors hover:bg-primary-container">
          <span>{item.action_label}</span>
          <Icon name="arrow_forward" className="text-[16px]" />
        </Link>
      </div>
    </div>
  );
}

function TeamQueue({ tickets }: { tickets: TicketSummary[] }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const take = useMutation({
    mutationFn: (id: string) => api.tickets.assignToMe(id),
    onSuccess: (t) => {
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast(`${t.ticket_number} is now yours`);
      navigate(`/tickets/${t.id}`);
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  if (tickets.length === 0) return null;
  return (
    <div className="flex flex-col gap-space-md pt-space-md">
      <div className="flex items-center gap-space-xs">
        <span className="font-headline-sm text-headline-sm font-semibold text-on-surface">Team queue</span>
        <span className="pl-space-xs font-body-sm text-body-sm text-on-surface-variant">Unassigned in your team</span>
      </div>
      <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm">
        {tickets.map((t) => (
          <div key={t.id} className="flex items-center gap-space-md border-b border-surface-container-low px-space-lg py-space-md last:border-b-0">
            <PriorityDot priority={t.priority} />
            <span className="w-24 font-label-code text-label-code font-medium text-on-surface">{t.ticket_number}</span>
            <span className="flex-1 truncate font-body-md text-body-md text-on-surface">{t.title}</span>
            <span className={clsx("hidden font-label-code text-label-code sm:inline", slaClass(t))}>{t.sla.label}</span>
            <button type="button" className="btn-ghost h-7 px-2.5" disabled={take.isPending} onClick={() => take.mutate(t.id)}>
              {take.isPending && take.variables === t.id ? <Spinner /> : "Assign to me"}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}

export function DispatchPage() {
  const [filter, setFilter] = useState<FilterKey>("all");
  const navigate = useNavigate();
  const query = useQuery({ queryKey: ["dashboard", "engineer"], queryFn: api.dashboard.engineer, refetchInterval: 30_000 });
  const rows = useMemo(() => (query.data?.my_tickets ?? []).filter((t) => matches(filter, t)), [query.data, filter]);

  if (query.isLoading) return <LoadingState label="Loading dispatch…" className="py-24" />;
  if (query.isError || !query.data)
    return (
      <div className="mx-auto max-w-xl px-gutter py-space-xl">
        <ErrorState title="Unable to load tickets." message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
      </div>
    );
  const d = query.data;
  return (
    <div className="flex w-full flex-col">
      <div className="mx-auto flex w-full max-w-7xl flex-col gap-space-xl px-space-lg py-space-xl">
        <div className="flex flex-col justify-between gap-space-lg pb-space-lg md:flex-row md:items-end">
          <div className="flex flex-col gap-space-xs">
            <div className="flex items-center gap-space-xs font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant">
              <span className="h-2 w-2 rounded-full bg-secondary" />
              <span>{d.shift_label}</span>
            </div>
            <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">Operations Dispatch</h1>
            <p className="font-body-md text-body-md text-on-surface-variant">Triage queue aligned by immediate operational urgency.</p>
          </div>
          <div className="flex flex-wrap items-stretch gap-space-md">
            <Metric label="Assigned to Me" value={d.metrics.assigned_to_me} sub="open" tone="default" />
            <Metric label="Urgent" value={d.metrics.urgent} sub={d.metrics.urgent_at_risk > 0 ? `${d.metrics.urgent_at_risk} breach risk` : "P1–P2"} tone="error" />
            <Metric label="Due Soon" value={d.metrics.due_soon} sub="< 1 hour" tone="accent" />
          </div>
        </div>

        <div className="flex flex-col gap-space-md">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-space-sm">
              <span className="font-headline-sm text-headline-sm font-semibold text-on-surface">Needs Your Attention</span>
              <span className={clsx("rounded-full px-space-xs py-0.5 font-label-code text-label-code", d.needs_attention.length ? "bg-error-container text-on-error-container" : "bg-surface-container-high text-on-surface-variant")}>
                {d.needs_attention.length} Actionable
              </span>
            </div>
            <span className="font-body-sm text-body-sm text-on-surface-variant">What should I work on next?</span>
          </div>
          {d.needs_attention.length === 0 ? (
            <div className="rounded-xl bg-surface-container-lowest shadow-sm">
              <EmptyState icon="task_alt" title="Nothing needs your attention right now." message="New assignments, requester replies, escalations and SLA risks will appear here." />
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-space-md">
              {d.needs_attention.map((item) => (
                <AttentionCard key={item.ticket.id} item={item} />
              ))}
            </div>
          )}
        </div>

        <div className="flex flex-col gap-space-md pt-space-md">
          <div className="flex flex-col justify-between gap-space-sm sm:flex-row sm:items-center">
            <div className="flex items-center gap-space-xs">
              <span className="font-headline-sm text-headline-sm font-semibold text-on-surface">My Tickets</span>
              <span className="pl-space-xs font-body-sm text-body-sm text-on-surface-variant">{d.my_tickets.length} open</span>
            </div>
            <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-low p-1 font-body-sm text-body-sm" role="tablist">
              {FILTERS.map((f) => (
                <button key={f.key} type="button" role="tab" aria-selected={filter === f.key} onClick={() => setFilter(f.key)} className={clsx("rounded px-space-md py-1 transition-colors", filter === f.key ? "bg-surface-container-lowest font-medium text-on-surface shadow-sm" : "text-on-surface-variant hover:text-on-surface")}>
                  {f.label}
                </button>
              ))}
            </div>
          </div>
          <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm">
            {rows.length === 0 ? (
              <EmptyState icon="inbox" title="No tickets assigned." message={filter === "all" ? "Tickets routed to you will appear here." : "Nothing matches this filter."} />
            ) : (
              <div className="w-full overflow-x-auto">
                <table className="w-full border-collapse text-left">
                  <thead>
                    <tr className="bg-surface-container-low/60 font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant">
                      <th className="w-28 px-space-lg py-space-md">Priority</th>
                      <th className="w-32 px-space-md py-space-md">ID</th>
                      <th className="min-w-[320px] px-space-md py-space-md">Summary</th>
                      <th className="w-48 px-space-md py-space-md">Requester</th>
                      <th className="w-36 px-space-md py-space-md">SLA</th>
                      <th className="w-36 px-space-lg py-space-md text-right">Status</th>
                    </tr>
                  </thead>
                  <tbody className="font-body-md text-body-md text-on-surface">
                    {rows.map((t) => (
                      <tr key={t.id} className="group cursor-pointer transition-colors hover:bg-surface-container-low" onClick={() => navigate(`/tickets/${t.id}`)}>
                        <td className="whitespace-nowrap px-space-lg py-space-lg"><PriorityDot priority={t.priority} /></td>
                        <td className="whitespace-nowrap px-space-md py-space-lg font-label-code text-label-code font-medium text-on-surface">
                          <Link to={`/tickets/${t.id}`} onClick={(e) => e.stopPropagation()}>{t.ticket_number}</Link>
                        </td>
                        <td className="px-space-md py-space-lg">
                          <div className="flex flex-col">
                            <span className="font-medium text-on-surface transition-colors group-hover:text-primary">{t.title}</span>
                            <span className="max-w-lg truncate font-body-sm text-body-sm text-on-surface-variant">{t.ai_headline ?? t.summary ?? [t.category, t.subcategory].filter(Boolean).join(" / ")}</span>
                          </div>
                        </td>
                        <td className="whitespace-nowrap px-space-md py-space-lg font-body-sm text-body-sm text-on-surface-variant">
                          {t.requester.name}
                          {t.requester.department ? ` (${t.requester.department})` : ""}
                        </td>
                        <td className="whitespace-nowrap px-space-md py-space-lg">
                          <span className={clsx("font-label-code text-label-code font-medium", slaClass(t))}>{t.sla.label}</span>
                        </td>
                        <td className="whitespace-nowrap px-space-lg py-space-lg text-right">
                          <span className={clsx("rounded px-2 py-0.5 font-label-code text-label-code", statusTone(t))}>{t.status_label}</span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </div>

        <TeamQueue tickets={d.team_queue} />
      </div>
    </div>
  );
}
