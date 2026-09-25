/** Workspace overlays: Ask AI drawer, escalate, resolve, reassign and priority dialogs. */
import { useMutation, useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { useToast } from "@/components/Toast";
import { FieldLabel, Icon, Modal, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { Priority, TicketDetail } from "@/lib/types";

const QUICK = ["What should I check next?", "Why this diagnosis?", "Find similar incidents", "Summarize incident", "Draft user update"];

export function CopilotDrawer({ ticket, open, onClose, onUseDraft }: { ticket: TicketDetail; open: boolean; onClose: () => void; onUseDraft: (text: string) => void }) {
  const toast = useToast();
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ role: "user" | "assistant"; content: string; draft?: string | null; refs?: string[] }[]>([]);
  const endRef = useRef<HTMLDivElement>(null);
  const history = useQuery({ queryKey: ["ticket", ticket.id, "copilot"], queryFn: () => api.tickets.copilot.history(ticket.id), enabled: open, staleTime: Infinity });
  useEffect(() => {
    if (history.data && messages.length === 0) setMessages(history.data);
  }, [history.data, messages.length]);
  useEffect(() => endRef.current?.scrollIntoView({ block: "end" }), [messages.length]);
  const ask = useMutation({
    mutationFn: (q: string) => api.tickets.copilot.ask(ticket.id, q),
    onMutate: (q) => setMessages((m) => [...m, { role: "user", content: q }]),
    onSuccess: (r) => setMessages((m) => [...m, { role: "assistant", content: r.answer, draft: r.draft_message, refs: r.references }]),
    onError: (e) => {
      setMessages((m) => m.slice(0, -1));
      toast(errorMessage(e, "Copilot couldn't answer right now."), "error");
    },
  });
  const submit = (q: string) => {
    const text = q.trim();
    if (text && !ask.isPending) {
      setInput("");
      ask.mutate(text);
    }
  };
  return (
    <div className={clsx("fixed inset-y-0 right-0 z-50 flex w-full max-w-sm transform flex-col border-l border-outline-variant/30 bg-surface-container-lowest shadow-2xl transition-transform duration-200 ease-in-out", open ? "translate-x-0" : "translate-x-full")} aria-hidden={!open}>
      <div className="flex items-center justify-between border-b border-surface-container-high p-space-md">
        <div className="flex items-center gap-space-xs">
          <Icon name="auto_awesome" className="text-[18px] text-secondary" />
          <span className="font-headline-sm text-headline-sm font-semibold text-on-surface">AI Copilot</span>
        </div>
        <button type="button" onClick={onClose} className="rounded p-1 text-on-surface-variant hover:text-on-surface" aria-label="Close copilot">
          <Icon name="close" className="text-[18px]" />
        </button>
      </div>
      <div className="flex flex-1 flex-col gap-space-md overflow-y-auto p-space-md">
        <div className="flex flex-col gap-space-xs">
          <span className="label-caps font-medium text-outline">Suggested questions</span>
          <div className="flex flex-col gap-1.5">
            {QUICK.map((q) => (
              <button key={q} type="button" disabled={ask.isPending} onClick={() => submit(q)} className="rounded bg-surface-container-low px-2.5 py-1.5 text-left text-[12px] font-medium text-on-surface transition-colors hover:bg-secondary-fixed hover:text-on-secondary-fixed-variant disabled:opacity-60">
                {q}
              </button>
            ))}
          </div>
        </div>
        <div className="flex flex-col gap-space-sm pt-space-xs text-body-sm">
          <div className="flex flex-col gap-1 rounded bg-surface-container-low p-space-sm text-[12px] text-on-surface">
            <span className="font-label-code text-[11px] font-medium text-secondary">Copilot</span>
            <p className="leading-relaxed">I'm grounded on {ticket.ticket_number}, its plan, notes, knowledge and similar incidents. I can explain and draft — you make every change.</p>
          </div>
          {messages.map((m, i) =>
            m.role === "user" ? (
              <div key={i} className="max-w-[85%] self-end rounded bg-surface-container-high p-space-sm text-[12px] text-on-surface">{m.content}</div>
            ) : (
              <div key={i} className="flex flex-col gap-1 rounded bg-surface-container-low p-space-md text-[12px] text-on-surface">
                <span className="font-label-code text-[11px] font-medium text-secondary">Copilot</span>
                <p className="whitespace-pre-line leading-relaxed">{m.content}</p>
                {m.refs && m.refs.length > 0 && <p className="font-label-code text-[10px] text-on-surface-variant">Sources: {m.refs.join(", ")}</p>}
                {m.draft && (
                  <div className="mt-1 flex flex-col gap-1 rounded border border-outline-variant/40 bg-surface-container-lowest p-space-sm">
                    <span className="label-caps text-on-surface-variant">Draft for the requester</span>
                    <p className="whitespace-pre-line">{m.draft}</p>
                    <button type="button" onClick={() => onUseDraft(m.draft!)} className="self-start font-body-sm text-[12px] font-medium text-secondary hover:underline">
                      Use as reply
                    </button>
                  </div>
                )}
              </div>
            ),
          )}
          {ask.isPending && (
            <div className="flex items-center gap-2 rounded bg-surface-container-low p-space-sm text-[12px] text-on-surface-variant">
              <Spinner /> Looking into it…
            </div>
          )}
          <div ref={endRef} />
        </div>
      </div>
      <form
        className="border-t border-surface-container-high bg-surface-container-lowest p-space-md"
        onSubmit={(e: FormEvent) => {
          e.preventDefault();
          submit(input);
        }}
      >
        <div className="relative flex items-center">
          <input value={input} onChange={(e) => setInput(e.target.value)} maxLength={2000} placeholder={`Ask about ${ticket.ticket_number}...`} aria-label="Ask the copilot" className="w-full rounded border border-transparent bg-surface-container-low px-3 py-2 pr-10 font-body-sm text-body-sm text-on-surface transition-all placeholder:text-outline focus:border-outline-variant focus:bg-surface-container-lowest focus:outline-none focus:ring-1 focus:ring-primary" />
          <button type="submit" disabled={!input.trim() || ask.isPending} className="absolute right-2 flex items-center justify-center p-1 text-on-surface-variant transition-colors hover:text-primary" aria-label="Send">
            <Icon name="arrow_forward" className="text-[16px]" />
          </button>
        </div>
      </form>
    </div>
  );
}

const REASONS = [
  { value: "requires_elevated_access", label: "Requires elevated access" },
  { value: "requires_specialist_expertise", label: "Requires specialist expertise" },
  { value: "outside_l1_runbook", label: "Outside the L1 runbook" },
  { value: "sla_risk", label: "SLA at risk" },
  { value: "vendor_involvement", label: "Needs vendor involvement" },
  { value: "other", label: "Other" },
];

export function EscalateModal({ ticket, open, onClose, onDone }: { ticket: TicketDetail; open: boolean; onClose: () => void; onDone: (t: TicketDetail) => void }) {
  const toast = useToast();
  const teams = useQuery({ queryKey: ["teams"], queryFn: api.admin.teams, enabled: open, staleTime: 5 * 60_000 });
  const [teamId, setTeamId] = useState(ticket.team?.id ?? "");
  const [reason, setReason] = useState(REASONS[0].value);
  const [note, setNote] = useState("");
  useEffect(() => {
    if (open) {
      setTeamId(ticket.team?.id ?? "");
      setNote("");
    }
  }, [open, ticket.team?.id]);
  const escalate = useMutation({
    mutationFn: () => api.tickets.escalate(ticket.id, { reason, note: note.trim() || undefined, target_team_id: teamId || undefined }),
    onSuccess: (t) => {
      toast(`Escalated to ${t.team?.name ?? "L2"}${t.assignee ? ` · ${t.assignee.name}` : ""}`);
      onDone(t);
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const completed = ticket.steps.filter((s) => s.status === "completed").length;
  const alreadyL2 = ticket.support_level === "L2";
  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Escalate incident"
      footer={
        <>
          <button type="button" className="btn-ghost h-8 px-3" onClick={onClose}>Cancel</button>
          <button type="button" className="btn-primary h-8 px-4" disabled={escalate.isPending || !teamId} onClick={() => escalate.mutate()}>
            {escalate.isPending ? <Spinner className="border-t-white" /> : "Confirm escalation"}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="esc-team">Target escalation team</FieldLabel>
        <select id="esc-team" className="input h-9" value={teamId} onChange={(e) => setTeamId(e.target.value)}>
          <option value="" disabled>Choose a team</option>
          {teams.data?.map((t) => (
            <option key={t.id} value={t.id} disabled={alreadyL2 && t.id === ticket.team?.id}>
              L2 {t.name}{t.l2_count === 0 ? " (no L2 engineers — team queue)" : ""}
            </option>
          ))}
        </select>
      </div>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="esc-reason">Reason for escalation</FieldLabel>
        <select id="esc-reason" className="input h-9" value={reason} onChange={(e) => setReason(e.target.value)}>
          {REASONS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}
        </select>
      </div>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="esc-note">Note for L2 (optional)</FieldLabel>
        <textarea id="esc-note" className="input h-20 resize-none py-2" value={note} onChange={(e) => setNote(e.target.value)} placeholder="What you checked and what you need" />
      </div>
      <div className="rounded bg-surface-container-low p-space-sm font-body-sm text-body-sm text-on-surface-variant">
        <p className="mb-1 font-medium text-on-surface">Moves with the ticket</p>
        Original request · AI diagnosis & evidence · resolution plan ({completed} completed) · notes · full activity history. Nexa also prepares an AI handoff brief for L2.
      </div>
    </Modal>
  );
}

const CODES = [
  { value: "fixed", label: "Fixed" },
  { value: "workaround", label: "Workaround applied" },
  { value: "user_guidance", label: "Guidance given" },
  { value: "no_fault_found", label: "No fault found" },
  { value: "duplicate", label: "Duplicate" },
  { value: "other", label: "Other" },
];

export function ResolveModal({ ticket, open, onClose, onDone }: { ticket: TicketDetail; open: boolean; onClose: () => void; onDone: (t: TicketDetail) => void }) {
  const toast = useToast();
  const [summary, setSummary] = useState("");
  const [code, setCode] = useState("fixed");
  const draft = useMutation({ mutationFn: () => api.tickets.resolutionDraft(ticket.id), onSuccess: (d) => setSummary((s) => s || d.resolution_summary) });
  const requestDraft = draft.mutate; // stable across renders
  useEffect(() => {
    if (open) {
      setSummary("");
      requestDraft();
    }
  }, [open, requestDraft]);
  const resolve = useMutation({
    mutationFn: () => api.tickets.resolve(ticket.id, { resolution_summary: summary.trim(), resolution_code: code }),
    onSuccess: (t) => {
      toast(`${ticket.ticket_number} resolved`);
      onDone(t as TicketDetail);
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const pending = ticket.steps.filter((s) => s.status === "pending" || s.status === "in_progress").length;
  const noun = ticket.ticket_type === "incident" ? "incident" : "request";
  return (
    <Modal
      open={open}
      onClose={onClose}
      width="max-w-lg"
      title={`Resolve ${noun} ${ticket.ticket_number}`}
      footer={
        <>
          <button type="button" className="btn-ghost h-8 px-3" onClick={onClose}>Cancel</button>
          <button type="button" className="btn-primary h-8 px-4" disabled={summary.trim().length < 10 || resolve.isPending} onClick={() => resolve.mutate()}>
            {resolve.isPending ? <Spinner className="border-t-white" /> : `Resolve ${noun}`}
          </button>
        </>
      }
    >
      <div className="flex flex-col gap-space-xs">
        <div className="flex items-center justify-between">
          <FieldLabel htmlFor="resolution-notes">{draft.data?.generated ? "AI Resolution Summary Draft" : "Resolution summary"}</FieldLabel>
          {draft.isPending ? <span className="flex items-center gap-1 font-label-code text-[10px] text-on-surface-variant"><Spinner className="h-3 w-3" /> Drafting…</span> : <span className="font-label-code text-[10px] font-medium text-secondary">Editable</span>}
        </div>
        <textarea id="resolution-notes" className="h-28 w-full resize-none rounded border border-outline-variant/40 bg-surface-container-low p-space-sm font-body-sm text-body-sm text-on-surface focus:outline-none focus:ring-1 focus:ring-primary" value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="What was the cause, what fixed it, and how you verified it" />
        {draft.data?.employee_summary && <p className="font-body-sm text-body-sm text-on-surface-variant">The requester will see a plain-language version of this.</p>}
      </div>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="resolution-code">Outcome</FieldLabel>
        <select id="resolution-code" className="input h-9" value={code} onChange={(e) => setCode(e.target.value)}>
          {CODES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
        </select>
      </div>
      {pending > 0 && <p className="rounded bg-surface-container-low px-space-sm py-2 font-body-sm text-body-sm text-on-surface-variant">{pending} step{pending > 1 ? "s are" : " is"} still pending. You can resolve anyway if they're no longer needed.</p>}
    </Modal>
  );
}

export function ReassignModal({ ticket, open, onClose, onDone }: { ticket: TicketDetail; open: boolean; onClose: () => void; onDone: (t: TicketDetail) => void }) {
  const toast = useToast();
  const teams = useQuery({ queryKey: ["teams"], queryFn: api.admin.teams, enabled: open, staleTime: 5 * 60_000 });
  const [teamId, setTeamId] = useState(ticket.team?.id ?? "");
  const engineers = useQuery({ queryKey: ["engineers", teamId], queryFn: () => api.engineers(teamId || undefined), enabled: open });
  const [assigneeId, setAssigneeId] = useState("");
  const [note, setNote] = useState("");
  const reassign = useMutation({
    mutationFn: () => api.tickets.reassign(ticket.id, { team_id: teamId || undefined, assignee_id: assigneeId || undefined, note: note.trim() || undefined }),
    onSuccess: (t) => {
      toast(`Reassigned to ${t.assignee?.name ?? t.team?.name ?? "the team queue"}`);
      onDone(t);
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  return (
    <Modal open={open} onClose={onClose} title="Reassign ticket" footer={<><button type="button" className="btn-ghost h-8 px-3" onClick={onClose}>Cancel</button><button type="button" className="btn-primary h-8 px-4" disabled={reassign.isPending || (!teamId && !assigneeId)} onClick={() => reassign.mutate()}>{reassign.isPending ? <Spinner className="border-t-white" /> : "Reassign"}</button></>}>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="ra-team">Team</FieldLabel>
        <select id="ra-team" className="input h-9" value={teamId} onChange={(e) => { setTeamId(e.target.value); setAssigneeId(""); }}>
          {teams.data?.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
        </select>
      </div>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="ra-person">Engineer</FieldLabel>
        <select id="ra-person" className="input h-9" value={assigneeId} onChange={(e) => setAssigneeId(e.target.value)}>
          <option value="">Least-loaded engineer in the team</option>
          {engineers.data?.filter((u) => u.id !== ticket.assignee?.id).map((u) => <option key={u.id} value={u.id}>{u.name} · {u.engineer_level}</option>)}
        </select>
      </div>
      <div className="flex flex-col gap-space-xs">
        <FieldLabel htmlFor="ra-note">Internal note (optional)</FieldLabel>
        <textarea id="ra-note" className="input h-16 resize-none py-2" value={note} onChange={(e) => setNote(e.target.value)} />
      </div>
    </Modal>
  );
}

export function PriorityModal({ ticket, open, onClose, onDone }: { ticket: TicketDetail; open: boolean; onClose: () => void; onDone: (t: TicketDetail) => void }) {
  const toast = useToast();
  const [priority, setPriority] = useState<Priority>(ticket.priority);
  const save = useMutation({
    mutationFn: () => api.tickets.update(ticket.id, { priority }),
    onSuccess: (t) => { toast(`Priority set to ${priority} — SLA recalculated`); onDone(t as TicketDetail); },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  return (
    <Modal open={open} onClose={onClose} title="Change priority" footer={<><button type="button" className="btn-ghost h-8 px-3" onClick={onClose}>Cancel</button><button type="button" className="btn-primary h-8 px-4" disabled={save.isPending || priority === ticket.priority} onClick={() => save.mutate()}>Save</button></>}>
      <div className="grid grid-cols-4 gap-space-xs">
        {(["P1", "P2", "P3", "P4"] as Priority[]).map((p) => (
          <button key={p} type="button" onClick={() => setPriority(p)} className={clsx("rounded-lg border px-2 py-2 font-label-code text-label-code", priority === p ? "border-primary bg-surface-container-low font-semibold" : "border-outline-variant/40 text-on-surface-variant")}>{p}</button>
        ))}
      </div>
      <p className="font-body-sm text-body-sm text-on-surface-variant">The SLA due date is recalculated from when the ticket was opened.</p>
    </Modal>
  );
}
