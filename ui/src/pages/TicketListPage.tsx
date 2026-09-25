/** Engineer ticket lists: My Tickets, Incidents, Requests, Changes. */
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { EmptyState, ErrorState, Icon, LoadingState, PriorityDot } from "@/components/ui";
import { api, errorMessage, type TicketListQuery } from "@/lib/api";
import { relative, slaTone } from "@/lib/format";
import type { Priority, TicketType } from "@/lib/types";

const CONFIG: Record<string, { title: string; subtitle: string; type?: TicketType; scope?: TicketListQuery["scope"] }> = {
  mine: { title: "My Tickets", subtitle: "Everything assigned to you.", scope: "assigned" },
  incidents: { title: "Incidents", subtitle: "Something is broken or degraded.", type: "incident" },
  requests: { title: "Requests", subtitle: "Access, hardware and software requests.", type: "service_request" },
  changes: { title: "Changes", subtitle: "Planned changes to services and infrastructure.", type: "change" },
};

export function TicketListPage({ kind }: { kind: keyof typeof CONFIG }) {
  const { me } = useAuth();
  const cfg = CONFIG[kind];
  const navigate = useNavigate();
  const [scope, setScope] = useState<TicketListQuery["scope"]>(cfg.scope ?? (me?.role === "admin" ? "visible" : "team"));
  const [openOnly, setOpenOnly] = useState(true);
  const [priority, setPriority] = useState<Priority | "">("");
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  useEffect(() => {
    const id = window.setTimeout(() => setSearch(q.trim()), 250);
    return () => window.clearTimeout(id);
  }, [q]);
  useEffect(() => {
    setScope(cfg.scope ?? (me?.role === "admin" ? "visible" : "team"));
    setPage(0);
  }, [kind, cfg.scope, me?.role]);
  const limit = 25;
  const query = useQuery({
    queryKey: ["tickets", kind, scope, openOnly, priority, search, page],
    queryFn: () => api.tickets.list({ scope, ticket_type: cfg.type, open_only: openOnly, priority: priority || undefined, q: search || undefined, sort: openOnly ? "sla" : "updated", limit, offset: page * limit }),
    placeholderData: (prev) => prev,
  });
  const scopes: { key: NonNullable<TicketListQuery["scope"]>; label: string }[] = cfg.scope
    ? []
    : [
        { key: "team", label: "My team" },
        { key: "assigned", label: "Assigned to me" },
        { key: "visible", label: me?.role === "admin" ? "All" : "All I can see" },
      ];

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-space-lg px-space-lg py-space-xl">
      <div className="flex flex-col gap-space-xs">
        <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">{cfg.title}</h1>
        <p className="font-body-md text-body-md text-on-surface-variant">{cfg.subtitle}</p>
      </div>
      <div className="flex flex-wrap items-center gap-space-sm">
        {scopes.length > 0 && (
          <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-low p-1 font-body-sm text-body-sm">
            {scopes.map((s) => (
              <button key={s.key} type="button" onClick={() => { setScope(s.key); setPage(0); }} className={clsx("rounded px-space-md py-1", scope === s.key ? "bg-surface-container-lowest font-medium text-on-surface shadow-sm" : "text-on-surface-variant hover:text-on-surface")}>
                {s.label}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-low p-1 font-body-sm text-body-sm">
          {[true, false].map((v) => (
            <button key={String(v)} type="button" onClick={() => { setOpenOnly(v); setPage(0); }} className={clsx("rounded px-space-md py-1", openOnly === v ? "bg-surface-container-lowest font-medium text-on-surface shadow-sm" : "text-on-surface-variant hover:text-on-surface")}>
              {v ? "Open" : "All statuses"}
            </button>
          ))}
        </div>
        <select aria-label="Priority" className="input h-8 w-36" value={priority} onChange={(e) => { setPriority(e.target.value as Priority | ""); setPage(0); }}>
          <option value="">Any priority</option>
          {["P1", "P2", "P3", "P4"].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <div className="relative ml-auto w-full sm:w-72">
          <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-[16px] text-on-surface-variant" />
          <input className="input h-8 pl-8" placeholder="Search number, title or text" value={q} onChange={(e) => { setQ(e.target.value); setPage(0); }} aria-label="Search tickets" />
        </div>
      </div>

      <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm">
        {query.isLoading && <LoadingState label="Loading tickets…" />}
        {query.isError && <ErrorState className="shadow-none" title="Unable to load tickets." message={errorMessage(query.error)} onRetry={() => void query.refetch()} />}
        {query.data && query.data.items.length === 0 && <EmptyState title="No tickets found" message={search ? "Try a different search." : "Nothing matches these filters."} />}
        {query.data && query.data.items.length > 0 && (
          <div className="w-full overflow-x-auto">
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-surface-container-low/60 font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant">
                  <th className="w-24 px-space-lg py-space-md">Priority</th>
                  <th className="w-32 px-space-md py-space-md">ID</th>
                  <th className="min-w-[280px] px-space-md py-space-md">Summary</th>
                  <th className="w-44 px-space-md py-space-md">Assignee</th>
                  <th className="w-44 px-space-md py-space-md">Requester</th>
                  <th className="w-32 px-space-md py-space-md">SLA</th>
                  <th className="w-36 px-space-lg py-space-md text-right">Status</th>
                </tr>
              </thead>
              <tbody className="font-body-md text-body-md">
                {query.data.items.map((t) => {
                  const tone = slaTone(t.sla);
                  return (
                    <tr key={t.id} className="group cursor-pointer transition-colors hover:bg-surface-container-low" onClick={() => navigate(`/tickets/${t.id}`)}>
                      <td className="px-space-lg py-space-md"><PriorityDot priority={t.priority} /></td>
                      <td className="px-space-md py-space-md font-label-code text-label-code font-medium text-on-surface">{t.ticket_number}</td>
                      <td className="px-space-md py-space-md">
                        <div className="flex flex-col">
                          <span className="font-medium text-on-surface">{t.title}</span>
                          <span className="max-w-lg truncate font-body-sm text-body-sm text-on-surface-variant">{[t.category, t.subcategory].filter(Boolean).join(" / ") || "Uncategorised"} · updated {relative(t.updated_at)}</span>
                        </div>
                      </td>
                      <td className="px-space-md py-space-md font-body-sm text-body-sm text-on-surface-variant">{t.assignee?.name ?? (t.team ? `${t.team.name} queue` : "—")}</td>
                      <td className="px-space-md py-space-md font-body-sm text-body-sm text-on-surface-variant">{t.requester.name}</td>
                      <td className={clsx("px-space-md py-space-md font-label-code text-label-code", tone === "error" ? "text-error" : tone === "accent" ? "text-secondary" : "text-on-surface-variant")}>{t.sla.label}</td>
                      <td className="px-space-lg py-space-md text-right">
                        <span className="rounded bg-surface-container-high px-2 py-0.5 font-label-code text-label-code text-on-surface-variant">{t.status_label}</span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
      {query.data && query.data.total > limit && (
        <div className="flex items-center justify-between font-body-sm text-body-sm text-on-surface-variant">
          <span>{page * limit + 1}–{Math.min((page + 1) * limit, query.data.total)} of {query.data.total}</span>
          <div className="flex gap-space-xs">
            <button type="button" className="btn-ghost h-8 px-3" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</button>
            <button type="button" className="btn-ghost h-8 px-3" disabled={(page + 1) * limit >= query.data.total} onClick={() => setPage((p) => p + 1)}>Next</button>
          </div>
        </div>
      )}
    </div>
  );
}
