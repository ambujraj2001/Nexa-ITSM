import type { Priority, SlaInfo, TicketStatus } from "./types";

export function timeOfDay(iso: string): string {
  return new Date(iso).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function shortDate(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  if (date.toDateString() === today.toDateString()) return `Today, ${timeOfDay(iso)}`;
  const yesterday = new Date(today);
  yesterday.setDate(today.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return `Yesterday, ${timeOfDay(iso)}`;
  return date.toLocaleDateString([], { month: "short", day: "numeric" }) + `, ${timeOfDay(iso)}`;
}

export function relative(iso: string | null | undefined): string {
  if (!iso) return "";
  const seconds = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 14) return `${days}d ago`;
  const weeks = Math.round(days / 7);
  if (weeks < 9) return `${weeks}w ago`;
  return `${Math.round(days / 30)}mo ago`;
}

export const PRIORITY_LABEL: Record<Priority, string> = { P1: "Urgent", P2: "High", P3: "Normal", P4: "Low" };

export function slaTone(sla: SlaInfo): "error" | "accent" | "muted" | "success" {
  if (sla.state === "breached" || sla.state === "missed") return "error";
  if (sla.state === "due_soon" || sla.state === "at_risk") return "accent";
  if (sla.state === "met") return "success";
  return "muted";
}

export function isOpen(status: TicketStatus): boolean {
  return status !== "resolved" && status !== "closed";
}

export function initials(name: string): string {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  return ((parts[0]?.[0] ?? "") + (parts.length > 1 ? parts[parts.length - 1][0] : "")).toUpperCase() || "?";
}

export function pluralize(n: number, word: string, plural = `${word}s`): string {
  return `${n} ${n === 1 ? word : plural}`;
}

export function fileSize(bytes: number | null | undefined): string {
  if (!bytes) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
