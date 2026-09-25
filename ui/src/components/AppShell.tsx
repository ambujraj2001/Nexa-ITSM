/**
 * Authenticated layout from the reference screens: fixed 256px sidebar, 56px
 * translucent top bar, calm canvas. Navigation adapts to the user's role
 * (employees get an assistant-first experience, not an admin console).
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import clsx from "clsx";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router";
import { useAuth } from "@/auth/AuthProvider";
import { api } from "@/lib/api";
import { relative } from "@/lib/format";
import type { Me } from "@/lib/types";
import { Avatar, Icon, NexaMark, PriorityDot, Spinner, Wordmark } from "./ui";
import { Aurora } from "@/pages/landing/effects";

interface NavItem {
  to: string;
  label: string;
  icon: string;
  end?: boolean;
}

function navFor(me: Me): { main: NavItem[]; settings: NavItem } {
  if (me.role === "employee") {
    return {
      main: [
        { to: "/assistant", label: "AI Assistant", icon: "auto_awesome" },
        { to: "/my-tickets", label: "My Tickets", icon: "inbox" },
        { to: "/knowledge", label: "Knowledge", icon: "library_books" },
      ],
      settings: { to: "/settings/profile", label: "Settings", icon: "tune" },
    };
  }
  return {
    main: [
      { to: "/dispatch", label: "Overview", icon: "grid_view" },
      { to: "/assistant", label: "AI Assistant", icon: "auto_awesome" },
      { to: "/tickets/mine", label: "My Tickets", icon: "inbox" },
      { to: "/tickets/incidents", label: "Incidents", icon: "warning" },
      { to: "/tickets/requests", label: "Requests", icon: "assignment" },
      { to: "/tickets/changes", label: "Changes", icon: "published_with_changes" },
      { to: "/knowledge", label: "Knowledge", icon: "library_books" },
      { to: "/services", label: "Services", icon: "lan" },
    ],
    settings: { to: "/settings/ai", label: "Settings", icon: "tune" },
  };
}

function subtitle(me: Me): string {
  if (me.role === "admin") return me.team ? `Admin · ${me.team.name}` : "Workspace admin";
  if (me.role === "engineer") return [me.engineer_level, me.team?.name].filter(Boolean).join(" ") || "Engineer";
  return me.department || me.job_title || "Employee";
}

const SECTION_LABELS: [RegExp, string][] = [
  [/^\/dispatch/, "Operations"],
  [/^\/assistant/, "Assistant"],
  [/^\/my-tickets/, "My Tickets"],
  [/^\/tickets\/mine/, "My Tickets"],
  [/^\/tickets\/incidents/, "Incidents"],
  [/^\/tickets\/requests/, "Requests"],
  [/^\/tickets\/changes/, "Changes"],
  [/^\/tickets\//, "Workspace"],
  [/^\/knowledge/, "Knowledge"],
  [/^\/services/, "Services"],
  [/^\/settings/, "Settings"],
];

/** Where the logo and the "ITSM" breadcrumb go: the assistant for employees, Overview for staff. */
function homeFor(me: Me): string {
  return me.role === "employee" ? "/assistant" : "/dispatch";
}

function sectionLabel(pathname: string): string {
  return SECTION_LABELS.find(([re]) => re.test(pathname))?.[1] ?? "Workspace";
}

/** Instant tooltip to the right of a collapsed-rail item (desktop only). */
function RailTip({ show, children }: { show: boolean; children: string }) {
  if (!show) return null;
  return (
    <span
      role="tooltip"
      className="pointer-events-none absolute left-full top-1/2 z-[60] ml-3 hidden -translate-x-1 -translate-y-1/2 whitespace-nowrap rounded-md bg-[#0f1424] px-2.5 py-1 font-body-sm text-body-sm text-white opacity-0 shadow-[0_8px_24px_-6px_rgba(15,20,36,0.5)] transition-all duration-150 group-hover:translate-x-0 group-hover:opacity-100 group-focus-visible:translate-x-0 group-focus-visible:opacity-100 lg:block"
    >
      {children}
      <span className="absolute -left-1 top-1/2 h-2 w-2 -translate-y-1/2 rotate-45 bg-[#0f1424]" />
    </span>
  );
}

