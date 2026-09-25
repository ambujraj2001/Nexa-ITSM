/**
 * Employee AI Assistant (reference: employee_ai_assistant_simple_focused).
 * The conversation is the primary surface; active tickets are secondary.
 */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { InvestigationProgress } from "@/components/InvestigationProgress";
import { useToast } from "@/components/Toast";
import { ErrorState, Icon, LoadingState, PriorityChip, Spinner, StatusChip } from "@/components/ui";
import { api, ApiError, errorMessage } from "@/lib/api";
import { fileSize, shortDate, timeOfDay } from "@/lib/format";
import type { Conversation, Message, ProposalPayload, StatusCard, TicketSummary } from "@/lib/types";

const STARTERS = [
  { icon: "report", label: "Report an issue", text: "I want to report an issue with " },
  { icon: "key", label: "Request access", text: "I need to request access to " },
  { icon: "confirmation_number", label: "Check a ticket", text: "What is the status of my ticket?" },
  { icon: "contact_support", label: "Ask IT", text: "How do I " },
];

const CONVERSATION_KEY = ["conversation", "current"] as const;

/** Upsert server messages into the cached conversation (drops optimistic placeholders). */
function mergeMessages(queryClient: ReturnType<typeof useQueryClient>, incoming: Message[]) {
  queryClient.setQueryData<Conversation>(CONVERSATION_KEY, (current) => {
    if (!current) return current;
    const byId = new Map(current.messages.filter((m) => !m.id.startsWith("optimistic-")).map((m) => [m.id, m]));
    for (const m of incoming) byId.set(m.id, m);
    const messages = [...byId.values()].sort((a, b) => a.created_at.localeCompare(b.created_at));
    return { ...current, messages };
  });
}

function ProposalCard({ message, conversationId, disabled }: { message: Message; conversationId: string; disabled: boolean }) {
  const p = message.payload as unknown as ProposalPayload;
  const queryClient = useQueryClient();
  const toast = useToast();
  const confirm = useMutation({
    mutationFn: () => api.conversations.confirm(conversationId, message.id),
    onSuccess: (res) => {
      mergeMessages(queryClient, res.messages);
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "employee"] });
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const dismiss = useMutation({
    mutationFn: () => api.conversations.dismiss(conversationId, message.id),
    onSuccess: (res) => mergeMessages(queryClient, res.messages),
    onError: (e) => toast(errorMessage(e), "error"),
  });
  const actionable = p.status === "proposed";
  const noun = p.type_label?.toLowerCase() === "request" ? "request" : "incident";
  return (
    <div className={clsx("nx-ai flex flex-col gap-space-sm rounded-xl p-space-md shadow-[0_18px_40px_-22px_rgba(79,70,229,0.45)]", !actionable && p.status !== "created" && "opacity-70")}>
      <div className="flex items-center justify-between">
        <span className="label-caps text-on-surface-variant">{p.manual ? "Ticket draft" : "AI Analysis"}</span>
        <PriorityChip priority={p.priority} compact />
      </div>
      <p className="font-body-md text-body-md font-medium text-on-surface">{p.title}</p>
      <div className="grid grid-cols-1 gap-space-sm font-body-sm text-body-sm sm:grid-cols-2">
        <div className="flex flex-col">
          <span className="text-on-surface-variant">Category</span>
          <span className="font-medium text-on-surface">{[p.category, p.subcategory].filter(Boolean).join(" / ") || "To be classified by IT"}</span>
        </div>
        <div className="flex flex-col">
          <span className="text-on-surface-variant">Likely cause</span>
          <span className="font-medium text-on-surface">
            {p.likely_cause ?? "Not clear yet"}
            {p.likely_cause && p.confidence_label && <span className="ml-1 font-normal text-on-surface-variant">({p.confidence_label} confidence)</span>}
          </span>
        </div>
        {p.team_name && (
          <div className="flex flex-col">
            <span className="text-on-surface-variant">Routed to</span>
            <span className="font-medium text-on-surface">{p.team_name}</span>
          </div>
        )}
        {p.signals?.length > 0 && (
          <div className="flex flex-col">
            <span className="text-on-surface-variant">Details noted</span>
            <span className="font-medium text-on-surface">{p.signals.map((s) => s.value).join(" · ")}</span>
          </div>
        )}
      </div>
      {actionable ? (
        <div className="flex flex-wrap items-center gap-space-sm pt-space-xs">
          <button type="button" disabled={disabled || confirm.isPending || dismiss.isPending} onClick={() => confirm.mutate()} className="inline-flex h-8 items-center gap-space-xs rounded-lg bg-primary px-space-md font-headline-sm text-headline-sm text-on-primary shadow-sm transition-colors hover:bg-inverse-surface disabled:opacity-60">
            {confirm.isPending ? <Spinner className="border-t-white" /> : <Icon name="add_task" className="text-[15px]" />}
            <span>Create {noun}</span>
          </button>
          <button type="button" disabled={confirm.isPending || dismiss.isPending} onClick={() => dismiss.mutate()} className="btn-ghost h-8 px-3">
            Not now
          </button>
        </div>
      ) : (
        p.status !== "created" && <p className="font-body-sm text-body-sm text-outline">{p.status === "dismissed" ? "Not filed." : "Updated below."}</p>
      )}
    </div>
  );
}

