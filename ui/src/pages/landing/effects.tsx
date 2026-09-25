/**
 * Landing-page depth effects: aurora gradients, pointer-driven 3D tilt, scroll reveals and
 * the scroll-lit "horizon" section. CSS transforms only (no WebGL), and every effect is
 * disabled for visitors who ask for reduced motion.
 */
import clsx from "clsx";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

/** Slow-drifting blurred colour fields behind a section. */
export function Aurora({ className, dark = false }: { className?: string; dark?: boolean }) {
  return (
    <div aria-hidden="true" className={clsx("pointer-events-none absolute inset-0 -z-10 overflow-hidden", className)}>
      <div className={clsx("nx-aurora nx-aurora-a", dark && "opacity-60")} />
      <div className={clsx("nx-aurora nx-aurora-b", dark && "opacity-50")} />
      <div className={clsx("nx-aurora nx-aurora-c", dark && "opacity-40")} />
      <div className="nx-grid absolute inset-0" />
    </div>
  );
}

/** Tilts its child in 3D toward the pointer, with a moving specular highlight. */
export function Tilt({ children, className, max = 8, glare = true }: { children: ReactNode; className?: string; max?: number; glare?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const [style, setStyle] = useState<CSSProperties>({});
  const onMove = (e: React.PointerEvent) => {
    if (reducedMotion() || e.pointerType === "touch" || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width - 0.5;
    const y = (e.clientY - r.top) / r.height - 0.5;
    setStyle({
      transform: `rotateX(${(-y * max).toFixed(2)}deg) rotateY(${(x * max).toFixed(2)}deg) translateZ(0)`,
      ["--gx" as string]: `${(x + 0.5) * 100}%`,
      ["--gy" as string]: `${(y + 0.5) * 100}%`,
    });
  };
  return (
    <div className={clsx("[perspective:1400px]", className)} onPointerMove={onMove} onPointerLeave={() => setStyle({})}>
      <div ref={ref} style={style} className="nx-tilt relative [transform-style:preserve-3d]">
        {children}
        {glare && <div aria-hidden="true" className="nx-glare pointer-events-none absolute inset-0 rounded-[inherit]" />}
      </div>
    </div>
  );
}

/** Fades and lifts content into place the first time it scrolls into view. */
export function Reveal({ children, className, delay = 0 }: { children: ReactNode; className?: string; delay?: number }) {
  const ref = useRef<HTMLDivElement>(null);
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || reducedMotion() || typeof IntersectionObserver === "undefined") return setShown(true);
    const io = new IntersectionObserver(([entry]) => entry.isIntersecting && (setShown(true), io.disconnect()), { threshold: 0.12 });
    io.observe(el);
    return () => io.disconnect();
  }, []);
  return (
    <div ref={ref} style={{ transitionDelay: `${delay}ms` }} className={clsx("nx-reveal", shown && "nx-reveal-in", className)}>
      {children}
    </div>
  );
}

/** Tracks how far a tall element has scrolled through the viewport (0 → 1). */
function useScrollProgress<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const el = ref.current;
      if (!el) return;
      const r = el.getBoundingClientRect();
      const total = r.height - window.innerHeight;
      setProgress(total > 0 ? Math.min(1, Math.max(0, -r.top / total)) : 0);
    };
    const onScroll = () => (frame ||= requestAnimationFrame(update));
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(frame);
    };
  }, []);
  return [ref, progress] as const;
}

const HORIZON_WORDS = [
  { word: "UNDERSTAND", line: "Reads the employee's own words — no forms, no category pickers." },
  { word: "INVESTIGATE", line: "Searches your knowledge base and resolved-incident history." },
  { word: "DIAGNOSE", line: "Proposes a probable cause, with the evidence it relied on." },
  { word: "DISPATCH", line: "Routes a step-by-step plan to the right engineer, who executes it." },
];

