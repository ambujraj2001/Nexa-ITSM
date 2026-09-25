/** Employee: "My Tickets" list and ticket detail (status, people, progress, messages, resolution). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useState } from "react";
import { Link, useParams } from "react-router";
import { InvestigationProgress } from "@/components/InvestigationProgress";
import { useToast } from "@/components/Toast";
import { Avatar, EmptyState, ErrorState, Icon, LoadingState, Modal, PriorityChip, Spinner, StatusChip } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { relative, shortDate } from "@/lib/format";
import type { EmployeeTicketDetail, TicketDetail } from "@/lib/types";

const TABS = [
  { key: "open", label: "Open" },
  { key: "resolved", label: "Resolved" },
  { key: "all", label: "All" },
] as const;

export function MyTicketsPage() {
  const [tab, setTab] = useState<(typeof TABS)[number]["key"]>("open");
  const query = useQuery({
    queryKey: ["tickets", "requested", tab],
    queryFn: () =>
      api.tickets.list({ scope: "requested", open_only: tab === "open", status: tab === "resolved" ? ["resolved", "closed"] : undefined, sort: "updated", limit: 50 }),
  });
  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-space-lg px-gutter py-space-xl">
      <div className="flex flex-col justify-between gap-space-md sm:flex-row sm:items-end">
        <div>
          <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">My Tickets</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">Everything you've asked IT for, and where it stands.</p>
        </div>
        <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-low p-1 font-body-sm text-body-sm">
          {TABS.map((t) => (
            <button key={t.key} type="button" onClick={() => setTab(t.key)} className={clsx("rounded px-space-md py-1 transition-colors", tab === t.key ? "bg-surface-container-lowest font-medium text-on-surface shadow-sm" : "text-on-surface-variant hover:text-on-surface")}>
              {t.label}
            </button>
          ))}
        </div>
      </div>
      {query.isLoading && <LoadingState label="Loading tickets…" />}
      {query.isError && <ErrorState title="Unable to load tickets." message={errorMessage(query.error)} onRetry={() => void query.refetch()} />}
      {query.data && query.data.items.length === 0 && (
        <EmptyState
          icon="inbox"
          title={tab === "open" ? "No open tickets" : "Nothing here yet"}
          message="When you report an issue through the assistant, it shows up here."
          action={<Link to="/assistant" className="btn-primary mt-space-sm h-9 px-4">Open the assistant</Link>}
        />
      )}
      <div className="flex flex-col gap-space-sm">
        {query.data?.items.map((t) => (
          <Link key={t.id} to={`/my-tickets/${t.id}`} className="flex flex-col gap-1 rounded-xl bg-surface-container-lowest px-space-lg py-space-md shadow-sm transition-shadow hover:shadow-md">
            <div className="flex flex-wrap items-center gap-space-sm">
              <span className="font-label-code text-label-code font-semibold text-on-surface">{t.ticket_number}</span>
              <span className="font-headline-sm text-headline-sm font-medium text-on-surface">{t.title}</span>
              <StatusChip status={t.status} label={t.status_label} />
            </div>
            <div className="flex flex-wrap items-center gap-x-space-md font-body-sm text-body-sm text-on-surface-variant">
              <span>{t.assignee ? `${t.assignee.name}${t.team ? ` · ${t.team.name}` : ""}` : t.team ? `${t.team.name} queue` : "Being routed"}</span>
              {t.steps_total > 0 && <span>{t.steps_done} of {t.steps_total} steps done</span>}
              <span>Updated {relative(t.updated_at)}</span>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}

function ReopenModal({ open, onClose, onSubmit, busy }: { open: boolean; onClose: () => void; onSubmit: (reason: string) => void; busy: boolean }) {
  const [reason, setReason] = useState("");
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Still having issues?"
      footer={
        <>
          <button type="button" className="btn-ghost h-8 px-3" onClick={onClose}>Cancel</button>
          <button type="button" className="btn-primary h-8 px-4" disabled={reason.trim().length < 3 || busy} onClick={() => onSubmit(reason.trim())}>
            {busy ? <Spinner className="border-t-white" /> : "Reopen ticket"}
          </button>
        </>
      }
    >
      <textarea className="input h-28 resize-none py-2" placeholder="What's still not working?" value={reason} onChange={(e) => setReason(e.target.value)} aria-label="What's still not working?" />
    </Modal>
  );
}

function EmployeeTicketView({ ticket }: { ticket: EmployeeTicketDetail }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [reply, setReply] = useState("");
  const [reopenOpen, setReopenOpen] = useState(false);
  const comments = useQuery({ queryKey: ["ticket", ticket.id, "comments"], queryFn: () => api.tickets.comments.list(ticket.id) });
  const activity = useQuery({ queryKey: ["ticket", ticket.id, "activity"], queryFn: () => api.tickets.activity(ticket.id) });
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["ticket", ticket.id] });
    void queryClient.invalidateQueries({ queryKey: ["tickets"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const send = useMutation({
    mutationFn: () => api.tickets.comments.add(ticket.id, { content: reply.trim() }),
    onSuccess: () => {
      setReply("");
      refresh();
      toast("Message sent to the IT team");
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const close = useMutation({ mutationFn: () => api.tickets.close(ticket.id), onSuccess: () => { refresh(); toast("Thanks for confirming — ticket closed"); }, onError: (e) => toast(errorMessage(e), "error") });
  const reopen = useMutation({
    mutationFn: (reason: string) => api.tickets.reopen(ticket.id, reason),
    onSuccess: () => { setReopenOpen(false); refresh(); toast("Ticket reopened — the engineer has been notified"); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const investigating = ticket.ai_status === "pending" || ticket.ai_status === "running";
  const question = [...(comments.data ?? [])].reverse().find((c) => c.kind === "question");

  return (
    <div className="mx-auto flex w-full max-w-4xl flex-col gap-space-xl px-gutter py-space-xl">
      <div className="flex flex-col gap-space-xs">
        <Link to="/my-tickets" className="inline-flex items-center gap-1 font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface">
          <Icon name="arrow_back" className="text-[16px]" /> My Tickets
        </Link>
        <div className="flex flex-wrap items-center gap-space-sm">
          <span className="font-label-code text-label-code font-semibold text-on-surface">{ticket.ticket_number}</span>
          <PriorityChip priority={ticket.priority} compact />
          <StatusChip status={ticket.status} label={ticket.status_label} />
        </div>
        <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">{ticket.title}</h1>
        <p className="font-body-sm text-body-sm text-on-surface-variant">Reported {shortDate(ticket.created_at)} · Updated {relative(ticket.updated_at)}</p>
      </div>

      {ticket.waiting_on === "you" && (
        <section className="flex flex-col gap-space-sm rounded-xl border border-error-container bg-surface-container-lowest p-space-lg shadow-sm">
          <div className="flex items-center gap-space-xs font-headline-sm text-headline-sm text-on-surface">
            <Icon name="priority_high" className="text-[18px] text-error" /> The engineer needs something from you
          </div>
          {question && <p className="font-body-lg text-body-lg text-on-surface">“{question.content}”</p>}
          <p className="font-body-sm text-body-sm text-on-surface-variant">Reply below — it goes straight to {ticket.assignee?.name ?? "the IT team"}.</p>
        </section>
      )}

      <section className="grid grid-cols-1 gap-space-md md:grid-cols-2">
        <div className="flex flex-col gap-space-sm rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <span className="label-caps text-on-surface-variant">Who's handling it</span>
          {investigating ? (
            <InvestigationProgress ticketId={ticket.id} typeLabel={ticket.type_label} />
          ) : ticket.assignee ? (
            <div className="flex items-center gap-space-sm">
              <Avatar name={ticket.assignee.name} url={ticket.assignee.avatar_url} />
              <div className="flex flex-col">
                <span className="font-body-md text-body-md font-medium text-on-surface">{ticket.assignee.name}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{[ticket.team?.name, ticket.assignee.engineer_level].filter(Boolean).join(" · ")}</span>
              </div>
            </div>
          ) : (
            <p className="font-body-md text-body-md text-on-surface">{ticket.team ? `In the ${ticket.team.name} queue — an engineer will pick it up.` : "Being routed to the right team."}</p>
          )}
          {!investigating && ticket.status !== "resolved" && ticket.status !== "closed" && (
            <p className="font-body-sm text-body-sm text-on-surface-variant">{ticket.waiting_on === "you" ? "Waiting on your reply." : "Nothing is needed from you right now."}</p>
          )}
        </div>
        <div className="flex flex-col gap-space-sm rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <span className="label-caps text-on-surface-variant">What we think is happening</span>
          {ticket.likely_cause ? (
            <>
              <p className="font-body-md text-body-md text-on-surface">{ticket.likely_cause}</p>
              <p className="font-body-sm text-body-sm text-outline">Likely cause from the AI investigation — the engineer confirms it.</p>
            </>
          ) : (
            <p className="font-body-md text-body-md text-on-surface-variant">{investigating ? "Nexa is still looking into it." : "The engineer will update you as they investigate."}</p>
          )}
        </div>
      </section>

      {ticket.resolution && (
        <section className="flex flex-col gap-space-md rounded-xl bg-surface-container-lowest p-space-lg shadow-sm">
          <div className="flex items-center gap-space-xs">
            <Icon name="task_alt" className="text-[20px] text-on-tertiary-container" />
            <h2 className="font-headline-sm text-headline-sm font-semibold text-on-surface">Resolved</h2>
            {ticket.resolution.resolved_at && <span className="font-body-sm text-body-sm text-on-surface-variant">· {shortDate(ticket.resolution.resolved_at)}{ticket.resolution.resolved_by ? ` by ${ticket.resolution.resolved_by.name}` : ""}</span>}
          </div>
          <p className="font-body-lg text-body-lg text-on-surface">{ticket.resolution.summary}</p>
          {ticket.resolution.completed_steps.length > 0 && (
            <ul className="flex flex-col gap-1">
              {ticket.resolution.completed_steps.map((s) => (
                <li key={s} className="flex items-center gap-space-xs font-body-md text-body-md text-on-surface-variant">
                  <Icon name="check" className="text-[16px] text-on-tertiary-container" /> {s}
                </li>
              ))}
            </ul>
          )}
          {(ticket.permissions.can_close || ticket.permissions.can_reopen) && (
            <div className="flex flex-wrap items-center gap-space-sm pt-space-xs">
              {ticket.permissions.can_close && (
                <button type="button" className="btn-primary h-8 px-4" disabled={close.isPending} onClick={() => close.mutate()}>
                  {close.isPending ? <Spinner className="border-t-white" /> : <Icon name="thumb_up" className="text-[15px]" />} Yes, it's fixed
                </button>
              )}
              {ticket.permissions.can_reopen && (
                <button type="button" className="btn-ghost h-8 px-3" onClick={() => setReopenOpen(true)}>
                  Still having issues
                </button>
              )}
            </div>
          )}
        </section>
      )}

      {ticket.steps_total > 0 && !ticket.resolution && (
        <section className="flex flex-col gap-space-sm">
          <div className="flex items-baseline justify-between border-b border-surface-container-high pb-2">
            <h2 className="font-headline-sm text-headline-sm font-semibold text-on-surface">Progress</h2>
            <span className="font-label-code text-[11px] text-on-surface-variant">{ticket.steps_done} of {ticket.steps_total} done</span>
          </div>
          <ul className="flex flex-col gap-1">
            {ticket.steps.map((s) => (
              <li key={s.id} className="flex items-center gap-space-md p-space-sm">
                <Icon name={s.status === "completed" ? "check_box" : "check_box_outline_blank"} filled={s.status === "completed"} className={clsx("text-[20px]", s.status === "completed" ? "text-secondary" : "text-outline")} />
                <span className={clsx("font-body-md text-body-md", s.status === "completed" ? "text-on-surface-variant line-through" : "text-on-surface")}>{s.description}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-space-md">
        <h2 className="font-headline-sm text-headline-sm font-semibold text-on-surface">Messages</h2>
        {comments.isLoading && <LoadingState label="Loading messages…" />}
        {comments.isError && <ErrorState title="Unable to load messages." onRetry={() => void comments.refetch()} />}
        {comments.data?.length === 0 && <p className="font-body-md text-body-md text-on-surface-variant">No messages yet.</p>}
        <div className="flex flex-col gap-space-sm">
          {comments.data?.map((c) => (
            <div key={c.id} className="flex flex-col gap-1 rounded-xl bg-surface-container-lowest px-space-lg py-space-md shadow-sm">
              <div className="flex items-center gap-space-xs font-body-sm text-body-sm">
                <span className="font-medium text-on-surface">{c.author_label}</span>
                <span className="text-on-surface-variant">· {shortDate(c.created_at)}</span>
                {c.kind === "question" && <span className="chip bg-error-container text-on-error-container">Question for you</span>}
                {c.kind === "resolution" && <span className="chip bg-tertiary-fixed/40 text-on-tertiary-fixed-variant">Resolution</span>}
              </div>
              <p className="whitespace-pre-line font-body-md text-body-md text-on-surface">{c.content}</p>
            </div>
          ))}
        </div>
        {ticket.permissions.can_reply && (
          <form
            className="flex flex-col gap-space-sm"
            onSubmit={(e) => {
              e.preventDefault();
              if (reply.trim()) send.mutate();
            }}
          >
            <textarea className="input h-24 resize-none py-2" placeholder="Send a message to the IT team…" value={reply} onChange={(e) => setReply(e.target.value)} aria-label="Message to the IT team" />
            <button type="submit" className="btn-primary h-8 self-end px-4" disabled={!reply.trim() || send.isPending}>
              {send.isPending ? <Spinner className="border-t-white" /> : "Send"}
            </button>
          </form>
        )}
      </section>

      <section className="flex flex-col gap-space-sm">
        <h2 className="label-caps text-on-surface-variant">Activity</h2>
        {activity.data?.map((a) => (
          <div key={a.id} className="flex items-baseline gap-space-md font-body-sm text-body-sm">
            <span className="w-28 shrink-0 font-label-code text-[11px] text-outline">{shortDate(a.at)}</span>
            <span className={clsx("font-medium", a.actor_type === "ai" ? "text-secondary" : "text-on-surface")}>{a.actor_label}</span>
            <span className="text-on-surface-variant">{a.summary}</span>
          </div>
        ))}
      </section>

      <ReopenModal open={reopenOpen} onClose={() => setReopenOpen(false)} onSubmit={(r) => reopen.mutate(r)} busy={reopen.isPending} />
    </div>
  );
}

export function EmployeeTicketPage() {
  const { ticketId = "" } = useParams();
  const query = useQuery({ queryKey: ["ticket", ticketId], queryFn: () => api.tickets.get(ticketId), refetchInterval: 20_000 });
  if (query.isLoading) return <LoadingState label="Loading ticket…" className="py-24" />;
  if (query.isError || !query.data)
    return (
      <div className="mx-auto max-w-xl px-gutter py-space-xl">
        <ErrorState title="Unable to load this ticket." message={errorMessage(query.error)} onRetry={() => void query.refetch()} />
      </div>
    );
  const data = query.data;
  if (data.view === "engineer") {
    // Staff reporting their own issue still see the requester view here.
    const t = data as TicketDetail;
    return (
      <div className="mx-auto max-w-4xl px-gutter py-space-xl">
        <p className="font-body-md text-body-md text-on-surface-variant">
          You have IT staff access to {t.ticket_number}. <Link className="font-medium text-on-surface underline" to={`/tickets/${t.id}`}>Open the engineer workspace</Link>.
        </p>
      </div>
    );
  }
  return <EmployeeTicketView ticket={data} />;
}
