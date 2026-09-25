/**
 * Live AI investigation stages. These are workflow stages reported by the
 * backend — not model reasoning. Polls while the investigation runs.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import type { Progress } from "@/lib/types";
import { Icon, Spinner } from "./ui";

export function useInvestigationProgress(ticketId: string | null | undefined, onSettled?: (p: Progress) => void) {
  const queryClient = useQueryClient();
  const settledRef = useRef(false);
  const query = useQuery({
    queryKey: ["progress", ticketId],
    queryFn: () => api.tickets.progress(ticketId as string),
    enabled: Boolean(ticketId),
    refetchInterval: (q) => {
      const status = q.state.data?.ai_status;
      return status === "pending" || status === "running" || !status ? 1500 : false;
    },
  });
  const status = query.data?.ai_status;
  useEffect(() => {
    if (!query.data || settledRef.current) return;
    if (status === "completed" || status === "failed" || status === "skipped") {
      settledRef.current = true;
      onSettled?.(query.data);
      void queryClient.invalidateQueries({ queryKey: ["ticket", ticketId] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    }
  }, [status, query.data, onSettled, queryClient, ticketId]);
  return query;
}

export function StageList({ progress, compact }: { progress: Progress; compact?: boolean }) {
  return (
    <ol className={clsx("flex flex-col", compact ? "gap-1" : "gap-1.5")} aria-label="Investigation progress">
      {progress.stages.map((stage) => (
        <li key={stage.key} className="flex items-center gap-space-sm font-body-sm text-body-sm">
          {stage.state === "done" && <Icon name="check_circle" filled className="text-[16px] text-on-tertiary-container" />}
          {stage.state === "active" && <Spinner className="h-3.5 w-3.5" />}
          {stage.state === "pending" && <span className="mx-[3px] h-2.5 w-2.5 rounded-full border border-outline-variant" />}
          {stage.state === "failed" && <Icon name="error" className="text-[16px] text-error" />}
          {stage.state === "skipped" && <Icon name="remove" className="text-[16px] text-outline" />}
          <span className={clsx(stage.state === "active" ? "font-medium text-on-surface" : stage.state === "pending" ? "text-outline" : "text-on-surface-variant")}>{stage.label}</span>
        </li>
      ))}
    </ol>
  );
}

/** Compact line + stages used inside the assistant conversation. */
export function InvestigationProgress({ ticketId, typeLabel }: { ticketId: string; typeLabel: string }) {
  const query = useInvestigationProgress(ticketId);
  const p = query.data;
  if (query.isError) return <p className="font-body-sm text-body-sm text-on-surface-variant">Live status is unavailable right now — your ticket is saved.</p>;
  if (!p) {
    return (
      <div className="flex items-center gap-space-sm font-body-sm text-body-sm text-on-surface-variant">
        <Spinner /> Checking status…
      </div>
    );
  }
  const running = p.ai_status === "pending" || p.ai_status === "running";
  const routed = p.team ? `${p.team.name}${p.assignee ? ` · ${p.assignee.name} is handling it` : " queue"}` : null;
  return (
    <div className="flex flex-col gap-space-sm">
      {running && (
        <div className="nx-ai nx-scan overflow-hidden rounded-lg p-space-md">
          <p className="label-caps mb-space-sm text-on-surface-variant">AI investigation in progress</p>
          <StageList progress={p} compact />
        </div>
      )}
      {!running && (
        <div className="flex items-start gap-space-xs rounded-lg bg-surface-container-high/40 p-space-sm font-body-md text-body-md text-on-surface">
          <Icon name={p.ai_status === "failed" ? "info" : "check_circle"} className={clsx("mt-0.5 shrink-0 text-[16px]", p.ai_status === "failed" ? "text-on-surface-variant" : "text-on-tertiary-container")} />
          <span>
            {typeLabel}{" "}
            <span className="rounded bg-surface-container-lowest px-1.5 py-0.5 font-label-code text-label-code font-medium text-on-surface">{p.ticket_number}</span>{" "}
            {routed ? <>has been assigned to {routed}.</> : <>has been created and is waiting for the IT team.</>}
            {p.ai_status === "failed" && " I couldn't finish the automated analysis, but an engineer will take it from here."}
          </span>
        </div>
      )}
    </div>
  );
}