function navClass({ isActive }: { isActive: boolean }) {
  return clsx(
    "group relative flex items-center gap-space-sm rounded-lg px-space-sm py-space-sm transition-colors",
    isActive ? "bg-surface-container-low font-medium text-on-surface" : "text-on-surface-variant hover:bg-surface-container-low hover:text-on-surface",
  );
}

function UserCard({ me }: { me: Me }) {
  const { signOut } = useAuth();
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center gap-space-sm rounded-lg bg-surface-container-low px-space-sm py-space-xs text-left"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <div className="flex min-w-0 flex-1 flex-col">
          <span className="truncate font-body-md text-body-md font-medium text-on-surface">{me.name}</span>
          <span className="truncate font-label-code text-label-code text-on-surface-variant">{subtitle(me)}</span>
        </div>
        <Icon name="unfold_more" className="text-[16px] text-on-surface-variant" />
      </button>
      {open && (
        <div role="menu" className="absolute bottom-full left-0 right-0 mb-2 overflow-hidden rounded-md border border-outline-variant/40 bg-surface-container-lowest shadow-lg">
          <Link role="menuitem" to="/settings/profile" onClick={() => setOpen(false)} className="flex items-center gap-space-sm px-space-md py-2 font-body-sm text-body-sm text-on-surface hover:bg-surface-container-low">
            <Icon name="person" className="text-[16px]" /> Profile
          </Link>
          <button role="menuitem" type="button" onClick={() => void signOut()} className="flex w-full items-center gap-space-sm px-space-md py-2 text-left font-body-sm text-body-sm text-on-surface hover:bg-surface-container-low">
            <Icon name="logout" className="text-[16px]" /> Sign out
          </button>
        </div>
      )}
    </div>
  );
}

