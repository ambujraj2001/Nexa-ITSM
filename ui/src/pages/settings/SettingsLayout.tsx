import clsx from "clsx";
import { NavLink, Outlet } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { Icon } from "@/components/ui";
import type { Role } from "@/lib/types";

const SECTIONS: { to: string; label: string; icon: string; roles: Role[] }[] = [
  { to: "/settings/ai", label: "AI & Automation", icon: "auto_awesome", roles: ["engineer", "admin"] },
  { to: "/settings/teams", label: "Teams & Users", icon: "group", roles: ["engineer", "admin"] },
  { to: "/settings/rules", label: "Assignment Rules", icon: "rule_folder", roles: ["engineer", "admin"] },
  { to: "/settings/sla", label: "SLA Policies", icon: "timer", roles: ["engineer", "admin"] },
  { to: "/settings/knowledge-sources", label: "Knowledge Sources", icon: "database", roles: ["engineer", "admin"] },
  { to: "/settings/integrations", label: "Integrations", icon: "extension", roles: ["admin"] },
  { to: "/settings/security", label: "Security & Compliance", icon: "verified_user", roles: ["engineer", "admin"] },
  { to: "/settings/audit", label: "Audit Log", icon: "receipt_long", roles: ["admin"] },
  { to: "/settings/profile", label: "Profile", icon: "person", roles: ["employee", "engineer", "admin"] },
];

export function SettingsLayout() {
  const { me } = useAuth();
  const items = SECTIONS.filter((s) => me && s.roles.includes(me.role));
  return (
    <div className="flex min-h-[calc(100vh-3.5rem)] flex-1 px-gutter py-space-xl">
      <div className="mx-auto flex w-full max-w-7xl flex-col items-start gap-space-xl md:flex-row">
        <aside className="flex w-full shrink-0 flex-col gap-space-md md:w-64">
          <div className="px-space-sm pb-space-xs">
            <h1 className="font-headline-md text-headline-md font-semibold tracking-tight text-on-surface">Settings</h1>
            <p className="font-body-sm text-body-sm text-on-surface-variant">{me?.role === "employee" ? "Your profile" : "System preferences & governance"}</p>
          </div>
          <nav aria-label="Settings" className="flex flex-col gap-space-xs">
            {items.map((s) => (
              <NavLink
                key={s.to}
                to={s.to}
                className={({ isActive }) =>
                  clsx(
                    "group flex items-center justify-between rounded-lg px-space-md py-space-sm transition-all",
                    isActive ? "bg-surface-container-high font-medium text-on-surface shadow-sm" : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <div className="flex items-center gap-space-sm">
                      <Icon name={s.icon} className={clsx("text-[18px]", isActive && "text-secondary")} />
                      <span className="font-body-md text-body-md">{s.label}</span>
                    </div>
                    {isActive && <span className="h-1.5 w-1.5 rounded-full bg-secondary" />}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </aside>
        <div className="flex w-full max-w-3xl flex-1 flex-col pb-space-xl">
          <Outlet />
        </div>
      </div>
    </div>
  );
}

export function SettingsHeader({ eyebrow, title, description }: { eyebrow?: string; title: string; description: string }) {
  return (
    <header className="mb-space-xl pb-space-md">
      {eyebrow && <div className="mb-space-xs flex items-center gap-space-xs font-label-caps text-label-caps uppercase tracking-wider text-secondary">{eyebrow}</div>}
      <h2 className="font-display-lg text-display-lg font-semibold tracking-tight text-on-surface">{title}</h2>
      <p className="mt-space-xs max-w-2xl font-body-lg text-body-lg text-on-surface-variant">{description}</p>
    </header>
  );
}
