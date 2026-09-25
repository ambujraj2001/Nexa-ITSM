/**
 * Engineer Ticket Workspace (reference: engineer_ticket_workspace_calm_focused).
 * User problem → AI diagnosis → suggested next steps (engineer executes) → activity.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router";
import { useToast } from "@/components/Toast";
import { ErrorState, Icon, LoadingState, PriorityChip, Spinner, StatusChip } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { TicketDetail } from "@/lib/types";
import { ActivityTabs } from "./ActivityTabs";
import { CopilotDrawer, EscalateModal, PriorityModal, ReassignModal, ResolveModal } from "./Panels";
import { DiagnosisSection, EscalationBanner, ResolutionBlock, UserProblem } from "./Sections";
import { StepsSection } from "./StepsSection";

const LIST_FOR_TYPE: Record<string, { label: string; to: string }> = {
  incident: { label: "Incidents", to: "/tickets/incidents" },
  service_request: { label: "Requests", to: "/tickets/requests" },
  change: { label: "Changes", to: "/tickets/changes" },
  problem: { label: "Problems", to: "/tickets/incidents" },
};

function MoreMenu({ ticket, onPriority, onReassign }: { ticket: TicketDetail; onPriority: () => void; onReassign: () => void }) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);
  const canWork = ticket.permissions.can_work;
  if (!canWork && !ticket.permissions.can_reassign) return null;
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex h-8 items-center rounded px-2 text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface" aria-label="More actions">
        <Icon name="more_horiz" className="text-[18px]" />
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-1 w-48 overflow-hidden rounded-md border border-outline-variant/40 bg-surface-container-lowest shadow-lg" role="menu">
          {canWork && (
            <button type="button" role="menuitem" onClick={() => { setOpen(false); onPriority(); }} className="flex w-full items-center gap-space-sm px-space-md py-2 text-left font-body-sm text-body-sm text-on-surface hover:bg-surface-container-low">
              <Icon name="flag" className="text-[16px]" /> Change priority
            </button>
          )}
          {ticket.permissions.can_reassign && (
            <button type="button" role="menuitem" onClick={() => { setOpen(false); onReassign(); }} className="flex w-full items-center gap-space-sm px-space-md py-2 text-left font-body-sm text-body-sm text-on-surface hover:bg-surface-container-low">
              <Icon name="swap_horiz" className="text-[16px]" /> Reassign
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function Workspace({ ticket }: { ticket: TicketDetail }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [copilot, setCopilot] = useState(false);
  const [escalating, setEscalating] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [reassigning, setReassigning] = useState(false);
  const [prioritizing, setPrioritizing] = useState(false);
  const [replyDraft, setReplyDraft] = useState<string | null>(null);
  const clearDraft = useCallback(() => setReplyDraft(null), []);

  const refresh = (t?: TicketDetail) => {
    if (t && t.view === "engineer") queryClient.setQueryData(["ticket", ticket.id], t);
    void queryClient.invalidateQueries({ queryKey: ["ticket", ticket.id] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    void queryClient.invalidateQueries({ queryKey: ["tickets"] });
  };
  const take = useMutation({ mutationFn: () => api.tickets.assignToMe(ticket.id), onSuccess: (t) => { refresh(t); toast(`${t.ticket_number} is now assigned to you`); }, onError: (e) => toast(errorMessage(e), "error") });
  const reopen = useMutation({ mutationFn: () => api.tickets.reopen(ticket.id, "Reopened by engineer for follow-up."), onSuccess: (t) => { refresh(t as TicketDetail); toast("Ticket reopened"); }, onError: (e) => toast(errorMessage(e), "error") });

  const p = ticket.permissions;
  const list = LIST_FOR_TYPE[ticket.ticket_type] ?? LIST_FOR_TYPE.incident;
  const noun = ticket.ticket_type === "incident" ? "Incident" : ticket.ticket_type === "change" ? "Change" : "Request";
  const done = ticket.status === "resolved" || ticket.status === "closed";
  const assignedLine = ticket.assignee ? (
    <>Assigned to <span className="font-medium text-on-surface">{ticket.assignee.name}</span> ({[ticket.assignee.engineer_level, ticket.team?.name].filter(Boolean).join(" ")})</>
  ) : (
    <>Unassigned{ticket.team ? ` · ${ticket.team.name} queue` : ""}</>
  );

  return (
    <div className="flex w-full flex-col">
      <div className="w-full bg-surface-container-lowest px-gutter py-space-md shadow-[0_1px_3px_rgba(0,0,0,0.02)]">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-space-lg">
          <div className="flex min-w-0 items-center gap-space-md">
            <div className="flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
              <Link to={list.to} className="transition-colors hover:text-on-surface">{list.label}</Link>
              <Icon name="chevron_right" className="text-[14px]" />
              <span className="font-label-code text-label-code font-medium text-on-surface">{ticket.ticket_number}</span>
            </div>
            <span className="h-1 w-1 rounded-full bg-outline-variant" />
            <div className="flex items-center gap-space-xs">
              <PriorityChip priority={ticket.priority} />
              <StatusChip status={ticket.status} label={ticket.status_label} />
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-space-sm">
            {p.can_escalate && (
              <button type="button" onClick={() => setEscalating(true)} className="flex h-8 items-center gap-1.5 rounded px-3 font-body-sm text-body-sm font-medium text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface">
                <Icon name="share" className="text-[16px]" /><span>Escalate</span>
              </button>
            )}
            <button type="button" onClick={() => setCopilot(true)} className="flex h-8 items-center gap-1.5 rounded bg-secondary-fixed px-3 font-body-sm text-body-sm font-medium text-on-secondary-fixed-variant transition-colors hover:bg-secondary hover:text-on-secondary">
              <Icon name="auto_awesome" className="text-[16px]" /><span>Ask AI</span>
            </button>
            {p.can_self_assign && !p.can_work && (
              <button type="button" disabled={take.isPending} onClick={() => take.mutate()} className="flex h-8 items-center gap-1.5 rounded bg-primary px-4 font-body-sm text-body-sm font-medium text-on-primary shadow-sm transition-colors hover:bg-primary-container">
                {take.isPending ? <Spinner className="border-t-white" /> : <Icon name="person_add" className="text-[16px]" />}<span>Assign to me</span>
              </button>
            )}
            {p.can_resolve && (
              <button type="button" onClick={() => setResolving(true)} className="flex h-8 items-center gap-1.5 rounded bg-primary px-4 font-body-sm text-body-sm font-medium text-on-primary shadow-sm transition-colors hover:bg-primary-container">
                <Icon name="check_circle" className="text-[16px]" /><span>Resolve {noun}</span>
              </button>
            )}
            {done && p.can_reopen && (
              <button type="button" disabled={reopen.isPending} onClick={() => reopen.mutate()} className="flex h-8 items-center gap-1.5 rounded px-3 font-body-sm text-body-sm font-medium text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface">
                <Icon name="undo" className="text-[16px]" /><span>Reopen</span>
              </button>
            )}
            <MoreMenu ticket={ticket} onPriority={() => setPrioritizing(true)} onReassign={() => setReassigning(true)} />
          </div>
        </div>
      </div>

      <div className="mx-auto flex w-full max-w-4xl flex-col gap-space-xl px-gutter py-space-xl">
        <div className="flex flex-col gap-1 pb-space-xs">
          <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">{ticket.title}</h1>
          <p className="flex flex-wrap items-center gap-x-space-xs font-body-sm text-body-sm text-on-surface-variant">
            <span>{assignedLine}</span>
            {ticket.service && <span>· {ticket.service.name}</span>}
            {!done && <span>· SLA {ticket.sla.label}</span>}
            {ticket.category && <span>· {[ticket.category, ticket.subcategory].filter(Boolean).join(" / ")}</span>}
          </p>
          {!p.can_work && !done && (
            <p className="mt-1 font-body-sm text-body-sm text-outline">
              {p.can_self_assign ? "Assign this ticket to yourself to work the plan." : "View only — this ticket is assigned to someone else."}
            </p>
          )}
        </div>

        <EscalationBanner ticket={ticket} />
        <UserProblem ticket={ticket} />
        <DiagnosisSection ticket={ticket} />
        <ResolutionBlock ticket={ticket} />
        <StepsSection ticket={ticket} />
        <ActivityTabs ticket={ticket} replyDraft={replyDraft} onDraftUsed={clearDraft} />
      </div>

      <CopilotDrawer ticket={ticket} open={copilot} onClose={() => setCopilot(false)} onUseDraft={(text) => { setReplyDraft(text); setCopilot(false); }} />
      <EscalateModal ticket={ticket} open={escalating} onClose={() => setEscalating(false)} onDone={(t) => { setEscalating(false); refresh(t); }} />
      <ResolveModal ticket={ticket} open={resolving} onClose={() => setResolving(false)} onDone={(t) => { setResolving(false); refresh(t); }} />
      <ReassignModal ticket={ticket} open={reassigning} onClose={() => setReassigning(false)} onDone={(t) => { setReassigning(false); refresh(t); }} />
      <PriorityModal ticket={ticket} open={prioritizing} onClose={() => setPrioritizing(false)} onDone={(t) => { setPrioritizing(false); refresh(t); }} />
    </div>
  );
}

export function TicketWorkspacePage() {
  const { ticketId = "" } = useParams();
  const query = useQuery({ queryKey: ["ticket", ticketId], queryFn: () => api.tickets.get(ticketId), refetchInterval: 30_000 });
  if (query.isLoading) return <LoadingState label="Loading ticket…" className="py-24" />;
  if (query.isError || !query.data)
    return (
      <div className="mx-auto max-w-xl px-gutter py-space-xl">
        <ErrorState title="Unable to load this ticket." message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
      </div>
    );
  if (query.data.view !== "engineer") {
    return (
      <div className="mx-auto max-w-xl px-gutter py-space-xl">
        <ErrorState title="This is your own request" message="Open it from My Tickets to see its status." />
      </div>
    );
  }
  return <Workspace ticket={query.data} />;
}