/** Dark, sticky section: a curved glowing horizon while each stage lights up on scroll. */
export function Horizon() {
  const [ref, progress] = useScrollProgress<HTMLElement>();
  const active = Math.min(HORIZON_WORDS.length - 1, Math.floor(progress * HORIZON_WORDS.length));
  const rise = reducedMotion() ? 1 : Math.min(1, progress * 2.2);
  return (
    <section ref={ref} id="horizon" data-nav-dark className="relative h-[260vh] bg-[#05070d]" aria-label="How Nexa works">
      <div className="sticky top-0 flex h-screen items-center justify-center overflow-hidden">
        {/* Horizon arc + glow rising with scroll */}
        <div
          aria-hidden="true"
          className="nx-horizon pointer-events-none absolute left-1/2 top-1/2 aspect-square w-[160vmax] -translate-x-1/2 rounded-full"
          style={{ transform: `translate(-50%, ${(1 - rise) * 30 + 8}%) scale(${0.9 + rise * 0.1})` }}
        />
        <div aria-hidden="true" className="pointer-events-none absolute bottom-[-18vh] left-1/2 h-[46vh] w-[70vw] -translate-x-1/2 rounded-full bg-[radial-gradient(closest-side,rgba(99,102,241,0.75),rgba(56,189,248,0.25)_55%,transparent)] blur-2xl" style={{ opacity: 0.35 + rise * 0.65 }} />
        <div aria-hidden="true" className="nx-stars pointer-events-none absolute inset-0 opacity-60" />

        <div className="relative z-10 flex flex-col items-center gap-3 px-6 text-center">
          <span className="mb-4 font-label-caps text-label-caps uppercase tracking-[0.3em] text-[#8ea2ff]">One intelligence layer</span>
          {HORIZON_WORDS.map((w, i) => (
            <span
              key={w.word}
              className={clsx(
                "font-display-lg text-[clamp(36px,7vw,88px)] font-semibold leading-[1] tracking-[-0.03em] transition-all duration-500",
                i === active ? "nx-word-active scale-105 text-white" : i < active ? "text-white/35" : "text-white/15",
              )}
            >
              {w.word}
            </span>
          ))}
          <p className="mt-8 h-12 max-w-md font-body-lg text-body-lg text-[#bec6e0] transition-opacity duration-500" key={active}>
            {HORIZON_WORDS[active].line}
          </p>
          <span className="mt-2 font-label-code text-label-code uppercase tracking-widest text-white/40">AI investigates · Humans resolve</span>
        </div>
      </div>
    </section>
  );
}

/** Glowing vertical beam with a floating glass badge — the hero's centre-piece accent. */
export function LightBeam() {
  return (
    <div aria-hidden="true" className="pointer-events-none absolute inset-x-0 top-0 -z-10 flex h-full justify-center">
      <div className="nx-beam h-full w-px" />
    </div>
  );
}

/** Starts tilted back in perspective (a floating slab) and straightens as the page scrolls. */
export function ScrollTiltIn({ children, className }: { children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [t, setT] = useState(0);
  useEffect(() => {
    if (reducedMotion()) return setT(1);
    let frame = 0;
    const update = () => {
      frame = 0;
      const el = ref.current;
      if (!el) return;
      const top = el.getBoundingClientRect().top;
      const vh = window.innerHeight;
      setT(Math.min(1, Math.max(0, (vh - top) / (vh * 0.9))));
    };
    const onScroll = () => (frame ||= requestAnimationFrame(update));
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);
  const eased = 1 - Math.pow(1 - t, 3);
  return (
    <div ref={ref} className={clsx("[perspective:1600px]", className)}>
      <div
        className="origin-top will-change-transform"
        style={{ transform: `rotateX(${(1 - eased) * 22}deg) scale(${0.92 + eased * 0.08}) translateY(${(1 - eased) * 40}px)`, opacity: 0.55 + eased * 0.45 }}
      >
        {children}
      </div>
    </div>
  );
}
