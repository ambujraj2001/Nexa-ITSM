/** Small presentational primitives shared across screens (Calm Precision tokens). */
import clsx from "clsx";
import { useEffect, useRef, type ReactNode } from "react";
import { initials } from "@/lib/format";
import type { Priority, TicketStatus } from "@/lib/types";

export function Icon({ name, className, filled, label }: { name: string; className?: string; filled?: boolean; label?: string }) {
  return (
    <span className={clsx("material-symbols-outlined", filled && "filled", className)} aria-hidden={label ? undefined : true} aria-label={label} role={label ? "img" : undefined}>
      {name}
    </span>
  );
}

/** Geometric N monogram — replaces the remote logo image used in the mockups. */
export function NexaMark({ size = 32 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
      <rect width="32" height="32" rx="7" fill="#0b1c30" />
      <path d="M9 23V9h2.6l7.8 9.6V9H22v14h-2.6l-7.8-9.6V23z" fill="#fff" />
      <circle cx="24.5" cy="8.5" r="2.5" fill="#6063ee" />
    </svg>
  );
}

export function Wordmark({ badge = "ITSM" }: { badge?: string }) {
  return (
    <div className="flex items-center gap-space-sm">
      <NexaMark />
      <span className="font-headline-sm text-headline-sm font-semibold tracking-tight text-on-surface">Nexa</span>
      <span className="rounded bg-surface-container-high px-1.5 py-0.5 font-label-code text-label-code font-medium text-on-surface-variant">{badge}</span>
    </div>
  );
}

export function Avatar({ name, url, size = 32, className }: { name: string; url?: string | null; size?: number; className?: string }) {
  if (url) {
    return <img src={url} alt="" width={size} height={size} className={clsx("rounded-full object-cover", className)} style={{ width: size, height: size }} />;
  }
  return (
    <span
      className={clsx("inline-flex items-center justify-center rounded-full bg-primary-container font-label-code font-semibold text-on-primary", className)}
      style={{ width: size, height: size, fontSize: Math.max(10, size * 0.36) }}
      aria-hidden="true"
    >
      {initials(name)}
    </span>
  );
}

const PRIORITY_STYLE: Record<Priority, { chip: string; dot: string; text: string; label: string }> = {
  P1: { chip: "bg-error-container text-on-error-container", dot: "bg-error", text: "text-error", label: "P1 Urgent" },
  P2: { chip: "bg-secondary-fixed text-on-secondary-fixed", dot: "bg-secondary", text: "text-secondary", label: "P2 High" },
  P3: { chip: "bg-surface-container-high text-on-surface", dot: "bg-outline", text: "text-on-surface-variant", label: "P3 Normal" },
  P4: { chip: "bg-surface-container-high text-on-surface-variant", dot: "bg-outline-variant", text: "text-on-surface-variant", label: "P4 Low" },
};

export function PriorityChip({ priority, compact }: { priority: Priority; compact?: boolean }) {
  const style = PRIORITY_STYLE[priority];
  return (
    <span className={clsx("chip", style.chip)}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", style.dot)} />
      {compact ? priority : style.label}
    </span>
  );
}

export function PriorityDot({ priority }: { priority: Priority }) {
  const style = PRIORITY_STYLE[priority];
  return (
    <span className={clsx("flex items-center gap-space-xs font-label-code text-label-code", style.text)}>
      <span className={clsx("h-2 w-2 rounded-full", style.dot)} />
      <span className="font-medium">{priority}</span>
    </span>
  );
}

const STATUS_STYLE: Partial<Record<TicketStatus, string>> = {
  in_progress: "bg-secondary-fixed text-on-secondary-fixed-variant",
  escalated: "bg-secondary-fixed text-on-secondary-fixed-variant",
  pending_engineer: "bg-error-container text-on-error-container",
  reopened: "bg-error-container text-on-error-container",
  resolved: "bg-tertiary-fixed/40 text-on-tertiary-fixed-variant",
  closed: "bg-surface-container-high text-on-surface-variant",
};

