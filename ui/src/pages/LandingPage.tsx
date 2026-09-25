/**
 * Public landing page ("/").
 *
 * Ported from reference/nexa_ai_native_it_service_management_editorial_landing_page/code.html.
 * Layout, type scale and colours follow the reference. The copy follows the product
 * spec: no invented statistics, customers, testimonials, integrations or certifications,
 * and V1 is human-in-the-loop — the AI investigates and recommends, engineers execute
 * every change. Tickets, people and timestamps inside the illustrations are examples.
 */
import clsx from "clsx";
import { Fragment, useEffect, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { Icon, NexaMark } from "@/components/ui";
import { api } from "@/lib/api";
import { Aurora, Horizon, Reveal, ScrollTiltIn, Tilt } from "./landing/effects";

// ── Shared pieces ────────────────────────────────────────────────────────────

/** All-caps label above a section headline. `className` carries the colour (and any spacing). */
function Eyebrow({ children, className = "text-secondary" }: { children: ReactNode; className?: string }) {
  return <span className={clsx("font-label-caps text-label-caps uppercase tracking-wider font-semibold", className)}>{children}</span>;
}

/** A button drawn inside a product illustration — a span, so it is neither focusable nor announced as a control. */
function MockButton({ children, className }: { children: ReactNode; className: string }) {
  return <span className={clsx("inline-flex items-center justify-center whitespace-nowrap", className)}>{children}</span>;
}

const pad = (n: number) => String(n).padStart(2, "0");

// ── Header ───────────────────────────────────────────────────────────────────

const NAV_LINKS = [
  { label: "Product", href: "#product" },
  { label: "How it works", href: "#how-it-works" },
  { label: "Solutions", href: "#engineers" },
  { label: "Resources", href: "#knowledge" },
];

/** True while the header floats over a section marked data-nav-dark. */
function useOverDarkSection() {
  const [dark, setDark] = useState(false);
  useEffect(() => {
    let frame = 0;
    const check = () => {
      frame = 0;
      const probe = document.elementsFromPoint(window.innerWidth / 2, 90).find((el) => !el.closest("header"));
      setDark(Boolean(probe?.closest("[data-nav-dark]")));
    };
    const onScroll = () => (frame ||= requestAnimationFrame(check));
    check();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  return dark;
}

function SiteHeader() {
  const dark = useOverDarkSection();
  return (
    <header className="fixed top-3 left-0 right-0 z-50 px-4">
      <div className={clsx("nx-glass h-14 max-w-5xl mx-auto rounded-full pl-5 pr-2 flex items-center justify-between gap-gutter transition-colors duration-300", dark && "nx-glass-dark")}>
        <div className="flex items-center gap-space-md">
          <NexaMark size={32} />
          <div className="flex items-center gap-space-xs">
            <span className="font-headline-sm text-headline-sm tracking-tight text-on-surface font-semibold">Nexa</span>
            <span className="font-label-caps text-label-caps uppercase bg-surface-container-high text-on-surface-variant px-space-xs py-0.5 rounded tracking-wider">AI ITSM</span>
          </div>
        </div>
        <nav aria-label="Primary" className="hidden md:flex items-center gap-space-lg">
          {NAV_LINKS.map((link) => (
            <a key={link.href} href={link.href} className="font-body-md text-body-md text-on-surface-variant hover:text-on-surface transition-colors">
              {link.label}
            </a>
          ))}
        </nav>
        <div className="flex items-center gap-space-md">
          <Link to="/login" className="font-body-md text-body-md text-on-surface-variant hover:text-on-surface transition-colors px-space-sm py-1.5">
            Sign in
          </Link>
          <Link
            to="/signup"
            className="font-body-md text-body-md bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary px-space-md py-1.5 rounded-lg transition-colors inline-flex items-center justify-center font-medium"
          >
            Get started
          </Link>
        </div>
      </div>
    </header>
  );
}

// ── 1. Hero ──────────────────────────────────────────────────────────────────

const HERO_PLAN = [
  "Verify client cert timestamp in System.keychain",
  "Inspect Okta SSO radius auth sync status",
  "Trigger MDM payload push for G3 Root CA",
  "Re-verify tunnel handshake from telemetry",
];

function Hero() {
  return (
    <section className="relative isolate w-full pt-32 pb-24 lg:pt-40 lg:pb-32 px-margin overflow-hidden">
      <Aurora />
      <div
        aria-hidden="true"
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[1200px] h-[600px] bg-gradient-to-b from-surface-variant/40 via-surface-container-low/20 to-transparent blur-3xl -z-10 pointer-events-none"
      />
      <div className="max-w-7xl mx-auto flex flex-col items-start">
        <div className="inline-flex items-center gap-space-xs mb-space-lg">
          <span className="w-1.5 h-1.5 rounded-full bg-secondary" />
          <Eyebrow className="text-on-surface-variant">AI-Native IT Service Management</Eyebrow>
        </div>
        <h1 className="font-display-lg text-[min(48px,12.5vw)] sm:text-[68px] lg:text-[96px] leading-[0.92] tracking-[-0.035em] text-on-surface font-semibold max-w-6xl mb-space-lg">
          <span>IT SUPPORT THAT UNDERSTANDS THE PROBLEM.</span>{" "}
          <span className="block text-on-surface-variant/80 mt-2 sm:mt-4">BEFORE YOUR TEAM TOUCHES IT.</span>
        </h1>
        <div className="flex flex-col md:flex-row md:items-baseline justify-between w-full gap-space-lg pb-space-xl border-b border-surface-container-high/60">
          <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl leading-relaxed">
            Nexa investigates IT issues, understands deep infrastructure context, generates a verified resolution plan, and directs it instantly to the right engineer.
          </p>
          <div className="flex flex-col items-start md:items-end gap-space-xs">
            <span className="font-label-code text-label-code text-secondary uppercase tracking-widest font-medium">Core Axiom</span>
            <span className="font-headline-md text-headline-md text-on-surface font-medium">AI investigates. Humans resolve.</span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-space-md pt-space-xl mb-20">
          <Link
            to="/signup"
            className="h-11 px-space-xl bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary transition-all duration-150 rounded-lg font-body-md text-body-md font-medium inline-flex items-center gap-space-xs shadow-sm hover:shadow"
          >
            <span>Get started</span>
            <Icon name="arrow_forward" className="text-[18px]" />
          </Link>
          <Link
            to="/login"
            className="h-11 px-space-lg bg-surface-container-lowest text-on-surface hover:bg-surface-container-low transition-colors duration-150 rounded-lg font-body-md text-body-md font-medium inline-flex items-center gap-space-xs shadow-sm"
          >
            <span>Sign in</span>
          </Link>
          <span className="font-label-code text-label-code text-on-surface-variant/70 ml-space-sm hidden sm:inline-block">AI recommends · Engineers execute</span>
        </div>
        <ScrollTiltIn className="w-full">
          <Tilt max={6} className="w-full">
            <HeroIllustration />
          </Tilt>
        </ScrollTiltIn>
      </div>
    </section>
  );
}

/** The hero's incident journey: employee report → AI read → diagnosis → plan handed to an engineer. */
function HeroIllustration() {
  return (
    <figure className="w-full relative mt-4">
      <div className="nx-depth w-full rounded-2xl bg-surface-container-lowest p-6 sm:p-10 lg:p-12 relative overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-space-md pb-8 border-b border-surface-container-high/70">
          <div className="flex items-center gap-space-md">
            <span className="font-label-code text-label-code font-semibold px-2 py-0.5 rounded bg-surface-container text-on-surface whitespace-nowrap">INC-8492</span>
            <span className="font-body-sm text-body-sm text-on-surface-variant">Auth0 SSO Gateway / GlobalProtect Mesh</span>
          </div>
          <div className="flex items-center gap-space-md">
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-error-container/60 text-error font-label-code text-label-code font-medium">
              <span className="w-1.5 h-1.5 rounded-full bg-error" />
              P2 High
            </span>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 pt-10">
          {/* 01–02: what the employee said, and the AI's first read of it */}
          <div className="lg:col-span-4 flex flex-col gap-6">
            <div>
              <span className="font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant font-semibold block mb-3">01 · Employee Signal</span>
              <div className="p-4 rounded-xl bg-surface-container-low shadow-sm">
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-5 h-5 rounded-full bg-surface-container-highest flex items-center justify-center font-label-code text-[10px] text-on-surface font-medium">ER</div>
                  <span className="font-body-sm text-body-sm text-on-surface font-medium">Elena Rostova</span>
                  <span className="font-label-code text-[11px] text-on-surface-variant ml-auto">09:14 AM</span>
                </div>
                <p className="font-body-md text-body-md text-on-surface font-normal">
                  "My VPN stopped working this morning right after the morning auth prompt. Can't reach the staging clusters."
                </p>
              </div>
            </div>
            <div className="relative pl-6 before:content-[''] before:absolute before:left-2 before:top-0 before:bottom-0 before:w-[2px] before:bg-secondary/20">
              <span className="font-label-caps text-label-caps uppercase tracking-wider text-secondary font-semibold block mb-2">02 · Agentic Intercept</span>
              <div className="p-3.5 rounded-lg bg-surface-container-high/40 text-on-surface font-body-sm text-body-sm leading-relaxed">
                <div className="flex items-center gap-1.5 mb-1.5 text-secondary font-medium">
                  <Icon name="auto_awesome" className="text-[16px]" />
                  <span>Nexa Agent Analysis</span>
                </div>
                "Identified recurring pattern with GP-CERT-2024 rotation. Matches a known certificate-rotation issue."
              </div>
            </div>
          </div>

          {/* 03: diagnosis */}
          <div className="lg:col-span-4 flex flex-col gap-4">
            <span className="font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant font-semibold">03 · Structural Diagnosis</span>
            <div className="p-5 rounded-xl bg-surface-container-low/60 flex flex-col gap-4">
              <div className="flex items-center justify-between pb-3 border-b border-surface-container-high">
                <span className="font-body-sm text-body-sm text-on-surface-variant">Inferred Service</span>
                <span className="font-label-code text-label-code text-on-surface font-medium">CorpNet / Palo Alto VPN</span>
              </div>
              <div className="flex items-center justify-between pb-3 border-b border-surface-container-high">
                <span className="font-body-sm text-body-sm text-on-surface-variant">Hypothesis</span>
                <span className="font-body-sm text-body-sm text-error font-medium text-right">Root Cert Expiration (macOS Keychain)</span>
              </div>
              <div className="flex flex-col gap-1.5 pt-1">
                <span className="font-label-caps text-[10px] uppercase tracking-wider text-on-surface-variant">Reported Error</span>
                <div className="font-label-code text-[11px] p-2.5 rounded bg-surface-container-highest text-on-surface leading-tight font-mono">
                  AUTH_ERR_604: TLS_V1_CERT_UNTRUSTED
                  <br />
                  Issuer: "Nexa Internal Intermediate G2"
                  <br />
                  Expired: 2025-05-18T00:00:00Z
                </div>
              </div>
              <div className="flex items-center gap-2 pt-1">
                <span className="w-2 h-2 rounded-full bg-secondary-container" />
                <span className="font-label-code text-label-code text-on-surface-variant">
                  Confidence: <strong className="text-on-surface">High</strong>
                </span>
              </div>
            </div>
          </div>

          {/* 04: the plan, handed to an engineer */}
          <div className="lg:col-span-4 flex flex-col gap-4">
            <span className="font-label-caps text-label-caps uppercase tracking-wider text-on-surface-variant font-semibold">04 · Execution Plan &amp; Dispatch</span>
            <div className="p-5 rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-3">
              <span className="font-label-code text-label-code font-semibold text-on-surface">Generated Plan #71</span>
              <ol className="flex flex-col gap-2">
                {HERO_PLAN.map((step, i) => (
                  <li key={step} className="flex items-start gap-2 text-on-surface font-body-sm text-body-sm">
                    <span className="font-label-code text-label-code text-secondary font-semibold pt-0.5">{pad(i + 1)}</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
              <div className="mt-3 pt-3 border-t border-surface-container-high flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div className="w-7 h-7 rounded-full bg-primary-container text-on-primary flex items-center justify-center font-label-code text-xs font-semibold">RS</div>
                  <div className="flex flex-col">
                    <span className="font-body-sm text-body-sm text-on-surface font-medium leading-tight">Rahul Sharma</span>
                    <span className="font-label-code text-[11px] text-on-surface-variant leading-none">Network Support · L1</span>
                  </div>
                </div>
                <span className="font-label-caps text-label-caps px-2 py-0.5 rounded bg-tertiary-container text-on-tertiary-container font-semibold">Ready for engineer</span>
              </div>
            </div>
          </div>
        </div>
      </div>
      <figcaption className="mt-space-sm font-label-code text-label-code text-on-surface-variant/70">Illustrative example</figcaption>
    </figure>
  );
}

// ── 2. The big idea ──────────────────────────────────────────────────────────

function ShiftSection() {
  return (
    <section className="w-full py-28 lg:py-36 px-margin bg-surface-container-low/40">
      <div className="max-w-5xl mx-auto flex flex-col gap-space-lg">
        <Eyebrow>The Shift in IT Operation</Eyebrow>
        <h2 className="font-display-lg text-[40px] sm:text-[56px] lg:text-[76px] leading-[0.98] tracking-[-0.03em] text-on-surface font-semibold">
          IT SUPPORT SHOULDN'T START WITH A TICKET.
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-space-xl pt-space-lg">
          <p className="font-body-lg text-body-lg text-on-surface leading-relaxed font-normal">
            Employees know what is broken. They don't know which category to choose, which severity level applies, or which internal silo owns the infrastructure. They
            shouldn't have to.
          </p>
          <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed">
            Nexa eliminates the form. People describe reality in natural language. Nexa ingests the incident, reconstructs the underlying context from services and incident
            history, forms a plan, and hands it directly to an engineer ready to execute.
          </p>
        </div>
      </div>
    </section>
  );
}

// ── 3. How it works ──────────────────────────────────────────────────────────

const STAGES = [
  {
    label: "Understand",
    title: "Natural Input",
    body: '"My VPN stopped working." No forced drop-down classifications or obscure component pickers.',
    footer: "Input: web assistant",
  },
  {
    label: "Investigate",
    title: "Context Synthesis",
    body: "AI automatically queries internal runbooks, past incident history, and your service and asset catalogue.",
    footer: "Knowledge base + incident history",
  },
  {
    label: "Diagnose",
    title: "Probable Cause",
    body: 'Hypothesis generated: "Client authentication cert invalid after G2 renewal." Backed by cited evidence.',
    footer: "Diagnostic certainty: High",
  },
  {
    label: "Route",
    title: "Surgical Assignment",
    body: "Targeted to Rahul Sharma (Network Support). Dispatched with ready-to-execute step checklist.",
    footer: "Routed by rules, recommended by AI",
  },
];

function HowItWorksSection() {
  return (
    <section id="how-it-works" className="w-full py-28 px-margin scroll-mt-16">
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col md:flex-row md:items-end justify-between mb-16 gap-space-md">
          <div>
            <Eyebrow className="text-on-surface-variant block mb-2">Predictable Trajectory</Eyebrow>
            <h2 className="font-headline-lg text-[28px] sm:text-[36px] leading-tight tracking-tight text-on-surface font-semibold">FROM 'SOMETHING IS BROKEN' TO A CLEAR PLAN.</h2>
          </div>
          <span className="font-label-code text-label-code text-on-surface-variant">Deterministic progression · Every stage is visible to the engineer</span>
        </div>
        <ol className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          {STAGES.map((stage, i) => (
            <li key={stage.label} className="nx-reveal-in nx-depth p-6 rounded-xl bg-surface-container-lowest flex flex-col justify-between h-72 transition-transform duration-300 hover:-translate-y-1.5">
              <div className="flex flex-col">
                <span className="font-display-lg text-display-lg text-on-surface font-semibold mb-space-sm">{pad(i + 1)}</span>
                <span className="font-label-caps text-label-caps uppercase text-secondary font-semibold mb-space-xs">{stage.label}</span>
                <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold mb-space-xs">{stage.title}</h3>
                <p className="font-body-sm text-body-sm text-on-surface-variant">{stage.body}</p>
              </div>
              <div className="pt-4 border-t border-surface-container-high/60">
                <span className="font-label-code text-label-code text-on-surface-variant/80">{stage.footer}</span>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

// ── 4. Employee experience ───────────────────────────────────────────────────

const QUICK_PROMPTS = ["What's the status?", "Who is handling this?", "What do I need to do right now?"];

function EmployeeSection() {
  return (
    <section className="w-full py-24 px-margin bg-surface-container-lowest">
      <div className="max-w-7xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 lg:gap-16 items-center">
        <div className="lg:col-span-5 flex flex-col gap-space-md">
          <Eyebrow>User Experience</Eyebrow>
          <h2 className="font-display-lg text-[36px] sm:text-[48px] leading-[1] tracking-tight text-on-surface font-semibold">JUST TELL IT WHAT'S WRONG.</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed">
            No mandatory 12-field request forms. No browsing 40 nested categories like {'"Infrastructure > Network > Edge > Remote Access"'}. No guessing which regional
            team handles the outage.
          </p>
          <p className="font-body-md text-body-md text-on-surface-variant">
            Employees simply describe the problem in their own words. Nexa acts as a high-empathy, hyper-competent bridge between user frustration and operational resolution.
          </p>
          <div className="pt-2">
            <div className="inline-flex items-center gap-2 font-label-code text-label-code text-on-surface">
              <span className="w-2 h-2 rounded-full bg-tertiary-container" />
              No forms, no category pickers
            </div>
          </div>
        </div>

        {/* Employee assistant preview */}
        <Tilt max={7} className="lg:col-span-7">
          <div className="p-6 sm:p-8 rounded-2xl bg-surface-container-low shadow-[0_4px_24px_rgba(11,28,48,0.04)] flex flex-col gap-6">
            <div className="flex items-center justify-between pb-4 border-b border-surface-container-high">
              <div className="flex items-center gap-2">
                <span className="w-3 h-3 rounded-full bg-secondary" />
                <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">Nexa Assistant</span>
              </div>
              <span className="font-label-code text-label-code text-on-surface-variant">Active Workspace</span>
            </div>
            <div className="flex flex-col gap-4">
              <div className="self-end max-w-md p-4 rounded-xl rounded-tr-sm bg-primary text-on-primary font-body-md text-body-md">
                "Hey, I cannot pull from the internal Git registry. Getting 403 Forbidden since noon."
              </div>
              <div className="self-start max-w-lg p-4 rounded-xl rounded-tl-sm bg-surface-container-lowest shadow-sm flex flex-col gap-2">
                <div className="flex items-center gap-1.5 text-secondary font-label-caps text-label-caps uppercase">
                  <Icon name="auto_awesome" className="text-[14px]" />
                  <span>Nexa Synthesis</span>
                </div>
                <p className="font-body-md text-body-md text-on-surface">
                  I checked this against known issues. Your GitHub Enterprise SSH key has likely expired after the 90-day rotation cycle.
                </p>
                <div className="p-2.5 rounded bg-surface-container-low text-on-surface-variant font-label-code text-[11px]">
                  Target: github.corp.internal · User: marcus.v · Action required: Token re-issue
                </div>
              </div>
            </div>
            <div className="flex flex-col gap-2 pt-2">
              <span className="font-label-caps text-[11px] text-on-surface-variant uppercase tracking-wider font-semibold">Quick inquiries</span>
              <div className="flex flex-wrap gap-2">
                {QUICK_PROMPTS.map((prompt) => (
                  <MockButton
                    key={prompt}
                    className="px-3 py-1.5 rounded-full bg-surface-container-lowest hover:bg-surface-container text-on-surface font-body-sm text-body-sm transition-colors shadow-sm"
                  >
                    {prompt}
                  </MockButton>
                ))}
              </div>
            </div>
          </div>
        </Tilt>
      </div>
    </section>
  );
}

// ── 5. Engineer experience (dark) ────────────────────────────────────────────

const ENGINEER_EVIDENCE = ["KB article on certificate expiry", "2 similar resolved incidents", "Error text reported by the employee"];

const ENGINEER_STEPS: { text: string; state: "done" | "current" | "next" }[] = [
  { text: "1. Verify VPN client log timestamp", state: "done" },
  { text: "2. Inspect Radius auth fail error codes", state: "done" },
  { text: "3. Push renewed certificate via Jamf Pro", state: "current" },
  { text: "4. Test connectivity handshake", state: "next" },
];

const ENGINEER_STEP_TEXT = {
  done: "text-white line-through opacity-70",
  current: "text-white font-medium group-hover:text-secondary-fixed transition-colors",
  next: "text-[#bec6e0] group-hover:text-white transition-colors",
};

function EngineerSection() {
  return (
    <section id="engineers" data-nav-dark className="relative isolate w-full py-28 lg:py-36 px-margin bg-[#090d16] text-[#ffffff] scroll-mt-16 overflow-hidden">
      <Aurora dark />
      <div className="max-w-7xl mx-auto flex flex-col gap-16">
        <div className="flex flex-col lg:flex-row lg:items-end justify-between gap-space-lg">
          <div className="max-w-2xl flex flex-col gap-space-sm">
            <Eyebrow className="text-secondary-fixed">Engineer Leverage</Eyebrow>
            <h2 className="font-display-lg text-[40px] sm:text-[56px] lg:text-[72px] leading-[0.96] tracking-[-0.03em] font-semibold text-white">GIVE ENGINEERS A HEAD START.</h2>
          </div>
          <p className="font-body-lg text-body-lg text-primary-fixed max-w-md leading-relaxed">
            Nexa does not replace the engineer. It delivers the deep context, supporting evidence, and root-cause hypothesis that should have existed before the ticket ever
            arrived in their queue.
          </p>
        </div>

        {/* Engineer ticket workspace preview */}
        <Reveal>
        <Tilt max={5}>
        <div className="w-full rounded-2xl bg-[#111726] border border-[#212c42] p-6 sm:p-10 flex flex-col gap-8 shadow-[0_40px_120px_-30px_rgba(99,102,241,0.45)]">
          <div className="flex flex-wrap items-center justify-between gap-4 pb-6 border-b border-[#212c42]">
            <div className="flex flex-wrap items-center gap-3">
              <span className="px-2.5 py-1 rounded bg-[#ba1a1a]/20 text-[#ffdad6] font-label-code text-xs font-semibold whitespace-nowrap">INC-8492 · P2 High</span>
              <span className="font-headline-sm text-headline-sm text-white font-medium">VPN Connection Handshake Failure</span>
            </div>
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-secondary/20 text-secondary-fixed font-label-code text-xs">
              <Icon name="bolt" className="text-[14px]" />
              <span>AI Suggested · Engineer Executes</span>
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-12 gap-8">
            <div className="lg:col-span-7 flex flex-col gap-6">
              <div className="flex flex-col gap-2">
                <span className="font-label-caps text-label-caps text-[#bec6e0] uppercase tracking-wider">AI Root Cause Hypothesis</span>
                <p className="font-body-lg text-body-lg text-white font-medium">
                  VPN authentication certificate in macOS Keychain expired. RADIUS server rejected EAP-TLS negotiation.
                </p>
              </div>
              <div className="p-4 rounded-xl bg-[#070a10] border border-[#1a2335] font-label-code text-[12px] text-[#bec6e0] flex flex-col gap-1.5 font-mono">
                <div className="text-[#68dba9]">✓ Evidence behind this hypothesis</div>
                <ul className="flex flex-col gap-1.5">
                  {ENGINEER_EVIDENCE.map((item) => (
                    <li key={item}>· {item}</li>
                  ))}
                </ul>
                <div className="text-[#ffdad6]">! Resolution path: Re-issue user payload or renew CA trust pair</div>
              </div>
              <div className="p-4 rounded-xl bg-[#172033] flex items-center justify-between gap-3">
                <div className="flex items-center gap-3">
                  <Icon name="history" className="text-secondary-fixed text-[20px]" />
                  <span className="font-body-sm text-body-sm text-white">
                    Matched a similar resolved incident <strong className="font-label-code whitespace-nowrap">INC-7821</strong>
                  </span>
                </div>
                <span className="font-label-code text-xs text-[#bec6e0] underline whitespace-nowrap">View diff</span>
              </div>
            </div>

            {/* Suggested next steps */}
            <div className="lg:col-span-5 p-6 rounded-xl bg-[#0b101c] border border-[#212c42] flex flex-col justify-between">
              <div className="flex flex-col gap-4">
                <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1 pb-3 border-b border-[#1c273c]">
                  <span className="font-label-caps text-label-caps uppercase tracking-wider text-[#bec6e0]">Actionable Runbook</span>
                  <span className="font-label-code text-xs text-[#68dba9] whitespace-nowrap">4 steps pre-populated</span>
                </div>
                <ul className="flex flex-col gap-3">
                  {ENGINEER_STEPS.map((step) => (
                    <li key={step.text} className="flex items-start gap-3 group">
                      {/* Illustration only: inert, out of the tab order and hidden from assistive tech (state is in the text). */}
                      <input
                        type="checkbox"
                        checked={step.state === "done"}
                        readOnly
                        tabIndex={-1}
                        aria-hidden="true"
                        className="mt-1 accent-secondary rounded pointer-events-none"
                      />
                      <span className={clsx("font-body-sm text-body-sm", ENGINEER_STEP_TEXT[step.state])}>
                        {step.state === "done" && <span className="sr-only">Done: </span>}
                        {step.text}
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="pt-6 mt-6 border-t border-[#1c273c] flex flex-wrap items-center justify-between gap-3">
                <span className="font-body-sm text-body-sm text-[#bec6e0]">Assigned to you</span>
                <MockButton className="h-9 px-4 rounded bg-white text-black font-body-sm text-body-sm font-semibold hover:bg-slate-200 transition-colors">Mark step 3 complete</MockButton>
              </div>
            </div>
          </div>
        </div>
        </Tilt>
        </Reveal>
      </div>
    </section>
  );
}

// ── 6. Human in the loop ─────────────────────────────────────────────────────

type DomainItem = { icon: string; text: string };

const AI_DOMAIN: DomainItem[] = [
  { icon: "psychology", text: "Understand issue from ambiguous language" },
  { icon: "search", text: "Investigate across knowledge, past incidents & services" },
  { icon: "analytics", text: "Diagnose root cause with a confidence level" },
  { icon: "format_list_bulleted", text: "Create step-by-step resolution plan" },
  { icon: "person_pin", text: "Assign with complete context to right engineer" },
];

const ENGINEER_DOMAIN: DomainItem[] = [
  { icon: "verified", text: "Review proposed diagnosis and evidence" },
  { icon: "play_circle", text: "Execute actions or adjust checklist" },
  { icon: "forward", text: "Escalate when deeper cross-system tier needed" },
  { icon: "check_circle", text: "Final sign-off & ticket resolution verification" },
  { icon: "auto_stories", text: "Enrich corporate memory for future recurrence" },
];

function DomainCard({ title, badge, badgeClass, rowClass, iconClass, items }: { title: string; badge: string; badgeClass: string; rowClass: string; iconClass: string; items: DomainItem[] }) {
  return (
    <div className="p-8 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col gap-6">
      <div className="flex items-center justify-between pb-4 border-b border-surface-container-high">
        <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold">{title}</h3>
        <span className={clsx("px-2 py-0.5 rounded font-label-code text-xs", badgeClass)}>{badge}</span>
      </div>
      <ol className="flex flex-col gap-3 font-body-md text-body-md">
        {items.map((item, i) => (
          <li key={item.text} className={clsx("flex items-center gap-3 p-3 rounded-lg text-on-surface", rowClass)}>
            <Icon name={item.icon} className={clsx(iconClass, "text-[20px]")} />
            <span>
              {i + 1}. {item.text}
            </span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function HumanInTheLoopSection() {
  return (
    <section className="w-full py-28 px-margin bg-surface">
      <div className="max-w-6xl mx-auto flex flex-col gap-14 text-center items-center">
        <div className="flex flex-col items-center gap-space-sm max-w-3xl">
          <Eyebrow>Strict Governance Guardrail</Eyebrow>
          <h2 className="font-display-lg text-[36px] sm:text-[52px] leading-[1.02] tracking-tight text-on-surface font-semibold">AI DOES THE THINKING. HUMANS STAY IN CONTROL.</h2>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-xl">
            Nexa does not mutate production configurations on its own in V1. It formulates verified plans; human engineers make the decisive calls.
          </p>
        </div>
        <div className="w-full grid grid-cols-1 md:grid-cols-2 gap-8 text-left">
          <DomainCard
            title="AI Responsibility Domain"
            badge="Recommends"
            badgeClass="bg-surface-container text-on-surface"
            rowClass="bg-surface-container-low"
            iconClass="text-secondary"
            items={AI_DOMAIN}
          />
          <DomainCard
            title="Human Engineer Domain"
            badge="Authoritative"
            badgeClass="bg-primary text-on-primary"
            rowClass="bg-surface-container-high/40"
            iconClass="text-primary"
            items={ENGINEER_DOMAIN}
          />
        </div>
      </div>
    </section>
  );
}

// ── 7. Resolution plan ───────────────────────────────────────────────────────

const PLAN_STEPS: { text: string; state: "done" | "active" | "pending" }[] = [
  { text: "Check client GlobalProtect connection log bundle", state: "done" },
  { text: "Query Auth0 SSO directory for RADIUS sync lock", state: "done" },
  { text: "Verify validity of MDM-pushed user cert payload", state: "active" },
  { text: "Test tunnel handshake & notify Elena Rostova", state: "pending" },
];

const PLAN_ROW = {
  done: "bg-surface-container-low hover:bg-surface-container transition-colors",
  active: "bg-surface-container-highest",
  pending: "bg-surface-container-low opacity-60",
};

function ResolutionPlanSection() {
  return (
    <section className="w-full py-24 px-margin bg-surface-container-low/50">
      <div className="max-w-6xl mx-auto grid grid-cols-1 lg:grid-cols-12 gap-12 items-center">
        <div className="lg:col-span-5 flex flex-col gap-space-md">
          <Eyebrow>Structured Execution</Eyebrow>
          <h2 className="font-display-lg text-[32px] sm:text-[44px] leading-tight text-on-surface font-semibold">EVERY INCIDENT STARTS WITH A PLAN.</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed">
            No blank stare. No "Where do I start?" Nexa outputs a structured checklist derived from verified incident history and your own knowledge base.
          </p>
          <p className="font-body-md text-body-md text-on-surface-variant">Engineers can effortlessly add steps, tweak sequences, or reassign the ticket with one click.</p>
        </div>

        {/* Plan checklist preview */}
        <Tilt max={7} className="lg:col-span-7">
          <div className="p-6 sm:p-8 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col gap-5">
            <div className="flex flex-wrap items-center justify-between gap-3 pb-3 border-b border-surface-container-high">
              <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">Active Runbook: INC-8492</span>
              <div className="flex items-center gap-2">
                <MockButton className="px-2.5 py-1 rounded bg-surface-container text-on-surface font-label-code text-xs font-medium hover:bg-surface-container-high transition-colors">
                  + Add Step
                </MockButton>
                <MockButton className="px-2.5 py-1 rounded bg-surface-container text-on-surface font-label-code text-xs font-medium hover:bg-surface-container-high transition-colors">
                  Reorder
                </MockButton>
              </div>
            </div>
            <ol className="flex flex-col gap-3">
              {PLAN_STEPS.map((step, i) => (
                <li key={step.text} className={clsx("flex items-center justify-between gap-3 p-3.5 rounded-lg", PLAN_ROW[step.state])}>
                  <div className="flex items-center gap-3">
                    <span className={clsx("font-label-code text-label-code font-bold", step.state === "pending" ? "text-on-surface-variant" : "text-secondary")}>{pad(i + 1)}</span>
                    <span className={clsx("font-body-md text-body-md text-on-surface", step.state === "active" && "font-medium")}>{step.text}</span>
                  </div>
                  {step.state === "done" && <Icon name="check" label="Done" className="text-on-tertiary-container text-[20px]" />}
                  {step.state === "active" && (
                    <span className="shrink-0 whitespace-nowrap font-label-caps text-[11px] px-2 py-0.5 rounded bg-secondary-container text-on-secondary-container font-semibold">In Progress</span>
                  )}
                  {step.state === "pending" && <span className="shrink-0 font-label-code text-xs text-on-surface-variant">Pending</span>}
                </li>
              ))}
            </ol>
          </div>
        </Tilt>
      </div>
    </section>
  );
}

// ── 8. Escalation & context continuity ───────────────────────────────────────

const DOSSIER = [
  { label: "AI Diagnosis", text: "Root CA mismatch in macOS bundle" },
  { label: "Execution Log", text: "L1 confirmed client auth fails" },
  { label: "Engineer Notes", text: '"Requires Jamf cert profile redeploy"' },
  { label: "Activity History", text: "Full ticket timeline preserved" },
];

function EscalationSection() {
  return (
    <section className="w-full py-28 px-margin bg-surface">
      <div className="max-w-6xl mx-auto flex flex-col gap-14">
        <div className="flex flex-col gap-space-sm max-w-3xl">
          <Eyebrow>Context Continuity</Eyebrow>
          <h2 className="font-display-lg text-[36px] sm:text-[50px] leading-tight text-on-surface font-semibold">WHEN L1 NEEDS HELP, CONTEXT MOVES WITH THE TICKET.</h2>
          <p className="font-body-lg text-body-lg text-on-surface-variant leading-relaxed">
            No restarting the investigation from zero. When a ticket escalates from L1 to L2 or Senior Infrastructure, the AI diagnosis, hypothesis tests, and engineer
            annotations move in a clean bundle.
          </p>
        </div>

        {/* L1 → L2 handoff preview */}
        <div className="p-8 sm:p-10 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col gap-8">
          <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 pb-6 border-b border-surface-container-high">
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-surface-container-high flex items-center justify-center font-label-code font-semibold text-on-surface">L1</div>
              <div>
                <span className="font-body-sm text-body-sm font-semibold text-on-surface block">L1 Service Desk</span>
                <span className="font-label-code text-xs text-on-surface-variant">Investigated 4 min · Steps 1 &amp; 2 executed</span>
              </div>
            </div>
            <div className="flex items-center gap-2 text-secondary font-label-caps text-label-caps font-semibold uppercase tracking-wider">
              <span>Seamless Handshake</span>
              <Icon name="trending_flat" className="text-[20px]" />
            </div>
            <div className="flex items-center gap-4">
              <div className="w-10 h-10 rounded-full bg-primary text-on-primary flex items-center justify-center font-label-code font-semibold">L2</div>
              <div>
                <span className="font-body-sm text-body-sm font-semibold text-on-surface block">Tier 2 Network Operations</span>
                <span className="font-label-code text-xs text-on-surface-variant">Assigned with full dossier</span>
              </div>
            </div>
          </div>
          <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {DOSSIER.map((item) => (
              <li key={item.label} className="p-4 rounded-xl bg-surface-container-low">
                <span className="font-label-caps text-label-caps uppercase text-secondary font-semibold block mb-1">{item.label}</span>
                <p className="font-body-sm text-body-sm text-on-surface">{item.text}</p>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ── 9. Knowledge & memory ────────────────────────────────────────────────────

const MEMORY_SOURCES = ["Knowledge base articles & runbooks", "Resolved incident history", "Service & asset catalogue", "Engineer notes and resolutions"];

const PAYOFFS = ["Recurring issues recognised sooner", "Plans grounded in your own runbooks", "Resolutions captured for next time"];

function KnowledgeSection() {
  return (
    <section id="knowledge" className="w-full py-24 px-margin bg-surface-container-low/40 scroll-mt-16">
      <div className="max-w-6xl mx-auto flex flex-col gap-12">
        <div className="flex flex-col gap-space-xs">
          <Eyebrow>Institutional Recall</Eyebrow>
          <h2 className="font-display-lg text-[32px] sm:text-[46px] leading-tight tracking-tight text-on-surface font-semibold">EVERY INCIDENT MAKES THE NEXT ONE EASIER.</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
          <div className="p-6 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between">
            <div>
              <span className="font-label-caps text-label-caps uppercase text-on-surface-variant font-semibold block mb-4">Input Memory Sources</span>
              <ul className="flex flex-col gap-2.5 font-label-code text-label-code text-on-surface">
                {MEMORY_SOURCES.map((source) => (
                  <li key={source} className="p-2.5 rounded bg-surface-container-low">
                    {source}
                  </li>
                ))}
              </ul>
            </div>
            <span className="font-label-code text-xs text-on-surface-variant pt-4">Indexed as articles are published</span>
          </div>

          <div className="p-6 rounded-2xl bg-primary text-on-primary shadow-md flex flex-col justify-between">
            <div>
              <span className="font-label-caps text-label-caps uppercase text-primary-fixed font-semibold block mb-4">Nexa Semantic Graph</span>
              <div className="flex flex-col gap-3 font-body-sm text-body-sm text-slate-200">
                <p>Indexes knowledge articles and resolution workflows, and links new tickets to similar past incidents.</p>
                <p>Resolved incidents become searchable evidence for the next investigation.</p>
              </div>
            </div>
            <div className="pt-4 border-t border-slate-800">
              <span className="font-label-code text-xs text-tertiary-fixed">Dynamic context synthesis active</span>
            </div>
          </div>

          <div className="p-6 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col justify-between">
            <div>
              <span className="font-label-caps text-label-caps uppercase text-on-surface-variant font-semibold block mb-4">Immediate Payoff</span>
              <ul className="flex flex-col gap-2.5 font-body-sm text-body-sm text-on-surface">
                {PAYOFFS.map((payoff) => (
                  <li key={payoff} className="p-2.5 rounded bg-surface-container-low">
                    {payoff}
                  </li>
                ))}
              </ul>
            </div>
            <span className="font-label-code text-xs text-on-surface-variant pt-4">Resolution summaries drafted for review</span>
          </div>
        </div>
      </div>
    </section>
  );
}

// ── 10. One intelligence layer (dark) ────────────────────────────────────────

const PIPELINE = [
  { label: "Employee", className: "bg-[#1e293b] text-white" },
  { label: "AI Assistant", className: "bg-secondary/30 text-secondary-fixed font-medium" },
  { label: "AI Triage", className: "bg-secondary/30 text-secondary-fixed font-medium" },
  { label: "AI Diagnosis", className: "bg-secondary/30 text-secondary-fixed font-medium" },
  { label: "Resolution Plan", className: "bg-white text-black font-semibold" },
  { label: "Engineer", className: "bg-[#1e293b] text-white" },
  { label: "Resolved", className: "bg-[#069669]/30 text-[#85f8c4]" },
];

const MODULES = ["Incidents", "Service Requests", "Knowledge", "Services & Assets", "Changes", "SLA Policies"];

function PlatformSection() {
  return (
    <section id="product" data-nav-dark className="w-full py-28 lg:py-36 px-margin bg-[#070b14] text-white scroll-mt-16">
      <div className="max-w-7xl mx-auto flex flex-col items-center text-center gap-12">
        <div className="flex flex-col items-center gap-3 max-w-3xl">
          <Eyebrow className="text-secondary-fixed">Unified Operating System</Eyebrow>
          <h2 className="font-display-lg text-[40px] sm:text-[60px] leading-[1.02] tracking-tight font-semibold text-white">ONE INTELLIGENCE LAYER FOR IT.</h2>
          <p className="font-body-md text-body-md text-[#bec6e0] max-w-xl">
            An end-to-end incident pipeline replacing fragmented ticketing tools, manual Slack triage channels, and dead runbooks.
          </p>
        </div>
        <div className="w-full p-8 sm:p-12 rounded-2xl bg-[#0f172a]/70 border border-[#1e293b] flex flex-col gap-10">
          <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 text-xs sm:text-sm font-label-code">
            {PIPELINE.map((stage, i) => (
              <Fragment key={stage.label}>
                {i > 0 && (
                  <span aria-hidden="true" className="text-secondary-fixed">
                    →
                  </span>
                )}
                <span className={clsx("px-3 py-1.5 rounded", stage.className)}>{stage.label}</span>
              </Fragment>
            ))}
          </div>
          <ul className="flex flex-wrap items-center justify-center gap-3 pt-6 border-t border-[#1e293b]/80">
            {MODULES.map((module) => (
              <li key={module} className="font-label-code text-xs px-3 py-1 rounded-full bg-[#131b2e] text-[#bec6e0]">
                {module}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ── 11. Capabilities ─────────────────────────────────────────────────────────

const CAPABILITIES = [
  { icon: "troubleshoot", title: "Incident Management", body: "Real-time incident lifecycle management without slow status updates or lost tickets." },
  { icon: "auto_awesome", title: "AI Triage & Classification", body: "Automatic categorization and severity tagging, with explainable confidence and rule-based routing." },
  { icon: "auto_stories", title: "Knowledge Synthesis", body: "Transforms knowledge base articles and past resolved tickets into dynamic, contextual diagnostic runbooks." },
  { icon: "checklist", title: "Service Requests", body: "Access and hardware requests in plain language, routed to the right team." },
  { icon: "lan", title: "Escalation Handshake", body: "Seamless multi-tier escalation retaining all logs, hypotheses, and notes so senior engineers skip initial triage." },
  { icon: "database", title: "Services & Assets", body: "A lightweight service catalogue and asset register the AI uses as investigation context." },
];

function CapabilitiesSection() {
  return (
    <section className="w-full py-28 px-margin bg-surface">
      <div className="max-w-7xl mx-auto flex flex-col gap-14">
        <div className="flex flex-col gap-2">
          <Eyebrow>Capabilities</Eyebrow>
          <h2 className="font-headline-lg text-[32px] sm:text-[40px] leading-tight tracking-tight text-on-surface font-semibold">EVERYTHING YOUR IT TEAM NEEDS.</h2>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {CAPABILITIES.map((capability, i) => (
            <Reveal key={capability.title} delay={i * 70}>
            <div className="h-full p-6 rounded-xl bg-surface-container-lowest shadow-sm flex flex-col gap-3 transition-all duration-300 hover:-translate-y-1.5 hover:shadow-[0_24px_60px_-20px_rgba(11,28,48,0.25)]">
              <Icon name={capability.icon} className="text-secondary text-[24px]" />
              <h3 className="font-headline-sm text-headline-sm text-on-surface font-semibold">{capability.title}</h3>
              <p className="font-body-md text-body-md text-on-surface-variant leading-relaxed">{capability.body}</p>
            </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ── 12. Operations ───────────────────────────────────────────────────────────

const QUEUE = [
  {
    priority: "P1",
    priorityClass: "bg-error-container text-error",
    title: "Stripe Webhook Gateway Timeout",
    meta: "Payments team · AI generated 3-step roll-back plan",
    action: "Review Plan →",
    actionClass: "bg-primary text-on-primary",
  },
  {
    priority: "P2",
    priorityClass: "bg-surface-container-high text-on-surface",
    title: "GlobalProtect Handshake Failure",
    meta: "Assigned to Rahul S. · Root Cert Expiration verified",
    action: "Resume",
    actionClass: "bg-surface-container-lowest text-on-surface",
  },
  {
    priority: "P3",
    priorityClass: "bg-surface-container-high text-on-surface",
    title: "Exchange Sync Latency on iOS Client",
    meta: "Diagnostics gathered · Waiting on engineer",
    action: "Open",
    actionClass: "bg-surface-container-lowest text-on-surface",
  },
];

function OperationsSection() {
  return (
    <section className="w-full py-24 px-margin bg-surface-container-low/40">
      <div className="max-w-6xl mx-auto flex flex-col gap-12">
        <div className="flex flex-col md:flex-row md:items-end justify-between gap-6">
          <div>
            <Eyebrow className="text-secondary block mb-2">Operational Focus</Eyebrow>
            <h2 className="font-headline-lg text-[32px] sm:text-[40px] leading-tight tracking-tight text-on-surface font-semibold">KNOW WHAT NEEDS YOUR ATTENTION.</h2>
          </div>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-md">
            Nexa surfaces the work that matters instead of forcing engineers to sift through overwhelming backlogs.
          </p>
        </div>

        {/* Focused queue preview */}
        <div className="p-6 sm:p-8 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col gap-4">
          <div className="flex items-center justify-between gap-3 pb-3 border-b border-surface-container-high">
            <div className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-error" />
              <span className="font-label-caps text-label-caps font-semibold uppercase text-on-surface tracking-wider">Needs Your Attention · 3 Active</span>
            </div>
            <span className="font-label-code text-xs text-on-surface-variant">Live Dispatch View</span>
          </div>
          <ul className="flex flex-col gap-4">
            {QUEUE.map((ticket) => (
              <li
                key={ticket.title}
                className="p-4 rounded-xl bg-surface-container-low hover:bg-surface-container transition-colors flex flex-col sm:flex-row sm:items-center justify-between gap-4"
              >
                <div className="flex items-center gap-4">
                  <span className={clsx("px-2 py-0.5 rounded font-label-code text-xs font-semibold", ticket.priorityClass)}>{ticket.priority}</span>
                  <div>
                    <span className="font-body-md text-body-md text-on-surface font-medium block">{ticket.title}</span>
                    <span className="font-body-sm text-body-sm text-on-surface-variant">{ticket.meta}</span>
                  </div>
                </div>
                <MockButton className={clsx("h-8 px-3 rounded font-body-sm text-body-sm font-medium self-start sm:self-center", ticket.actionClass)}>{ticket.action}</MockButton>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

// ── 13. AI settings & guardrails ─────────────────────────────────────────────

const ON = "bg-tertiary-container text-on-tertiary-container";

const POLICIES = [
  { title: "AI Triage & Categorization", description: "Automatically parse employee prompts and assign priority tags", status: "ACTIVE · ON", tone: ON },
  { title: "AI Root Cause Diagnosis", description: "Search knowledge and incident history to formulate causal hypotheses", status: "ACTIVE · ON", tone: ON },
  { title: "Dynamic Resolution Plans", description: "Synthesize interactive check-lists from historical resolutions", status: "ACTIVE · ON", tone: ON },
  {
    title: "Direct Infrastructure Mutation",
    description: "Autonomous API writes to production DNS, IAM, or cloud infrastructure",
    status: "BLOCKED · OFF",
    tone: "bg-error-container text-error",
  },
  {
    title: "Human Verification Mandate",
    description: "Require engineer sign-off on remediation actions",
    status: "ENFORCED",
    tone: "bg-secondary-container text-on-secondary-container",
  },
];

function GuardrailsSection() {
  return (
    <section className="w-full py-24 px-margin bg-surface">
      <div className="max-w-5xl mx-auto flex flex-col gap-10">
        <div className="flex flex-col gap-2">
          <Eyebrow>Safety &amp; Policies</Eyebrow>
          <h2 className="font-headline-lg text-[32px] sm:text-[38px] leading-tight tracking-tight text-on-surface font-semibold">INTELLIGENCE WITHOUT LOSING CONTROL.</h2>
          <p className="font-body-md text-body-md text-on-surface-variant max-w-xl">Granular permission policies ensure AI assistance stays within strict enterprise boundaries.</p>
        </div>

        {/* Policy matrix preview */}
        <ul className="p-6 sm:p-8 rounded-2xl bg-surface-container-lowest shadow-sm flex flex-col gap-4">
          {POLICIES.map((policy, i) => (
            <li key={policy.title} className={clsx("flex items-center justify-between gap-4 py-3", i < POLICIES.length - 1 && "border-b border-surface-container-high")}>
              <div>
                <span className="font-body-md text-body-md font-medium text-on-surface block">{policy.title}</span>
                <span className="font-body-sm text-body-sm text-on-surface-variant">{policy.description}</span>
              </div>
              <span className={clsx("shrink-0 px-3 py-1 rounded-full font-label-code text-xs font-bold", policy.tone)}>{policy.status}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

// ── 14. Final call to action ─────────────────────────────────────────────────

function FinalCtaSection() {
  return (
    <section className="w-full py-32 lg:py-48 px-margin bg-surface-container-lowest">
      <div className="max-w-5xl mx-auto flex flex-col items-start gap-8">
        <Eyebrow>The Standard for Modern IT</Eyebrow>
        <h2 className="font-display-lg text-[44px] sm:text-[64px] lg:text-[84px] leading-[0.95] tracking-[-0.035em] text-on-surface font-semibold">
          YOUR IT TEAM ALREADY KNOWS HOW TO FIX THINGS.
          <br />
          <span className="text-on-surface-variant/80">NEXA HELPS THEM GET THERE FASTER.</span>
        </h2>
        <p className="font-body-lg text-body-lg text-on-surface-variant max-w-xl leading-relaxed">AI investigates. Engineers resolve. Organizations move faster.</p>
        <div className="flex flex-wrap items-center gap-space-md pt-4">
          <Link
            to="/signup"
            className="h-12 px-space-xl bg-primary text-on-primary hover:bg-primary-container hover:text-on-primary transition-all duration-150 rounded-lg font-body-md text-body-md font-medium inline-flex items-center gap-space-xs shadow-md"
          >
            <span>Get started</span>
            <Icon name="arrow_forward" className="text-[18px]" />
          </Link>
          <Link
            to="/login"
            className="h-12 px-space-lg bg-surface-container text-on-surface hover:bg-surface-container-high transition-colors duration-150 rounded-lg font-body-md text-body-md font-medium inline-flex items-center"
          >
            <span>Sign in</span>
          </Link>
        </div>
      </div>
    </section>
  );
}

// ── Footer ───────────────────────────────────────────────────────────────────

type FooterLink = { label: string } & ({ href: string } | { to: string });

const FOOTER_COLUMNS: { heading: string; links: FooterLink[] }[] = [
  {
    heading: "Platform",
    links: [
      { label: "Product", href: "#product" },
      { label: "Architecture", href: "#how-it-works" },
      { label: "Incident Triage", href: "#engineers" },
    ],
  },
  { heading: "Resources", links: [{ label: "Runbooks", href: "#knowledge" }] },
  {
    heading: "Access",
    links: [
      { label: "Sign in", to: "/login" },
      { label: "Create account", to: "/signup" },
    ],
  },
];

type ApiState = "checking" | "operational" | "degraded" | "unreachable";

const API_STATUS: Record<ApiState, { dot: string; label: string }> = {
  checking: { dot: "bg-outline", label: "Checking status…" },
  operational: { dot: "bg-on-tertiary-container", label: "API operational" },
  degraded: { dot: "bg-amber-500", label: "API degraded" },
  unreachable: { dot: "bg-amber-500", label: "API unreachable" },
};

/** Live status of the Nexa API, from the public /health endpoint. */
function ApiStatus() {
  const { status, data } = useQuery({ queryKey: ["health"], queryFn: api.health, retry: false });
  const state: ApiState = status === "pending" ? "checking" : status === "error" ? "unreachable" : data?.status === "ok" ? "operational" : "degraded";
  const { dot, label } = API_STATUS[state];
  return (
    <span role="status" className="flex items-center gap-space-xs">
      <span aria-hidden="true" className={clsx("w-2 h-2 rounded-full inline-block", dot)} />
      {label}
    </span>
  );
}

function SiteFooter() {
  const linkClass = "font-body-sm text-body-sm text-on-surface-variant hover:text-on-surface transition-colors";
  return (
    <footer className="w-full bg-surface-container-low py-space-xl mt-space-xl">
      <div className="max-w-7xl mx-auto px-margin">
        <div className="flex flex-col md:flex-row items-baseline justify-between gap-space-lg pb-space-lg">
          <div className="flex flex-col gap-space-xs">
            <div className="flex items-center gap-space-xs">
              <span className="font-headline-sm text-headline-sm text-on-surface font-semibold">Nexa</span>
              <span className="font-label-caps text-label-caps uppercase text-on-surface-variant tracking-wider">ITSM</span>
            </div>
            <p className="font-body-sm text-body-sm text-on-surface-variant max-w-sm">Ultra-minimal, agentic incident workflows and operational automation for technical organizations.</p>
          </div>
          <nav aria-label="Footer" className="grid grid-cols-2 sm:grid-cols-3 gap-space-xl text-left">
            {FOOTER_COLUMNS.map((column) => (
              <div key={column.heading} className="flex flex-col gap-space-sm">
                <span className="font-label-caps text-label-caps uppercase text-on-surface-variant tracking-wider font-semibold">{column.heading}</span>
                {column.links.map((link) =>
                  "to" in link ? (
                    <Link key={link.label} to={link.to} className={linkClass}>
                      {link.label}
                    </Link>
                  ) : (
                    <a key={link.label} href={link.href} className={linkClass}>
                      {link.label}
                    </a>
                  ),
                )}
              </div>
            ))}
          </nav>
        </div>
        <div className="pt-space-lg flex flex-col sm:flex-row items-center justify-between gap-space-md font-body-sm text-body-sm text-on-surface-variant">
          <p>© 2026 Nexa. Built for zero-friction incident operations.</p>
          <ApiStatus />
        </div>
      </div>
    </footer>
  );
}

// ── Page ─────────────────────────────────────────────────────────────────────

export default function LandingPage() {
  return (
    <>
      <SiteHeader />
      <main className="w-full bg-surface min-h-[calc(100vh-16rem)]">
        <div className="flex flex-col w-full">
          <Hero />
          <ShiftSection />
          <Horizon />
          <HowItWorksSection />
          <EmployeeSection />
          <EngineerSection />
          <HumanInTheLoopSection />
          <ResolutionPlanSection />
          <EscalationSection />
          <KnowledgeSection />
          <PlatformSection />
          <CapabilitiesSection />
          <OperationsSection />
          <GuardrailsSection />
          <FinalCtaSection />
        </div>
      </main>
      <SiteFooter />
    </>
  );
}