function StatusCards({ cards }: { cards: StatusCard[] }) {
  return (
    <div className="flex flex-col gap-space-sm">
      {cards.map((c) => (
        <Link key={c.ticket_id} to={`/my-tickets/${c.ticket_id}`} className="flex flex-col gap-1 rounded-xl border border-surface-container-high bg-surface-container-low p-space-md transition-colors hover:bg-surface-container">
          <div className="flex flex-wrap items-center gap-space-sm">
            <span className="font-label-code text-label-code font-semibold text-on-surface">{c.ticket_number}</span>
            <span className="font-body-md text-body-md font-medium text-on-surface">{c.title}</span>
            <StatusChip status={c.status} label={c.status_label} />
          </div>
          <div className="flex flex-wrap items-center gap-x-space-md gap-y-1 font-body-sm text-body-sm text-on-surface-variant">
            {c.assignee_name ? <span>{c.assignee_name}{c.team_name ? ` · ${c.team_name}` : ""}</span> : c.team_name ? <span>{c.team_name} queue</span> : null}
            {c.steps_total > 0 && <span>{c.steps_done} of {c.steps_total} steps done</span>}
            {c.waiting_on === "you" && <span className="font-medium text-error">Waiting on you</span>}
          </div>
        </Link>
      ))}
    </div>
  );
}

