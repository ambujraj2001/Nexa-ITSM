/**
 * "Suggested next steps" — the AI-proposed resolution plan that the engineer
 * executes by hand. The engineer controls everything: complete, edit, add,
 * delete, skip, reorder, annotate. Commands stay behind "View technical details".
 */
import { DndContext, KeyboardSensor, PointerSensor, closestCenter, useSensor, useSensors, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, arrayMove, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useState, type FormEvent } from "react";
import { useToast } from "@/components/Toast";
import { Icon, Modal, Spinner } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { timeOfDay } from "@/lib/format";
import type { Step, StepStatus, TicketDetail } from "@/lib/types";

type StepPatch = Partial<{ description: string; details: string | null; technical_details: string | null; status: StepStatus; notes: string | null }>;

function useStepMutations(ticket: TicketDetail) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const apply = (steps: Step[]) => {
    queryClient.setQueryData<TicketDetail>(["ticket", ticket.id], (t) => (t ? { ...t, steps, steps_total: steps.length, steps_done: steps.filter((s) => s.status === "completed" || s.status === "skipped").length } : t));
    void queryClient.invalidateQueries({ queryKey: ["ticket", ticket.id] });
    void queryClient.invalidateQueries({ queryKey: ["ticket", ticket.id, "activity"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const onError = (e: unknown) => toast(errorMessage(e), "error");
  return {
    update: useMutation({ mutationFn: ({ id, patch }: { id: string; patch: StepPatch }) => api.tickets.steps.update(ticket.id, id, patch), onSuccess: apply, onError }),
    add: useMutation({ mutationFn: (body: { description: string; details?: string; technical_details?: string }) => api.tickets.steps.add(ticket.id, body), onSuccess: (s) => { apply(s); toast("Step added"); }, onError }),
    remove: useMutation({ mutationFn: (id: string) => api.tickets.steps.remove(ticket.id, id), onSuccess: (s) => { apply(s); toast("Step removed"); }, onError }),
    reorder: useMutation({ mutationFn: (ids: string[]) => api.tickets.steps.reorder(ticket.id, ids), onSuccess: (s) => { apply(s); toast("Plan reordered"); }, onError }),
    restore: useMutation({ mutationFn: () => api.tickets.steps.restore(ticket.id), onSuccess: (s) => { apply(s); toast("AI suggestions restored"); }, onError }),
  };
}

function SourceTag({ step }: { step: Step }) {
  if (step.source === "ai" && !step.edited) return <span className="inline-flex items-center gap-0.5 font-label-code text-[10px] text-secondary" title="AI suggested"><Icon name="auto_awesome" className="text-[12px]" />AI</span>;
  if (step.source === "ai" && step.edited) return <span className="inline-flex items-center gap-0.5 font-label-code text-[10px] text-on-surface-variant" title="AI suggested, edited by an engineer"><Icon name="edit" className="text-[12px]" />Edited</span>;
  return <span className="inline-flex items-center gap-0.5 font-label-code text-[10px] text-on-surface-variant" title={step.created_by ? `Added by ${step.created_by.name}` : "Added by an engineer"}><Icon name="person" className="text-[12px]" />{step.created_by?.name.split(" ")[0] ?? "Engineer"}</span>;
}

function TechnicalDetails({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const toast = useToast();
  return (
    <div className="pt-1">
      <button type="button" onClick={() => setOpen((v) => !v)} className="inline-flex items-center gap-1 font-label-code text-[11px] text-on-surface-variant transition-colors hover:text-on-surface" aria-expanded={open}>
        <Icon name="expand_more" className={clsx("text-[14px] transition-transform", open && "rotate-180")} />
        <span>View technical details</span>
      </button>
      {open && (
        <div className="mt-2 flex items-start justify-between gap-2 rounded bg-inverse-surface p-space-sm font-label-code text-label-code text-inverse-on-surface">
          <code className="select-all whitespace-pre-wrap break-all text-[11px] text-tertiary-fixed">{text}</code>
          <button
            type="button"
            className="ml-2 flex shrink-0 items-center gap-1 text-[11px] text-inverse-primary hover:text-white"
            onClick={() =>
              void navigator.clipboard.writeText(text).then(() => {
                setCopied(true);
                toast("Copied — run it yourself after reviewing");
                window.setTimeout(() => setCopied(false), 2000);
              })
            }
          >
            <Icon name={copied ? "check" : "content_copy"} className="text-[14px]" />
            <span>{copied ? "Copied" : "Copy"}</span>
          </button>
        </div>
      )}
      {open && <p className="mt-1 font-body-sm text-[11px] text-outline">Nexa never runs commands. Review before executing.</p>}
    </div>
  );
}

function StepEditor({ step, onSave, onCancel, busy }: { step?: Step; onSave: (v: { description: string; details: string; technical_details: string }) => void; onCancel: () => void; busy: boolean }) {
  const [description, setDescription] = useState(step?.description ?? "");
  const [details, setDetails] = useState(step?.details ?? "");
  const [tech, setTech] = useState(step?.technical_details ?? "");
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (description.trim()) onSave({ description: description.trim(), details: details.trim(), technical_details: tech.trim() });
  };
  return (
    <form onSubmit={submit} className="flex flex-col gap-space-sm rounded border border-outline-variant/40 bg-surface-container-lowest p-space-md">
      <input autoFocus className="input h-9" placeholder="What should be done? e.g. Verify certificate validity" value={description} onChange={(e) => setDescription(e.target.value)} maxLength={300} aria-label="Step description" />
      <input className="input h-9" placeholder="Details (optional): what to check or what good looks like" value={details} onChange={(e) => setDetails(e.target.value)} maxLength={2000} aria-label="Step details" />
      <textarea className="input h-16 resize-none py-2 font-label-code text-label-code" placeholder="Technical details (optional): commands or paths to run manually" value={tech} onChange={(e) => setTech(e.target.value)} maxLength={4000} aria-label="Technical details" />
      <div className="flex items-center justify-end gap-space-sm">
        <button type="button" className="btn-ghost h-7 px-2.5" onClick={onCancel}>Cancel</button>
        <button type="submit" className="btn-primary h-7 px-3" disabled={!description.trim() || busy}>{busy ? <Spinner className="border-t-white" /> : step ? "Save step" : "Add step"}</button>
      </div>
    </form>
  );
}

function NoteEditor({ step, onSave, onCancel, busy }: { step: Step; onSave: (note: string | null) => void; onCancel: () => void; busy: boolean }) {
  const [note, setNote] = useState(step.notes ?? "");
  return (
    <div className="flex flex-col gap-space-xs pl-9 pt-1">
      <textarea autoFocus className="input h-16 resize-none py-2" placeholder="What did you find? (visible to engineers only)" value={note} onChange={(e) => setNote(e.target.value)} aria-label="Step note" />
      <div className="flex items-center justify-end gap-space-sm">
        <button type="button" className="btn-ghost h-7 px-2.5" onClick={onCancel}>Cancel</button>
        <button type="button" className="btn-primary h-7 px-3" disabled={busy} onClick={() => onSave(note.trim() || null)}>{busy ? <Spinner className="border-t-white" /> : "Save note"}</button>
      </div>
    </div>
  );
}

function StepMenu({ step, onAction }: { step: Step; onAction: (a: "start" | "skip" | "unskip" | "note" | "delete") => void }) {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("click", close);
    return () => window.removeEventListener("click", close);
  }, [open]);
  const items: { key: "start" | "skip" | "unskip" | "note" | "delete"; label: string; icon: string }[] = [
    ...(step.status === "pending" ? [{ key: "start" as const, label: "Mark in progress", icon: "play_arrow" }] : []),
    ...(step.status !== "skipped" && step.status !== "completed" ? [{ key: "skip" as const, label: "Skip step", icon: "redo" }] : []),
    ...(step.status === "skipped" ? [{ key: "unskip" as const, label: "Un-skip", icon: "undo" }] : []),
    { key: "note", label: step.notes ? "Edit note" : "Add note", icon: "sticky_note_2" },
    { key: "delete", label: "Delete step", icon: "delete" },
  ];
  return (
    <div className="relative">
      <button type="button" onClick={(e) => { e.stopPropagation(); setOpen((v) => !v); }} className="rounded px-1 py-1 text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface" aria-label="More step actions">
        <Icon name="more_horiz" className="text-[18px]" />
      </button>
      {open && (
        <div className="absolute right-0 z-20 mt-1 w-44 overflow-hidden rounded-md border border-outline-variant/40 bg-surface-container-lowest shadow-lg" role="menu">
          {items.map((i) => (
            <button key={i.key} type="button" role="menuitem" onClick={() => onAction(i.key)} className={clsx("flex w-full items-center gap-space-sm px-space-md py-2 text-left font-body-sm text-body-sm hover:bg-surface-container-low", i.key === "delete" ? "text-error" : "text-on-surface")}>
              <Icon name={i.icon} className="text-[16px]" /> {i.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function StepRow({ step, ticket, canWork, afterCurrent }: { step: Step; ticket: TicketDetail; canWork: boolean; afterCurrent: boolean }) {
  const m = useStepMutations(ticket);
  const [editing, setEditing] = useState(false);
  const [noting, setNoting] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const done = step.status === "completed";
  const skipped = step.status === "skipped";
  const busy = m.update.isPending;
  const toggle = () => canWork && m.update.mutate({ id: step.id, patch: { status: done ? "pending" : "completed" } });
  const action = (a: "start" | "skip" | "unskip" | "note" | "delete") => {
    if (a === "start") m.update.mutate({ id: step.id, patch: { status: "in_progress" } });
    if (a === "skip") m.update.mutate({ id: step.id, patch: { status: "skipped" } });
    if (a === "unskip") m.update.mutate({ id: step.id, patch: { status: "pending" } });
    if (a === "note") setNoting(true);
    if (a === "delete") setConfirmDelete(true);
  };

  if (editing) {
    return (
      <StepEditor
        step={step}
        busy={busy}
        onCancel={() => setEditing(false)}
        onSave={(v) => m.update.mutate({ id: step.id, patch: { description: v.description, details: v.details || null, technical_details: v.technical_details || null } }, { onSuccess: () => setEditing(false) })}
      />
    );
  }

  const deleteModal = (
    <Modal
      open={confirmDelete}
      onClose={() => setConfirmDelete(false)}
      title="Delete this step?"
      footer={
        <>
          <button type="button" className="btn-ghost h-8 px-3" onClick={() => setConfirmDelete(false)}>Cancel</button>
          <button type="button" className="btn-primary h-8 px-4" disabled={m.remove.isPending} onClick={() => m.remove.mutate(step.id, { onSuccess: () => setConfirmDelete(false) })}>Delete step</button>
        </>
      }
    >
      <p className="font-body-md text-body-md text-on-surface-variant">“{step.description}” will be removed from the plan. The change is recorded in the activity log{step.source === "ai" ? ", and you can bring AI steps back with “Restore AI suggestions”" : ""}.</p>
    </Modal>
  );

  if (step.is_current && canWork) {
    return (
      <div className="flex flex-col gap-space-sm rounded border border-outline-variant/30 bg-surface-container-lowest p-space-md shadow-[0_1px_4px_rgba(0,0,0,0.03)]" data-testid={`step-${step.id}`}>
        <div className="flex items-start justify-between gap-space-md">
          <div className="flex flex-1 items-start gap-space-md">
            <button type="button" onClick={toggle} disabled={busy} className="mt-0.5 flex items-center justify-center text-primary hover:text-secondary" aria-label={`Mark “${step.description}” complete`}>
              <Icon name="check_box_outline_blank" className="text-[20px]" />
            </button>
            <div className="flex flex-1 flex-col gap-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-body-md text-body-md font-semibold text-on-surface">{step.description}</span>
                <span className="inline-flex items-center gap-1 rounded bg-secondary-fixed px-1.5 py-0.5 font-label-code text-[10px] font-medium text-on-secondary-fixed-variant">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-secondary" />
                  {step.status === "in_progress" ? "In progress" : "Current step"}
                </span>
                <SourceTag step={step} />
              </div>
              {step.details && <p className="font-body-sm text-body-sm text-on-surface-variant">{step.details}</p>}
              {step.notes && !noting && <p className="rounded bg-surface-container-low px-2 py-1 font-body-sm text-body-sm text-on-surface"><Icon name="sticky_note_2" className="mr-1 align-[-2px] text-[13px] text-outline" />{step.notes}</p>}
              {step.technical_details && <TechnicalDetails text={step.technical_details} />}
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button type="button" onClick={toggle} disabled={busy} className="h-7 rounded bg-primary px-2.5 font-body-sm text-body-sm font-medium text-on-primary transition-colors hover:bg-primary-container disabled:opacity-60">
              {busy ? <Spinner className="border-t-white" /> : "Mark complete"}
            </button>
            <button type="button" onClick={() => setEditing(true)} className="px-1.5 py-1 font-body-sm text-[12px] text-on-surface-variant hover:text-on-surface">Edit</button>
            <StepMenu step={step} onAction={action} />
          </div>
        </div>
        {noting && <NoteEditor step={step} busy={busy} onCancel={() => setNoting(false)} onSave={(n) => m.update.mutate({ id: step.id, patch: { notes: n } }, { onSuccess: () => setNoting(false) })} />}
        {deleteModal}
      </div>
    );
  }

  return (
    <div className="group flex flex-col rounded p-space-sm transition-colors hover:bg-surface-container-low" data-testid={`step-${step.id}`}>
      <div className="flex items-center justify-between gap-space-md">
        <div className="flex min-w-0 items-center gap-space-md">
          <button type="button" onClick={toggle} disabled={!canWork || busy || skipped} className={clsx("flex items-center justify-center", done ? "text-secondary" : "text-outline")} aria-label={done ? `Mark “${step.description}” not done` : `Mark “${step.description}” complete`}>
            <Icon name={done ? "check_box" : skipped ? "indeterminate_check_box" : "check_box_outline_blank"} filled={done} className="text-[20px]" />
          </button>
          <div className="flex min-w-0 flex-col">
            <div className="flex items-center gap-space-sm">
              <span className={clsx("font-body-md text-body-md", done || skipped ? "text-on-surface-variant line-through" : "text-on-surface")}>{step.description}</span>
              <SourceTag step={step} />
            </div>
            {step.notes && !noting && <span className="truncate font-body-sm text-body-sm text-on-surface-variant"><Icon name="sticky_note_2" className="mr-1 align-[-2px] text-[13px] text-outline" />{step.notes}</span>}
          </div>
        </div>
        <div className="flex items-center gap-space-sm">
          <span className="font-label-code text-[11px] text-outline">
            {done && step.completed_at ? `Completed · ${timeOfDay(step.completed_at)}` : skipped ? "Skipped" : step.status === "in_progress" ? "In progress" : afterCurrent ? "Pending previous" : "Pending"}
          </span>
          {canWork && (
            <div className="flex items-center opacity-0 transition-opacity focus-within:opacity-100 group-hover:opacity-100">
              <button type="button" onClick={() => setEditing(true)} className="px-1 font-body-sm text-[12px] text-on-surface-variant hover:text-on-surface">Edit</button>
              <StepMenu step={step} onAction={action} />
            </div>
          )}
        </div>
      </div>
      {step.technical_details && !done && !skipped && <div className="pl-9"><TechnicalDetails text={step.technical_details} /></div>}
      {noting && <NoteEditor step={step} busy={busy} onCancel={() => setNoting(false)} onSave={(n) => m.update.mutate({ id: step.id, patch: { notes: n } }, { onSuccess: () => setNoting(false) })} />}
      {deleteModal}
    </div>
  );
}

function SortableStep({ step, index, count, onMove }: { step: Step; index: number; count: number; onMove: (from: number, to: number) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id: step.id });
  return (
    <div ref={setNodeRef} style={{ transform: CSS.Transform.toString(transform), transition }} className={clsx("flex items-center gap-space-sm rounded border border-outline-variant/30 bg-surface-container-lowest p-space-sm", isDragging && "shadow-md")}>
      <button type="button" {...attributes} {...listeners} className="cursor-grab text-on-surface-variant" aria-label={`Drag to reorder “${step.description}”`}>
        <Icon name="drag_indicator" className="text-[18px]" />
      </button>
      <span className="w-6 font-label-code text-label-code text-outline">{String(index + 1).padStart(2, "0")}</span>
      <span className="flex-1 truncate font-body-md text-body-md text-on-surface">{step.description}</span>
      <button type="button" disabled={index === 0} onClick={() => onMove(index, index - 1)} className="rounded p-1 text-on-surface-variant hover:bg-surface-container-low disabled:opacity-30" aria-label="Move up"><Icon name="arrow_upward" className="text-[16px]" /></button>
      <button type="button" disabled={index === count - 1} onClick={() => onMove(index, index + 1)} className="rounded p-1 text-on-surface-variant hover:bg-surface-container-low disabled:opacity-30" aria-label="Move down"><Icon name="arrow_downward" className="text-[16px]" /></button>
    </div>
  );
}

export function StepsSection({ ticket }: { ticket: TicketDetail }) {
  const m = useStepMutations(ticket);
  const canWork = ticket.permissions.can_work;
  const [adding, setAdding] = useState(false);
  const [reordering, setReordering] = useState(false);
  const [order, setOrder] = useState<Step[]>(ticket.steps);
  const [confirmRestore, setConfirmRestore] = useState(false);
  const sensors = useSensors(useSensor(PointerSensor), useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }));
  useEffect(() => {
    if (!reordering) setOrder(ticket.steps);
  }, [ticket.steps, reordering]);

  const steps = ticket.steps;
  const pending = steps.filter((s) => s.status === "pending" || s.status === "in_progress").length;
  const currentIndex = steps.findIndex((s) => s.is_current);
  const hasAi = steps.some((s) => s.source === "ai" && s.edited);
  const investigating = ticket.ai_status === "pending" || ticket.ai_status === "running";

  const onDragEnd = (e: DragEndEvent) => {
    if (!e.over || e.active.id === e.over.id) return;
    const from = order.findIndex((s) => s.id === e.active.id);
    const to = order.findIndex((s) => s.id === e.over?.id);
    setOrder((o) => arrayMove(o, from, to));
  };

  return (
    <section className="flex flex-col gap-space-md pt-space-xs">
      <div className="flex flex-wrap items-baseline justify-between gap-space-sm border-b border-surface-container-high pb-2">
        <div className="flex items-center gap-space-sm">
          <h2 className="font-headline-sm text-headline-sm font-semibold text-on-surface">Suggested next steps</h2>
          {steps.length > 0 && <span className="rounded bg-surface-container-high px-2 py-0.5 font-label-code text-[11px] font-medium text-on-surface-variant">{pending} of {steps.length} pending</span>}
        </div>
        <p className="font-body-sm text-body-sm text-outline">AI suggested — engineer executes</p>
      </div>

      {steps.length === 0 && !adding && (
        <p className="rounded bg-surface-container-low p-space-md font-body-md text-body-md text-on-surface-variant">
          {investigating ? "The AI is preparing a resolution plan…" : ticket.ai_status === "failed" ? "No AI plan — add the steps you'll take." : "No steps yet. Add the steps you'll take to resolve this."}
        </p>
      )}

      {reordering ? (
        <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={onDragEnd}>
          <SortableContext items={order.map((s) => s.id)} strategy={verticalListSortingStrategy}>
            <div className="flex flex-col gap-2">
              {order.map((s, i) => (
                <SortableStep key={s.id} step={s} index={i} count={order.length} onMove={(from, to) => setOrder((o) => arrayMove(o, from, to))} />
              ))}
            </div>
          </SortableContext>
        </DndContext>
      ) : (
        <div className="flex flex-col gap-2" data-testid="steps-list">
          {steps.map((s, i) => (
            <StepRow key={s.id} step={s} ticket={ticket} canWork={canWork} afterCurrent={currentIndex >= 0 && i > currentIndex} />
          ))}
        </div>
      )}

      {adding && <StepEditor busy={m.add.isPending} onCancel={() => setAdding(false)} onSave={(v) => m.add.mutate({ description: v.description, details: v.details || undefined, technical_details: v.technical_details || undefined }, { onSuccess: () => setAdding(false) })} />}

      {canWork && (
        <div className="flex flex-wrap items-center gap-space-md pt-space-xs font-body-sm text-body-sm text-on-surface-variant">
          {reordering ? (
            <>
              <button type="button" className="btn-primary h-7 px-3" disabled={m.reorder.isPending} onClick={() => m.reorder.mutate(order.map((s) => s.id), { onSuccess: () => setReordering(false) })}>
                {m.reorder.isPending ? <Spinner className="border-t-white" /> : "Save order"}
              </button>
              <button type="button" className="hover:text-on-surface" onClick={() => { setOrder(steps); setReordering(false); }}>Cancel</button>
            </>
          ) : (
            <>
              <button type="button" className="flex items-center gap-1 transition-colors hover:text-on-surface" onClick={() => setAdding(true)}>
                <Icon name="add" className="text-[16px]" /><span>Add step</span>
              </button>
              {steps.length > 1 && (
                <>
                  <span className="text-outline-variant">•</span>
                  <button type="button" className="flex items-center gap-1 transition-colors hover:text-on-surface" onClick={() => setReordering(true)}>
                    <Icon name="drag_indicator" className="text-[16px]" /><span>Reorder</span>
                  </button>
                </>
              )}
              {(hasAi || ticket.steps.some((s) => s.source === "ai")) && (
                <>
                  <span className="text-outline-variant">•</span>
                  <button type="button" className="flex items-center gap-1 transition-colors hover:text-on-surface" onClick={() => setConfirmRestore(true)}>
                    <Icon name="history" className="text-[16px]" /><span>Restore AI suggestions</span>
                  </button>
                </>
              )}
            </>
          )}
        </div>
      )}

      <Modal
        open={confirmRestore}
        onClose={() => setConfirmRestore(false)}
        title="Restore AI suggestions?"
        footer={
          <>
            <button type="button" className="btn-ghost h-8 px-3" onClick={() => setConfirmRestore(false)}>Cancel</button>
            <button type="button" className="btn-primary h-8 px-4" disabled={m.restore.isPending} onClick={() => m.restore.mutate(undefined, { onSuccess: () => setConfirmRestore(false) })}>Restore</button>
          </>
        }
      >
        <p className="font-body-md text-body-md text-on-surface-variant">Deleted AI steps come back and edited AI steps return to their original wording. Steps you added and every completion are kept.</p>
      </Modal>
    </section>
  );
}
