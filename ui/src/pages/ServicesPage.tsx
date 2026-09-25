/** Service catalogue and asset register (context the AI uses during investigations). */
import { useQuery } from "@tanstack/react-query";
import clsx from "clsx";
import { useState } from "react";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { relative } from "@/lib/format";

const CRITICALITY: Record<string, string> = {
  critical: "bg-error-container text-on-error-container",
  high: "bg-secondary-fixed text-on-secondary-fixed-variant",
  medium: "bg-surface-container-high text-on-surface",
  low: "bg-surface-container-high text-on-surface-variant",
};

export function ServicesPage() {
  const [tab, setTab] = useState<"services" | "assets">("services");
  const services = useQuery({ queryKey: ["services"], queryFn: api.catalog.services });
  const assets = useQuery({ queryKey: ["assets"], queryFn: () => api.catalog.assets(), enabled: tab === "assets" });
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-space-lg px-gutter py-space-xl">
      <div className="flex flex-col justify-between gap-space-md sm:flex-row sm:items-end">
        <div>
          <h1 className="font-headline-lg text-headline-lg font-semibold tracking-tight text-on-surface">Services</h1>
          <p className="font-body-md text-body-md text-on-surface-variant">Service owners, criticality and assets — used for routing and as AI investigation context.</p>
        </div>
        <div className="flex items-center gap-space-xs rounded-lg bg-surface-container-low p-1 font-body-sm text-body-sm">
          {(["services", "assets"] as const).map((t) => (
            <button key={t} type="button" onClick={() => setTab(t)} className={clsx("rounded px-space-md py-1 capitalize", tab === t ? "bg-surface-container-lowest font-medium text-on-surface shadow-sm" : "text-on-surface-variant hover:text-on-surface")}>{t}</button>
          ))}
        </div>
      </div>
      {tab === "services" && (
        <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm">
          {services.isLoading && <LoadingState label="Loading services…" />}
          {services.isError && <ErrorState className="shadow-none" title="Unable to load services." message={errorMessage(services.error)} onRetry={() => void services.refetch()} />}
          {services.data?.length === 0 && <EmptyState icon="lan" title="No services yet" message="Run the seed script or add services through the API." />}
          {services.data && services.data.length > 0 && (
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-surface-container-low/60 font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant">
                  <th className="px-space-lg py-space-md">Service</th>
                  <th className="px-space-md py-space-md">Criticality</th>
                  <th className="px-space-md py-space-md">Owner</th>
                  <th className="px-space-md py-space-md text-right">Open tickets</th>
                  <th className="px-space-lg py-space-md text-right">Assets</th>
                </tr>
              </thead>
              <tbody className="font-body-md text-body-md">
                {services.data.map((s) => (
                  <tr key={s.id} className="border-t border-surface-container-low">
                    <td className="px-space-lg py-space-md">
                      <div className="flex flex-col">
                        <span className="font-medium text-on-surface">{s.name}</span>
                        {s.description && <span className="font-body-sm text-body-sm text-on-surface-variant">{s.description}</span>}
                      </div>
                    </td>
                    <td className="px-space-md py-space-md"><span className={clsx("chip capitalize", CRITICALITY[s.criticality])}>{s.criticality}</span></td>
                    <td className="px-space-md py-space-md font-body-sm text-body-sm text-on-surface-variant">{s.owner_team?.name ?? "—"}</td>
                    <td className="px-space-md py-space-md text-right font-label-code text-label-code text-on-surface">{s.open_tickets}</td>
                    <td className="px-space-lg py-space-md text-right font-label-code text-label-code text-on-surface-variant">{s.asset_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
      {tab === "assets" && (
        <div className="overflow-hidden rounded-xl bg-surface-container-lowest shadow-sm">
          {assets.isLoading && <LoadingState label="Loading assets…" />}
          {assets.isError && <ErrorState className="shadow-none" title="Unable to load assets." onRetry={() => void assets.refetch()} />}
          {assets.data?.length === 0 && <EmptyState icon="devices" title="No assets registered" />}
          {assets.data && assets.data.length > 0 && (
            <table className="w-full border-collapse text-left">
              <thead>
                <tr className="bg-surface-container-low/60 font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant">
                  <th className="px-space-lg py-space-md">Asset</th>
                  <th className="px-space-md py-space-md">Type</th>
                  <th className="px-space-md py-space-md">Owner</th>
                  <th className="px-space-md py-space-md">Details</th>
                  <th className="px-space-lg py-space-md text-right">Updated</th>
                </tr>
              </thead>
              <tbody className="font-body-md text-body-md">
                {assets.data.map((a) => (
                  <tr key={a.id} className="border-t border-surface-container-low">
                    <td className="px-space-lg py-space-md font-medium text-on-surface">{a.name}</td>
                    <td className="px-space-md py-space-md font-body-sm text-body-sm capitalize text-on-surface-variant">{a.asset_type.replace("_", " ")}</td>
                    <td className="px-space-md py-space-md font-body-sm text-body-sm text-on-surface-variant">{a.owner?.name ?? "—"}</td>
                    <td className="px-space-md py-space-md font-label-code text-[11px] text-on-surface-variant">{Object.entries(a.metadata).map(([k, v]) => `${k}: ${String(v)}`).join(" · ")}</td>
                    <td className="px-space-lg py-space-md text-right font-label-code text-[11px] text-outline">{relative(a.updated_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