export function StatusChip({ status, label }: { status: TicketStatus; label: string }) {
  const tone = STATUS_STYLE[status] ?? "bg-surface-container-high text-on-surface-variant";
  const dot = status === "in_progress" || status === "escalated" ? "bg-secondary" : status === "resolved" ? "bg-on-tertiary-container" : status === "pending_engineer" || status === "reopened" ? "bg-error" : "bg-outline";
  return (
    <span className={clsx("chip", tone)}>
      <span className={clsx("h-1.5 w-1.5 rounded-full", dot)} />
      {label}
    </span>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <span className={clsx("inline-block h-4 w-4 animate-spin rounded-full border-2 border-outline-variant border-t-secondary", className)} aria-hidden="true" />;
}

export function LoadingState({ label = "Loading…", className }: { label?: string; className?: string }) {
  return (
    <div role="status" className={clsx("flex items-center justify-center gap-space-sm py-space-xl font-body-md text-body-md text-on-surface-variant", className)}>
      <Spinner />
      <span>{label}</span>
    </div>
  );
}

export function ErrorState({ title = "Something went wrong.", message, onRetry, className }: { title?: string; message?: string; onRetry?: () => void; className?: string }) {
  return (
    <div role="alert" className={clsx("flex flex-col items-center gap-space-sm rounded-xl bg-surface-container-lowest px-space-lg py-space-xl text-center shadow-sm", className)}>
      <Icon name="error" className="text-[22px] text-error" />
      <p className="font-headline-sm text-headline-sm text-on-surface">{title}</p>
      {message && <p className="max-w-md font-body-md text-body-md text-on-surface-variant">{message}</p>}
      {onRetry && (
        <button type="button" onClick={onRetry} className="btn-ghost mt-space-xs h-8 px-3">
          <Icon name="refresh" className="text-[16px]" /> Try again
        </button>
      )}
    </div>
  );
}

export function EmptyState({ icon = "inbox", title, message, action, className }: { icon?: string; title: string; message?: string; action?: ReactNode; className?: string }) {
  return (
    <div className={clsx("flex flex-col items-center gap-space-sm px-space-lg py-space-xl text-center", className)}>
      <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-surface-container-low text-on-surface-variant">
        <Icon name={icon} className="text-[20px]" />
      </span>
      <p className="font-headline-sm text-headline-sm text-on-surface">{title}</p>
      {message && <p className="max-w-md font-body-md text-body-md text-on-surface-variant">{message}</p>}
      {action}
    </div>
  );
}

export function Toggle({ checked, onChange, disabled, label, id }: { checked: boolean; onChange?: (value: boolean) => void; disabled?: boolean; label: string; id?: string }) {
  return (
    <label className={clsx("relative inline-flex shrink-0 items-center", disabled ? "cursor-not-allowed" : "cursor-pointer")}>
      <input id={id} type="checkbox" className="peer sr-only" checked={checked} disabled={disabled} onChange={(e) => onChange?.(e.target.checked)} aria-label={label} />
      <div
        className={clsx(
          "h-6 w-11 rounded-full bg-surface-container-high transition-colors peer-checked:bg-primary peer-focus-visible:ring-2 peer-focus-visible:ring-secondary",
          "after:absolute after:left-[2px] after:top-[2px] after:h-5 after:w-5 after:rounded-full after:border after:border-surface-container-highest after:bg-white after:transition-all after:content-['']",
          "peer-checked:after:translate-x-full peer-checked:after:border-white",
          disabled && "opacity-50",
        )}
      />
    </label>
  );
}

export function Modal({ open, onClose, title, children, footer, width = "max-w-md" }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; width?: string }) {
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    panel.current?.querySelector<HTMLElement>("textarea, input, select, button")?.focus();
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-primary/20 p-4 backdrop-blur-sm" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={panel} role="dialog" aria-modal="true" aria-label={title} className={clsx("flex w-full flex-col gap-space-md rounded-lg bg-surface-container-lowest p-space-lg shadow-xl animate-fade-in", width)}>
        <div className="flex items-center justify-between">
          <h3 className="font-headline-sm text-headline-sm font-semibold text-on-surface">{title}</h3>
          <button type="button" onClick={onClose} className="rounded p-1 text-on-surface-variant hover:text-on-surface" aria-label="Close">
            <Icon name="close" className="text-[18px]" />
          </button>
        </div>
        {children}
        {footer && <div className="flex items-center justify-end gap-space-sm pt-space-xs">{footer}</div>}
      </div>
    </div>
  );
}

export function FieldLabel({ children, htmlFor }: { children: ReactNode; htmlFor?: string }) {
  return (
    <label htmlFor={htmlFor} className="font-body-sm text-body-sm text-on-surface-variant">
      {children}
    </label>
  );
}