function CommandPalette({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [q, setQ] = useState("");
  const [debounced, setDebounced] = useState("");
  const navigate = useNavigate();
  const { me } = useAuth();
  useEffect(() => {
    const id = window.setTimeout(() => setDebounced(q.trim()), 200);
    return () => window.clearTimeout(id);
  }, [q]);
  useEffect(() => {
    if (!open) setQ("");
  }, [open]);
  const results = useQuery({ queryKey: ["search", debounced], queryFn: () => api.search(debounced), enabled: open && debounced.length >= 2 });
  if (!open) return null;
  const ticketPath = (id: string) => (me?.role === "employee" ? `/my-tickets/${id}` : `/tickets/${id}`);
  const go = (path: string) => {
    onClose();
    navigate(path);
  };
  return (
    <div className="fixed inset-0 z-[70] flex items-start justify-center bg-white/80 px-4 pt-[12vh] backdrop-blur-[8px]" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-label="Search" className="w-full max-w-[600px] overflow-hidden rounded-lg border border-[#CBD5E1] bg-surface-container-lowest shadow-[0_8px_30px_rgba(15,23,42,0.08)]">
        <div className="flex h-11 items-center gap-space-sm border-b border-surface-container-high px-space-md">
          <Icon name="search" className="text-[18px] text-on-surface-variant" />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={(e) => e.key === "Escape" && onClose()}
            placeholder="Search tickets and knowledge…"
            className="flex-1 bg-transparent text-[16px] text-on-surface placeholder:text-outline focus:outline-none"
          />
          <kbd className="rounded bg-surface-container-low px-1.5 font-label-code text-[10px] text-on-surface-variant">esc</kbd>
        </div>
        <div className="max-h-[60vh] overflow-y-auto p-space-sm">
          {debounced.length < 2 && <p className="px-space-sm py-space-md font-body-sm text-body-sm text-on-surface-variant">Type at least two characters — a ticket number, a title or an error message.</p>}
          {results.isFetching && (
            <div className="flex items-center gap-2 px-space-sm py-space-md font-body-sm text-body-sm text-on-surface-variant">
              <Spinner /> Searching…
            </div>
          )}
          {results.isError && <p className="px-space-sm py-space-md font-body-sm text-body-sm text-error">Search is unavailable right now.</p>}
          {results.data && (
            <>
              <p className="label-caps px-space-sm pb-1 pt-space-sm text-on-surface-variant">Tickets</p>
              {results.data.tickets.length === 0 && <p className="px-space-sm pb-space-sm font-body-sm text-body-sm text-outline">No matching tickets.</p>}
              {results.data.tickets.map((t) => (
                <button key={t.id} type="button" onClick={() => go(ticketPath(t.id))} className="flex w-full items-center gap-space-sm rounded px-space-sm py-2 text-left hover:bg-surface-container-low">
                  <PriorityDot priority={t.priority} />
                  <span className="font-label-code text-label-code font-medium text-on-surface">{t.ticket_number}</span>
                  <span className="flex-1 truncate font-body-md text-body-md text-on-surface">{t.title}</span>
                  <span className="font-label-code text-[11px] text-outline">{t.status_label}</span>
                </button>
              ))}
              <p className="label-caps px-space-sm pb-1 pt-space-md text-on-surface-variant">Knowledge</p>
              {results.data.articles.length === 0 && <p className="px-space-sm pb-space-sm font-body-sm text-body-sm text-outline">No matching articles.</p>}
              {results.data.articles.map((a) => (
                <button key={a.id} type="button" onClick={() => go(`/knowledge/${a.id}`)} className="flex w-full items-center gap-space-sm rounded px-space-sm py-2 text-left hover:bg-surface-container-low">
                  <Icon name="description" className="text-[16px] text-outline" />
                  <span className="font-label-code text-label-code text-on-surface-variant">{a.article_number}</span>
                  <span className="flex-1 truncate font-body-md text-body-md text-on-surface">{a.title}</span>
                </button>
              ))}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Notifications() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();
  const { me } = useAuth();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["notifications"], queryFn: api.notifications.list, refetchInterval: 30_000 });
  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, [open]);
  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && (query.data?.unread ?? 0) > 0) void api.notifications.seen().then(() => queryClient.invalidateQueries({ queryKey: ["notifications"] }));
  };
  const unread = query.data?.unread ?? 0;
  return (
    <div className="relative" ref={ref}>
      <button type="button" onClick={toggle} className="relative flex items-center justify-center rounded p-space-xs text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface" aria-label={unread ? `Notifications (${unread} unread)` : "Notifications"}>
        <Icon name="notifications" className="text-[18px]" />
        {unread > 0 && <span className="absolute right-1 top-1 h-1.5 w-1.5 rounded-full bg-error" />}
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 overflow-hidden rounded-md border border-outline-variant/40 bg-surface-container-lowest shadow-lg">
          <p className="label-caps border-b border-surface-container-high px-space-md py-2 text-on-surface-variant">Updates</p>
          <div className="max-h-96 overflow-y-auto">
            {query.isLoading && <p className="px-space-md py-space-md font-body-sm text-body-sm text-on-surface-variant">Loading…</p>}
            {query.isError && <p className="px-space-md py-space-md font-body-sm text-body-sm text-error">Unable to load updates.</p>}
            {query.data?.items.length === 0 && <p className="px-space-md py-space-md font-body-sm text-body-sm text-on-surface-variant">You're all caught up.</p>}
            {query.data?.items.map((n) => (
              <button
                key={n.id}
                type="button"
                onClick={() => {
                  setOpen(false);
                  if (n.ticket_id) navigate(me?.role === "employee" ? `/my-tickets/${n.ticket_id}` : `/tickets/${n.ticket_id}`);
                }}
                className="flex w-full flex-col gap-0.5 border-b border-surface-container-low px-space-md py-2 text-left hover:bg-surface-container-low"
              >
                <span className="flex items-center gap-space-xs font-label-code text-[11px] text-outline">
                  {n.unread && <span className="h-1.5 w-1.5 rounded-full bg-secondary" />}
                  {n.ticket_number} · {relative(n.at)}
                </span>
                <span className="font-body-sm text-body-sm text-on-surface">{n.summary}</span>
                {n.ticket_title && <span className="truncate font-body-sm text-body-sm text-on-surface-variant">{n.ticket_title}</span>}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function Help() {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button type="button" onClick={() => setOpen((v) => !v)} className="flex items-center justify-center rounded p-space-xs text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface" aria-label="Help">
        <Icon name="help_outline" className="text-[18px]" />
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-72 rounded-md border border-outline-variant/40 bg-surface-container-lowest p-space-md shadow-lg">
          <p className="font-headline-sm text-headline-sm text-on-surface">AI investigates. Humans resolve.</p>
          <p className="mt-1 font-body-sm text-body-sm text-on-surface-variant">
            Nexa's AI classifies, researches and drafts a plan for every ticket. Engineers review the evidence and perform every change by hand.
          </p>
          <div className="mt-space-md flex items-center justify-between font-body-sm text-body-sm text-on-surface-variant">
            <span>Search</span>
            <kbd className="rounded bg-surface-container-low px-1.5 font-label-code text-[10px]">⌘K</kbd>
          </div>
        </div>
      )}
    </div>
  );
}

export function AppShell() {
  const { me } = useAuth();
  const location = useLocation();
  const [paletteOpen, setPaletteOpen] = useState(false);
  const [mobileNav, setMobileNav] = useState(false);
  // Desktop nav is an icon rail by default; the choice is remembered per browser.
  const [collapsed, setCollapsed] = useState(() => {
    try {
      return localStorage.getItem("nexa.nav") !== "expanded";
    } catch {
      return true;
    }
  });
  const toggleCollapsed = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem("nexa.nav", c ? "expanded" : "collapsed");
      } catch {
        /* storage unavailable */
      }
      return !c;
    });
  const rail = collapsed && !mobileNav;
  const label = clsx("font-body-md text-body-md whitespace-nowrap", rail && "lg:hidden");
  const nav = useMemo(() => (me ? navFor(me) : null), [me]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => setMobileNav(false), [location.pathname]);

  if (!me || !nav) return null;
  return (
    <div className="nx-app relative isolate min-h-screen bg-surface">
      <Aurora className="fixed" />
      <aside
        className={clsx(
          "nx-sidebar fixed left-0 top-0 z-50 flex h-full w-64 flex-col justify-between py-space-lg transition-[transform,width] duration-300 lg:translate-x-0",
          rail ? "px-space-md lg:w-[72px] lg:px-space-sm" : "px-space-md",
          mobileNav ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex flex-col gap-space-lg">
          <Link to={homeFor(me)} state={{ home: Date.now() }} className="group relative px-space-sm" aria-label="Nexa home">
            <RailTip show={rail}>Home</RailTip>
            {rail ? (
              <>
                <span className="hidden lg:inline-flex"><NexaMark size={32} /></span>
                <span className="lg:hidden"><Wordmark /></span>
              </>
            ) : (
              <Wordmark />
            )}
          </Link>
          <nav className="flex flex-col gap-space-xs" aria-label="Main">
            {nav.main.map((item) => (
              <NavLink key={item.to} to={item.to} end={item.end} className={(a) => clsx(navClass(a), rail && "lg:justify-center")}>
                <Icon name={item.icon} className="text-[18px]" />
                <span className={label}>{item.label}</span>
                <RailTip show={rail}>{item.label}</RailTip>
              </NavLink>
            ))}
          </nav>
        </div>
        <div className="flex flex-col gap-space-sm pt-space-md">
          <NavLink to={nav.settings.to} className={({ isActive }) => clsx(navClass({ isActive: isActive || location.pathname.startsWith("/settings") }), rail && "lg:justify-center")}>
            <Icon name={nav.settings.icon} className="text-[18px]" />
            <span className={label}>{nav.settings.label}</span>
            <RailTip show={rail}>{nav.settings.label}</RailTip>
          </NavLink>
          <button
            type="button"
            onClick={toggleCollapsed}
            className={clsx("group relative hidden items-center gap-space-sm rounded-lg px-space-sm py-2 text-on-surface-variant transition-colors hover:bg-surface-container-low hover:text-on-surface lg:flex", rail && "justify-center")}
            aria-label={rail ? "Expand navigation" : "Collapse navigation"}
          >
            <Icon name={rail ? "left_panel_open" : "left_panel_close"} className="text-[18px]" />
            {!rail && <span className="font-body-sm text-body-sm">Collapse</span>}
            <RailTip show={rail}>Expand navigation</RailTip>
          </button>
          {rail ? (
            <>
              <Link to="/settings/profile" className="group relative hidden justify-center lg:flex" aria-label="Your profile">
                <Avatar name={me.name} url={me.avatar_url} />
                <RailTip show={rail}>{me.name}</RailTip>
              </Link>
              <div className="lg:hidden"><UserCard me={me} /></div>
            </>
          ) : (
            <UserCard me={me} />
          )}
        </div>
      </aside>
      {mobileNav && <div className="fixed inset-0 z-40 bg-primary/20 lg:hidden" onClick={() => setMobileNav(false)} />}

      <div className={clsx("transition-[padding] duration-300", collapsed ? "lg:pl-[72px]" : "lg:pl-64")}>
        <header className={clsx("nx-topbar fixed left-0 right-0 top-0 z-40 flex h-14 items-center justify-between px-gutter transition-[left] duration-300", collapsed ? "lg:left-[72px]" : "lg:left-64")}>
          <div className="flex items-center gap-space-md">
            <button type="button" className="rounded p-1 text-on-surface-variant lg:hidden" onClick={() => setMobileNav(true)} aria-label="Open navigation">
              <Icon name="menu" className="text-[20px]" />
            </button>
            <div className="flex items-center gap-space-xs font-body-sm text-body-sm text-on-surface-variant">
              <Link to={homeFor(me)} state={{ home: Date.now() }} className="hover:text-on-surface">ITSM</Link>
              <Icon name="chevron_right" className="text-[14px]" />
              <span className="font-medium text-on-surface">{location.pathname === homeFor(me) ? "Home" : sectionLabel(location.pathname)}</span>
            </div>
            <button
              type="button"
              onClick={() => setPaletteOpen(true)}
              className="hidden w-72 items-center gap-space-xs rounded bg-surface-container-low px-space-sm py-1 text-left font-body-sm text-body-sm text-on-surface-variant md:flex"
            >
              <Icon name="search" className="text-[16px]" />
              <span className="flex-1">Search tickets, services, runbooks...</span>
              <kbd className="rounded bg-surface-container-lowest px-1 font-label-code text-[10px] text-on-surface-variant">⌘K</kbd>
            </button>
          </div>
          <div className="flex items-center gap-space-md">
            <Notifications />
            <Help />
            <Link to="/settings/profile" className="pl-space-xs" aria-label="Your profile">
              <Avatar name={me.name} url={me.avatar_url} />
            </Link>
          </div>
        </header>
        <main className="relative min-h-screen w-full pt-14">
          <Outlet />
        </main>
      </div>
      <CommandPalette open={paletteOpen} onClose={() => setPaletteOpen(false)} />
    </div>
  );
}
