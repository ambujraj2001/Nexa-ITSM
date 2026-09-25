import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { useToast } from "@/components/Toast";
import {
  EmptyState,
  ErrorState,
  Icon,
  LoadingState,
  Spinner,
} from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { relative, shortDate, timeOfDay } from "@/lib/format";
import type { TicketDetail } from "@/lib/types";

type Tab = "activity" | "notes" | "similar" | "knowledge";

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      role="tab"
      aria-selected={active}
      onClick={onClick}
      className={clsx(
        "relative pb-2 transition-colors",
        active
          ? "font-medium text-on-surface"
          : "text-on-surface-variant hover:text-on-surface",
      )}
    >
      {children}
      {active && (
        <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary" />
      )}
    </button>
  );
}

function Composer({
  ticket,
  draft,
  onDraftUsed,
}: {
  ticket: TicketDetail;
  draft: string | null;
  onDraftUsed: () => void;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [content, setContent] = useState("");
  const [mode, setMode] = useState<"internal" | "requester">("internal");
  const [ask, setAsk] = useState(false);
  useEffect(() => {
    if (draft) {
      setContent(draft);
      setMode("requester");
      onDraftUsed();
    }
  }, [draft, onDraftUsed]);
  const send = useMutation({
    mutationFn: () =>
      api.tickets.comments.add(ticket.id, {
        content: content.trim(),
        visibility: mode,
        request_info: mode === "requester" && ask,
      }),
    onSuccess: () => {
      setContent("");
      setAsk(false);
      void queryClient.invalidateQueries({ queryKey: ["ticket", ticket.id] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast(
        mode === "internal"
          ? "Note added"
          : ask
            ? "Question sent — ticket is waiting on the requester"
            : "Reply sent to the requester",
      );
    },
    onError: (e) => toast(errorMessage(e), "error"),
  });
  if (!ticket.permissions.can_reply) return null;
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (content.trim()) send.mutate();
  };
  return (
    <form
      onSubmit={submit}
      className="flex flex-col gap-space-sm rounded-lg bg-surface-container-lowest p-space-md shadow-sm"
    >
      <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-low p-1 self-start font-body-sm text-body-sm">
        {(["internal", "requester"] as const).map((m) => (
          <button
            key={m}
            type="button"
            onClick={() => setMode(m)}
            className={clsx(
              "rounded px-space-md py-1 transition-colors",
              mode === m
                ? "bg-surface-container-lowest font-medium text-on-surface shadow-sm"
                : "text-on-surface-variant hover:text-on-surface",
            )}
          >
            {m === "internal"
              ? "Internal note"
              : `Reply to ${ticket.requester.name.split(" ")[0]}`}
          </button>
        ))}
      </div>
      <textarea
        className="input h-24 resize-none py-2"
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder={
          mode === "internal"
            ? "Notes for engineers — never shown to the requester"
            : "Message the requester…"
        }
        aria-label={
          mode === "internal" ? "Internal note" : "Reply to requester"
        }
      />
      <div className="flex flex-wrap items-center justify-between gap-space-sm">
        {mode === "requester" && ticket.permissions.can_work ? (
          <label className="flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
            <input
              type="checkbox"
              checked={ask}
              onChange={(e) => setAsk(e.target.checked)}
              className="h-3.5 w-3.5 accent-primary"
            />
            Ask for information (ticket waits on the requester)
          </label>
        ) : (
          <span className="font-body-sm text-body-sm text-outline">
            {mode === "internal"
              ? "Visible to IT staff only"
              : "The requester sees this in their ticket and assistant"}
          </span>
        )}
        <button
          type="submit"
          className="btn-primary h-8 px-4"
          disabled={!content.trim() || send.isPending}
        >
          {send.isPending ? (
            <Spinner className="border-t-white" />
          ) : mode === "internal" ? (
            "Add note"
          ) : (
            "Send"
          )}
        </button>
      </div>
    </form>
  );
}

export function ActivityTabs({
  ticket,
  replyDraft,
  onDraftUsed,
}: {
  ticket: TicketDetail;
  replyDraft: string | null;
  onDraftUsed: () => void;
}) {
  const [tab, setTab] = useState<Tab>("activity");
  useEffect(() => {
    if (replyDraft) setTab("notes");
  }, [replyDraft]);
  const activity = useQuery({
    queryKey: ["ticket", ticket.id, "activity"],
    queryFn: () => api.tickets.activity(ticket.id),
  });
  const comments = useQuery({
    queryKey: ["ticket", ticket.id, "comments"],
    queryFn: () => api.tickets.comments.list(ticket.id),
  });
  const related = useQuery({
    queryKey: ["ticket", ticket.id, "related"],
    queryFn: () => api.tickets.related(ticket.id),
    staleTime: 5 * 60_000,
  });
  const items = [...(activity.data ?? [])].reverse();

  return (
    <section className="flex flex-col gap-space-md pt-space-lg">
      <div
        className="flex flex-wrap items-center gap-space-lg border-b border-surface-container-high font-body-sm text-body-sm"
        role="tablist"
      >
        <TabButton
          active={tab === "activity"}
          onClick={() => setTab("activity")}
        >
          Activity Timeline{activity.data ? ` (${activity.data.length})` : ""}
        </TabButton>
        <TabButton active={tab === "notes"} onClick={() => setTab("notes")}>
          Notes & Messages{comments.data ? ` (${comments.data.length})` : ""}
        </TabButton>
        <TabButton active={tab === "similar"} onClick={() => setTab("similar")}>
          Similar Incidents
          {related.data ? ` (${related.data.similar_incidents.length})` : ""}
        </TabButton>
        <TabButton
          active={tab === "knowledge"}
          onClick={() => setTab("knowledge")}
        >
          Knowledge{related.data ? ` (${related.data.knowledge.length})` : ""}
        </TabButton>
      </div>

      {tab === "activity" && (
        <div className="flex flex-col gap-space-sm pt-space-xs">
          {activity.isLoading && <LoadingState label="Loading activity…" />}
          {activity.isError && (
            <ErrorState
              title="Unable to load activity."
              onRetry={() => void activity.refetch()}
            />
          )}
          {items.map((a) => (
            <div
              key={a.id}
              className="flex items-baseline gap-space-md font-body-sm text-body-sm"
            >
              <span
                className="w-16 shrink-0 font-label-code text-[11px] text-outline"
                title={shortDate(a.at)}
              >
                {timeOfDay(a.at)}
              </span>
              <span
                className={clsx(
                  "flex shrink-0 items-center gap-1 font-medium",
                  a.actor_type === "ai"
                    ? "text-secondary"
                    : a.actor_type === "system"
                      ? "text-on-surface-variant"
                      : "text-on-surface",
                )}
              >
                {a.actor_type === "ai" && (
                  <Icon name="auto_awesome" className="text-[13px]" />
                )}
                {a.actor_label}
              </span>
              <span className="text-on-surface-variant">
                {a.summary}
                {a.detail && (
                  <span className="text-outline"> — {a.detail}</span>
                )}
              </span>
            </div>
          ))}
        </div>
      )}

      {tab === "notes" && (
        <div className="flex flex-col gap-space-md pt-space-xs">
          {comments.isLoading && <LoadingState label="Loading notes…" />}
          {comments.isError && (
            <ErrorState
              title="Unable to load notes."
              onRetry={() => void comments.refetch()}
            />
          )}
          {comments.data?.length === 0 && (
            <p className="font-body-md text-body-md text-on-surface-variant">
              No notes or messages yet.
            </p>
          )}
          {comments.data?.map((c) => (
            <div
              key={c.id}
              className={clsx(
                "flex flex-col gap-1 rounded-lg px-space-md py-space-sm",
                c.visibility === "internal"
                  ? "bg-surface-container-low"
                  : "bg-surface-container-lowest shadow-sm",
              )}
            >
              <div className="flex flex-wrap items-center gap-space-xs font-body-sm text-body-sm">
                <span
                  className={clsx(
                    "font-medium",
                    c.author_type === "ai"
                      ? "text-secondary"
                      : "text-on-surface",
                  )}
                >
                  {c.author_type === "ai" && (
                    <Icon
                      name="auto_awesome"
                      className="mr-0.5 align-[-2px] text-[13px]"
                    />
                  )}
                  {c.author_label}
                </span>
                <span className="text-on-surface-variant">
                  · {relative(c.created_at)}
                </span>
                <span className="chip bg-surface-container-high text-on-surface-variant">
                  {c.visibility === "internal"
                    ? "Internal"
                    : c.author?.id === ticket.requester.id
                      ? "From requester"
                      : "To requester"}
                </span>
                {c.kind === "question" && (
                  <span className="chip bg-error-container text-on-error-container">
                    Asked for info
                  </span>
                )}
                {c.kind === "escalation_note" && (
                  <span className="chip bg-secondary-fixed text-on-secondary-fixed-variant">
                    Escalation note
                  </span>
                )}
                {c.kind === "handoff_summary" && (
                  <span className="chip bg-secondary-fixed text-on-secondary-fixed-variant">
                    AI handoff brief
                  </span>
                )}
              </div>
              <p className="whitespace-pre-line font-body-md text-body-md text-on-surface">
                {c.content}
              </p>
            </div>
          ))}
          <Composer
            ticket={ticket}
            draft={replyDraft}
            onDraftUsed={onDraftUsed}
          />
        </div>
      )}

      {tab === "similar" && (
        <div className="flex flex-col gap-space-xs pt-space-xs">
          {related.isLoading && (
            <LoadingState label="Finding similar incidents…" />
          )}
          {related.isError && (
            <ErrorState
              title="Unable to load similar incidents."
              onRetry={() => void related.refetch()}
            />
          )}
          {related.data?.similar_incidents.length === 0 && (
            <EmptyState
              icon="history"
              title="No similar resolved incidents"
              message="Resolved tickets become searchable here."
            />
          )}
          {related.data?.similar_incidents.map((s) => (
            <details
              key={s.ticket_id}
              className="group rounded p-space-sm transition-colors hover:bg-surface-container-low"
            >
              <summary className="flex cursor-pointer list-none items-center justify-between gap-space-sm">
                <div className="flex min-w-0 items-center gap-space-sm">
                  <span className="font-label-code text-label-code font-medium text-on-surface">
                    {s.ticket_number}
                  </span>
                  <span className="truncate font-body-sm text-body-sm text-on-surface-variant">
                    {s.title}
                  </span>
                </div>
                {s.resolved_in && (
                  <span className="shrink-0 rounded bg-tertiary-container px-1.5 py-0.5 font-label-code text-[11px] text-tertiary-fixed-dim">
                    Resolved in {s.resolved_in}
                  </span>
                )}
              </summary>
              {s.resolution_summary && (
                <p className="mt-space-xs pl-1 font-body-sm text-body-sm text-on-surface">
                  {s.resolution_summary}
                </p>
              )}
            </details>
          ))}
        </div>
      )}

      {tab === "knowledge" && (
        <div className="flex flex-col gap-space-xs pt-space-xs">
          {related.isLoading && <LoadingState label="Searching knowledge…" />}
          {related.data?.knowledge.length === 0 && (
            <EmptyState icon="library_books" title="No matching articles" />
          )}
          {related.data?.knowledge.map((k) => (
            <Link
              key={k.article_id}
              to={`/knowledge/${k.article_id}`}
              className="flex items-center justify-between rounded p-space-sm transition-colors hover:bg-surface-container-low"
            >
              <div className="flex min-w-0 items-center gap-space-sm">
                <Icon name="description" className="text-[16px] text-outline" />
                <span className="truncate font-body-sm text-body-sm text-on-surface">
                  {k.article_number}: {k.title}
                </span>
              </div>
              <span className="shrink-0 font-label-code text-[11px] text-outline">
                Updated {relative(k.updated_at)}
              </span>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