function AssistantBubble({ message, conversationId, onSend, busy, name }: { message: Message; conversationId: string; onSend: (text: string) => void; busy: boolean; name: string }) {
  const payload = message.payload ?? {};
  const suggestions = (payload.suggestions as string[] | undefined) ?? [];
  return (
    <div className="flex w-full justify-start animate-fade-in">
      <div className="flex max-w-2xl flex-col gap-space-md rounded-2xl rounded-tl-sm bg-surface-container-lowest px-space-lg py-space-lg text-on-surface shadow-sm">
        <div className="flex items-center gap-space-sm">
          <div className="flex h-6 w-6 items-center justify-center rounded bg-surface-container-highest text-on-surface">
            <Icon name="auto_awesome" className="text-[16px]" />
          </div>
          <div className="flex items-center gap-space-xs">
            <span className="font-headline-sm text-headline-sm text-on-surface">{name}</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant">• {timeOfDay(message.created_at)}</span>
          </div>
        </div>
        {message.content && <p className="whitespace-pre-line font-body-lg text-body-lg leading-relaxed text-on-surface">{message.content}</p>}
        {message.message_type === "triage_proposal" && <ProposalCard message={message} conversationId={conversationId} disabled={busy} />}
        {message.message_type === "ticket_created" && message.ticket_id && <InvestigationProgress ticketId={message.ticket_id} typeLabel={String(payload.type_label ?? "Ticket")} />}
        {message.message_type === "ticket_status" && <StatusCards cards={(payload.tickets as StatusCard[]) ?? []} />}
        {message.message_type === "knowledge_answer" && Array.isArray(payload.sources) && (payload.sources as { id: string; article_number: string; title: string }[]).length > 0 && (
          <div className="flex flex-col gap-1">
            <span className="label-caps text-on-surface-variant">From the knowledge base</span>
            {(payload.sources as { id: string; article_number: string; title: string }[]).map((s) => (
              <Link key={s.id} to={`/knowledge/${s.id}`} className="inline-flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface hover:text-secondary">
                <Icon name="description" className="text-[15px] text-outline" />
                <span className="font-label-code text-label-code text-on-surface-variant">{s.article_number}</span> {s.title}
              </Link>
            ))}
          </div>
        )}
        {suggestions.length > 0 && (
          <div className="flex flex-wrap items-center gap-space-xs pt-space-xs">
            {suggestions.map((s) => (
              <button key={s} type="button" disabled={busy} onClick={() => onSend(s)} className="flex items-center gap-space-xs rounded-full bg-surface-container-low px-space-md py-1 font-body-sm text-body-sm text-on-surface-variant transition-colors hover:bg-surface-container hover:text-on-surface disabled:opacity-60">
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function ActiveTicketCard({ ticket }: { ticket: TicketSummary }) {
  const who = ticket.assignee ? `${ticket.assignee.name} ${ticket.status === "pending_user" ? "is waiting on you" : "investigating"}` : ticket.team ? `${ticket.team.name} queue` : "Being routed";
  return (
    <div className="w-full rounded-xl border border-surface-container-high/60 bg-surface-container-lowest px-space-lg py-space-md shadow-sm transition-shadow hover:shadow-md">
      <div className="flex flex-col justify-between gap-space-sm md:flex-row md:items-center">
        <div className="flex flex-wrap items-center gap-space-sm">
          <span className="font-label-code text-label-code font-semibold text-on-surface">{ticket.ticket_number}</span>
          <span className="font-body-sm text-body-sm text-outline">•</span>
          <span className="font-headline-sm text-headline-sm font-medium text-on-surface">{ticket.title}</span>
          <PriorityChip priority={ticket.priority} compact />
          <StatusChip status={ticket.status} label={ticket.status_label} />
          <span className="hidden font-body-sm text-body-sm text-outline sm:inline">•</span>
          <div className="flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
            <Icon name="person" className="text-[15px] text-outline" />
            <span>{who}</span>
          </div>
        </div>
        <Link to={`/my-tickets/${ticket.id}`} className="inline-flex shrink-0 items-center gap-1 self-start font-body-sm text-body-sm font-medium text-on-surface transition-colors hover:text-secondary md:self-center">
          <span>View details</span>
          <Icon name="chevron_right" className="text-[16px]" />
        </Link>
      </div>
    </div>
  );
}

export function AssistantPage() {
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [draft, setDraft] = useState("");
  const [attachments, setAttachments] = useState<{ id: string; file_name: string; size_bytes: number }[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const endRef = useRef<HTMLDivElement>(null);
  // Logo / "ITSM" breadcrumb → a fresh welcome screen; the previous chat is kept.
  const location = useLocation();
  const [welcome, setWelcome] = useState(false);
  // First message from the welcome screen: show it immediately while the conversation is created.
  const [pendingFirst, setPendingFirst] = useState<Message | null>(null);
  useEffect(() => {
    if ((location.state as { home?: number } | null)?.home) setWelcome(true);
  }, [location.key, location.state]);

  const conversation = useQuery({ queryKey: CONVERSATION_KEY, queryFn: api.conversations.current });
  const dashboard = useQuery({ queryKey: ["dashboard", "employee"], queryFn: api.dashboard.employee });
  const health = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false, staleTime: 60_000 });

  const send = useMutation({
    mutationFn: (text: string) => api.conversations.send(queryClient.getQueryData<Conversation>(CONVERSATION_KEY)!.id, text),
    onMutate: (text) => {
      const optimistic: Message = { id: `optimistic-${Date.now()}`, role: "user", content: text, message_type: "text", payload: {}, ticket_id: null, created_at: new Date().toISOString() };
      queryClient.setQueryData<Conversation>(CONVERSATION_KEY, (c) => (c ? { ...c, messages: [...c.messages, optimistic] } : c));
    },
    onSuccess: (res) => {
      mergeMessages(queryClient, res.messages);
      setAttachments([]);
      void queryClient.invalidateQueries({ queryKey: ["dashboard", "employee"] });
    },
    onError: (e, text) => {
      queryClient.setQueryData<Conversation>(CONVERSATION_KEY, (c) => (c ? { ...c, messages: c.messages.filter((m) => !m.id.startsWith("optimistic-")) } : c));
      setDraft(text);
      toast(e instanceof ApiError && e.code === "conversation_busy" ? "Still working on your last message…" : errorMessage(e, "Your message couldn't be sent."), "error");
    },
  });

  const newConversation = useMutation({
    mutationFn: api.conversations.create,
    onSuccess: (c) => queryClient.setQueryData(CONVERSATION_KEY, c),
    onError: (e) => toast(errorMessage(e), "error"),
  });

  const upload = useMutation({
    mutationFn: (file: File) => api.conversations.upload(conversation.data!.id, file),
    onSuccess: (a) => setAttachments((current) => [...current, a]),
    onError: (e) => toast(errorMessage(e, "That file couldn't be attached."), "error"),
  });

  const messages = pendingFirst ? [pendingFirst] : (conversation.data?.messages ?? []);
  // Keep the newest message in view: on new messages, and whenever content grows
  // (progress cards, late-loading data) while the reader is already near the bottom.
  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages.length, send.isPending]);
  useEffect(() => {
    const end = endRef.current;
    const scroller = end?.closest(".overflow-y-auto");
    const thread = end?.parentElement;
    if (!scroller || !thread || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(() => {
      if (scroller.scrollHeight - scroller.scrollTop - scroller.clientHeight < 400) scroller.scrollTop = scroller.scrollHeight;
    });
    observer.observe(thread);
    return () => observer.disconnect();
  }, [conversation.data?.id, messages.length > 0]);

  const submit = (text: string) => {
    const content = text.trim();
    if (!content || !conversation.data || send.isPending) return;
    const withFiles = attachments.length ? `${content}\n\n(Attached: ${attachments.map((a) => a.file_name).join(", ")})` : content;
    setDraft("");
    if (welcome) {
      // Starting from the welcome screen opens a new conversation for this message —
      // the chat opens instantly with the message; the conversation is created behind it.
      setPendingFirst({ id: `optimistic-${Date.now()}`, role: "user", content: withFiles, message_type: "text", payload: {}, ticket_id: null, created_at: new Date().toISOString() });
      setWelcome(false);
      void newConversation
        .mutateAsync()
        .then(() => send.mutate(withFiles))
        .catch(() => setDraft(withFiles))
        .finally(() => setPendingFirst(null));
      return;
    }
    send.mutate(withFiles);
  };
  const onSubmit = (e: FormEvent) => {
    e.preventDefault();
    submit(draft);
  };
  const fill = (text: string) => {
    setDraft(text);
    inputRef.current?.focus();
  };

  const aiReady = health.data?.configured.ai ?? true;
  const active = dashboard.data?.active ?? [];
  const recent = dashboard.data?.recent ?? [];

  const composer = (
        <form onSubmit={onSubmit} className="nx-composer relative w-full rounded-2xl bg-white/85 p-space-sm backdrop-blur-xl transition-all">
          <div className="flex items-center gap-space-sm px-space-sm py-space-xs">
            <Icon name="auto_awesome" className="text-[20px] text-on-surface-variant" />
            <input
              ref={inputRef}
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={4000}
              aria-label="Describe an IT issue or ask a question"
              placeholder={send.isPending ? "Working on it…" : "Describe an IT issue or ask a question..."}
              className="flex-1 bg-transparent py-1 font-body-lg text-body-lg text-on-surface placeholder:text-outline focus:outline-none"
            />
            <div className="flex items-center gap-space-xs">
              <input ref={fileRef} type="file" className="hidden" accept="image/*,.pdf,.txt,.log,.csv,.json,.zip" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload.mutate(f); e.target.value = ""; }} />
              <button type="button" disabled={!conversation.data || upload.isPending} onClick={() => fileRef.current?.click()} className="flex items-center justify-center rounded-lg p-space-xs text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface" title="Attach screenshot or log">
                {upload.isPending ? <Spinner /> : <Icon name="attach_file" className="text-[20px]" />}
              </button>
              <button type="submit" disabled={!draft.trim() || send.isPending || !conversation.data} className="flex h-9 items-center gap-space-xs rounded-lg bg-primary px-space-md font-headline-sm text-headline-sm text-on-primary transition-colors hover:bg-inverse-surface disabled:opacity-60">
                <span>Send</span>
                <Icon name="arrow_upward" className="text-[16px]" />
              </button>
            </div>
          </div>
          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-space-xs px-space-sm pb-space-xs">
              {attachments.map((a) => (
                <span key={a.id} className="chip bg-surface-container-low text-on-surface-variant">
                  <Icon name="attachment" className="text-[13px]" /> {a.file_name} {fileSize(a.size_bytes)}
                </span>
              ))}
            </div>
          )}
        </form>
  );

  const ticketsPanel = (
    <div className="flex w-full flex-col gap-space-md">
          <div className="flex items-center justify-between px-space-xs">
            <h2 className="font-headline-sm text-headline-sm font-semibold tracking-tight text-on-surface">Active Tickets</h2>
            <span className="font-body-sm text-body-sm text-on-surface-variant">{dashboard.data ? `${active.length} in progress` : ""}</span>
          </div>
          {dashboard.isLoading && <LoadingState label="Loading tickets…" />}
          {dashboard.isError && <ErrorState title="Unable to load tickets." message={errorMessage(dashboard.error)} onRetry={() => void dashboard.refetch()} />}
          {dashboard.data && active.length === 0 && <p className="px-space-xs font-body-md text-body-md text-on-surface-variant">No open tickets. Describe a problem above and Nexa will take it from there.</p>}
          {active.map((t) => (
            <ActiveTicketCard key={t.id} ticket={t} />
          ))}
          {recent.length > 0 && (
            <details className="group px-space-xs pt-space-sm">
              <summary className="flex cursor-pointer list-none items-center gap-1 font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface">
                <Icon name="chevron_right" className="text-[16px] transition-transform group-open:rotate-90" /> Recently resolved ({recent.length})
              </summary>
              <div className="mt-space-sm flex flex-col gap-1">
                {recent.map((t) => (
                  <Link key={t.id} to={`/my-tickets/${t.id}`} className="flex items-center gap-space-sm rounded px-space-sm py-1.5 font-body-sm text-body-sm hover:bg-surface-container-low">
                    <span className="font-label-code text-label-code text-on-surface-variant">{t.ticket_number}</span>
                    <span className="flex-1 truncate text-on-surface">{t.title}</span>
                    <StatusChip status={t.status} label={t.status_label} />
                  </Link>
                ))}
              </div>
            </details>
          )}
    </div>
  );

  const chatting = !welcome && !!conversation.data && messages.length > 0;

  if (conversation.isLoading) {
    return (
      <div className="flex h-[calc(100vh-4rem)] w-full items-center justify-center">
        <LoadingState label="Loading your conversation…" />
      </div>
    );
  }

  if (!chatting) {
    return (
      <div className="flex w-full flex-col">
        <div className="relative mx-auto flex w-full max-w-4xl flex-col items-center px-gutter py-space-xl">
          <div className="pointer-events-none absolute left-1/2 top-12 -z-10 h-96 w-96 -translate-x-1/2 rounded-full bg-surface-container-highest/40 blur-3xl" />
        <div className="mb-space-xl flex max-w-3xl flex-col items-center text-center">
          <div className="mb-space-sm inline-flex items-center gap-space-xs rounded-full bg-surface-container-low px-space-md py-1 font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant">
            <span className={clsx("h-1.5 w-1.5 rounded-full", aiReady ? "animate-pulse bg-on-tertiary-container" : "bg-outline")} />
            {aiReady ? "AI IT Concierge Active" : "Requests go straight to IT"}
          </div>
          <h1 className="nx-gradient-text font-display-lg text-[clamp(32px,4.5vw,52px)] font-semibold leading-tight tracking-tight">How can we help you today?</h1>
          <p className="mt-space-xs font-body-md text-body-md text-on-surface-variant">Ask anything, request access, or report a disruption. We'll handle the rest.</p>
        </div>

          {composer}
        <div className="mt-space-md flex w-full flex-wrap items-center justify-center gap-space-sm">
          {STARTERS.map((s) => (
            <button key={s.label} type="button" onClick={() => fill(s.text)} className="flex items-center gap-space-xs rounded-full bg-surface-container-lowest px-space-md py-1.5 font-body-md text-body-md text-on-surface shadow-sm transition-colors hover:bg-surface-container-low">
              <Icon name={s.icon} className="text-[15px] text-on-surface-variant" />
              <span>{s.label}</span>
            </button>
          ))}
        </div>
          <div className="mt-space-xl w-full">
            {conversation.isLoading && <LoadingState label="Loading your conversation…" />}
            {conversation.isError && <ErrorState title="Unable to load the assistant." message={errorMessage(conversation.error)} onRetry={() => void conversation.refetch()} />}
          </div>
          <div className="mt-space-xl w-full pt-space-lg">{ticketsPanel}</div>
        </div>
      </div>
    );
  }

  // Chat mode: header, scrolling thread, composer pinned to the bottom; tickets alongside.
  return (
    <div className="mx-auto flex h-[calc(100vh-4rem)] w-full max-w-7xl gap-space-lg px-gutter py-space-md">
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm">
        <header className="flex items-center justify-between border-b border-surface-container-high px-space-lg py-space-sm">
          <div className="flex items-center gap-space-sm">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-secondary-fixed text-on-secondary-fixed"><Icon name="auto_awesome" className="text-[16px]" /></span>
            <div className="flex flex-col">
              <span className="font-headline-sm text-headline-sm text-on-surface">Nexa Assistant</span>
              <span className="font-body-sm text-body-sm text-outline">Started {shortDate(messages[0].created_at)}</span>
            </div>
          </div>
          <button type="button" onClick={() => newConversation.mutate()} disabled={newConversation.isPending || send.isPending} className="inline-flex items-center gap-1 font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface">
            <Icon name="add_comment" className="text-[15px]" /> New conversation
          </button>
        </header>
        <div className="flex-1 overflow-y-auto bg-gradient-to-b from-[#f6f8ff] to-white px-space-lg py-space-lg">
          <div className="mx-auto max-w-3xl">
              <div className="flex w-full flex-col gap-space-md" aria-live="polite">
                {messages.map((m) =>
                  m.role === "user" ? (
                    <div key={m.id} className="flex w-full justify-end animate-fade-in">
                      <div className="max-w-xl rounded-2xl rounded-tr-sm bg-surface-container-high px-space-lg py-space-md text-on-surface shadow-sm">
                        <div className="mb-1 flex items-center gap-space-xs">
                          <span className="font-headline-sm text-headline-sm text-on-surface">{me?.name.split(" ")[0] ?? "You"}</span>
                          <span className="font-body-sm text-body-sm text-on-surface-variant">• {timeOfDay(m.created_at)}</span>
                        </div>
                        <p className="whitespace-pre-line font-body-lg text-body-lg leading-relaxed">{m.content}</p>
                      </div>
                    </div>
                  ) : (
                    <AssistantBubble key={m.id} message={m} conversationId={conversation.data!.id} onSend={submit} busy={send.isPending} name="AI Assistant" />
                  ),
                )}
                {(send.isPending || pendingFirst) && (
                  <div className="flex w-full justify-start">
                    <div className="flex items-center gap-space-sm rounded-2xl rounded-tl-sm bg-surface-container-lowest px-space-lg py-space-md font-body-md text-body-md text-on-surface-variant shadow-sm">
                      <Spinner /> Understanding your request…
                    </div>
                  </div>
                )}
                <div ref={endRef} />
              </div>
          </div>
        </div>
        <div className="border-t border-surface-container-high bg-surface-container-lowest px-space-lg py-space-sm">
          <div className="mx-auto max-w-3xl">{composer}</div>
        </div>
      </section>
      <aside className="hidden w-80 shrink-0 overflow-y-auto lg:block">{ticketsPanel}</aside>
    </div>
  );
}
