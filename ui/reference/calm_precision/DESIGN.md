---
name: Calm Precision
colors:
  surface: '#f8f9ff'
  surface-dim: '#cbdbf5'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eff4ff'
  surface-container: '#e5eeff'
  surface-container-high: '#dce9ff'
  surface-container-highest: '#d3e4fe'
  on-surface: '#0b1c30'
  on-surface-variant: '#45464d'
  inverse-surface: '#213145'
  inverse-on-surface: '#eaf1ff'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#4648d4'
  on-secondary: '#ffffff'
  secondary-container: '#6063ee'
  on-secondary-container: '#fffbff'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#002114'
  on-tertiary-container: '#069669'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#e1e0ff'
  secondary-fixed-dim: '#c0c1ff'
  on-secondary-fixed: '#07006c'
  on-secondary-fixed-variant: '#2f2ebe'
  tertiary-fixed: '#85f8c4'
  tertiary-fixed-dim: '#68dba9'
  on-tertiary-fixed: '#002114'
  on-tertiary-fixed-variant: '#005137'
  background: '#f8f9ff'
  on-background: '#0b1c30'
  surface-variant: '#d3e4fe'
typography:
  display-lg:
    fontFamily: Geist
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
    letterSpacing: -0.025em
  headline-lg:
    fontFamily: Geist
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
    letterSpacing: -0.02em
  headline-md:
    fontFamily: Geist
    fontSize: 20px
    fontWeight: '500'
    lineHeight: 28px
    letterSpacing: -0.015em
  headline-sm:
    fontFamily: Geist
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
    letterSpacing: -0.01em
  body-lg:
    fontFamily: Geist
    fontSize: 15px
    fontWeight: '400'
    lineHeight: 24px
    letterSpacing: -0.005em
  body-md:
    fontFamily: Geist
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20px
    letterSpacing: 0em
  body-sm:
    fontFamily: Geist
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: 0em
  label-code:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
    letterSpacing: -0.01em
  label-caps:
    fontFamily: Geist
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 16px
    letterSpacing: 0.04em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  gutter: 1rem
  margin: 1.5rem
  space-xs: 0.25rem
  space-sm: 0.5rem
  space-md: 0.75rem
  space-lg: 1.25rem
  space-xl: 2rem
---

## Brand & Style

This design system reflects an ultra-minimal, high-velocity operational environment for modern enterprise IT service management and technical operations. Drawing direct influence from the deliberate functionalism of Linear, the structural typographic rigor of Vercel, and the understated tactile quality of Stripe, the interface establishes absolute clarity in high-pressure technical incident workflows.

The brand persona is quiet, analytical, and authoritative. It strips away traditional enterprise clutter—ornate widgets, nested cards, redundant container borders, and gratuitous gradient badges—in favor of structural whitespace, deliberate typographic scale, and pinpoint optical balance. Users should feel complete spatial calm, immediate agency, and frictionless speed. Interactions should evoke zero latency and zero decorative friction; the tool disappears, leaving only state, resolution pathways, and agentic intelligence.

## Colors

The palette is anchored on high-key luminous whites and cool whisper-grays, contrasted against deep, surgical slate charcoals. The interface functions predominantly in monochrome, allowing status tokens and contextual AI assists to communicate without chromatic competition.

### Core Canvas & Surfaces
- **Canvas Base:** `#FAFAFA` — Subdued canvas for main dashboard backdrops and document shells.
- **Surface Elevation:** `#FFFFFF` — Primary working surface for tables, triage panels, and active execution zones.
- **Surface Hover / Subtle Inset:** `#F8FAFC` — Used for active selection rows, subtle pill containers, and key shortcut badges.
- **Hairline Borders:** `#E2E8F0` — 1px technical lines for structural isolation. Secondary inner-grid lines use `#F1F5F9`.

### Typography Colors
- **Primary Ink:** `#0F172A` — Deep slate-charcoal for headings, primary ticket identifiers, and high-impact text.
- **Secondary Ink:** `#334155` — Mid slate for body descriptions, workflow logs, and interactive controls.
- **Muted Ink:** `#64748B` — Metadata, inline timestamps, breadcrumbs, and hotkey labels.
- **Subtle / Ghost:** `#94A3B8` — Placeholders and de-emphasized structural hints.

### Accent & Intelligence
- **AI Accent (Refined Indigo):** `#6366F1` — Reserved strictly for autonomous ticket actions, machine-suggested root causes, synthesis badges, and active agent execution. Never use wide neon dropshadows, loud outer glows, or heavy decorative backgrounds; pair with 10% opacity tints (`#EEF2FF`) and 1px crisp borders (`#C7D2FE`).

### Semantic Status Tokens
- **Critical / P1 / Failed:** `#EF4444` (Text/Stroke: `#DC2626`, Tint Surface: `#FEF2F2`)
- **Warning / Degraded / Pending:** `#F59E0B` (Text/Stroke: `#D97706`, Tint Surface: `#FFFBEB`)
- **Success / Resolved / Operational:** `#059669` (Text/Stroke: `#047857`, Tint Surface: `#ECFDF5`)
- **Neutral / Informational / Draft:** `#64748B` (Text/Stroke: `#475569`, Tint Surface: `#F1F5F9`)

## Typography

Typography establishes 90% of the UI structure. Geist provides precise geometrical proportions, neutral horizontal rhythm, and optical legibility at high data densities, while JetBrains Mono ensures technical identifiers, commit hashes, SLA runtimes, and keyboard shortcuts remain clean and monospaced.

### Implementation Guidelines
- **Optical Tracking:** Tighten negative letter tracking slightly as font sizes scale up (`-0.025em` on displays; `-0.01em` down to 16px). For body text at 13px, tracking remains standard `0em`.
- **Labels & Microcopy:** `label-caps` must always be rendered in uppercase to differentiate field captions and section labels from ticket titles.
- **Monospace Discipline:** Reserve `label-code` for ticket keys (e.g., `INC-8921`), execution logs, duration indicators (`342ms`), and inline parameters. Do not mix serif fonts or decorative typefaces anywhere in the ecosystem.

## Layout & Spacing

Layout avoids defensive nesting. The workspace uses a flexible two-pane or three-pane master-detail structure with continuous fluid columns and fixed utility drawers. 

### Spacing Principles
- **Avoid "Card Hell":** Do not wrap every grouping in bordered boxes with distinct shadows. Let vertical typographic margins (`space-lg` to `space-xl`) define sections. Use single 1px hairline dividers (`#F1F5F9`) only where visual scanning requires hard demarcations (such as separating real-time activity streams from issue descriptions).
- **Rhythm & Grid:** Adhere to an 8px architectural grid (with 4px sub-intervals for tight control bars and badges). 
  - `space-xs` (4px): Inner-element gaps (icon-to-text, keybinding badge padding).
  - `space-sm` (8px): Button padding (vertical), list item spacing.
  - `space-md` (12px): Standard field padding, compact layout spacing.
  - `space-lg` (20px): Structural grouping padding.
  - `space-xl` (32px): Major panel separators and empty-state gutters.

### Adaptive Breakpoints
- **Desktop (>= 1280px):** Full tri-pane layout (Navigation Bar 220px fixed, Ticket Stream 360px-480px, Context Canvas flex-grow).
- **Tablet (768px - 1279px):** Split-pane with collapsible left navigation; command palette (`Cmd+K`) takes over global navigation.
- **Mobile (< 768px):** Single stack view with seamless edge-to-edge list transitions and sliding action sheets for triage metadata.

## Elevation & Depth

Depth in this system is achieved via flat architectural layering, subtle tonal differences, and precise micro-shadows. There are no thick, muddy dropshadows or heavy blur blurs.

### Surface Tiers
1. **Level 0 (Base Canvas):** Background tone `#FAFAFA`. Completely un-elevated.
2. **Level 1 (Structural Pane):** White `#FFFFFF` with a 1px border (`#E2E8F0`). Flat against canvas or delineated solely by hairline separators.
3. **Level 2 (Floating Popovers & Menus):** White `#FFFFFF` backed by `box-shadow: 0 1px 2px rgba(15, 23, 42, 0.04), 0 4px 12px rgba(15, 23, 42, 0.06);` and bordered with 1px `#E2E8F0`.
4. **Level 3 (Command Palette & Modals):** White `#FFFFFF` backed by `box-shadow: 0 8px 30px rgba(15, 23, 42, 0.08);` with a 1px `#CBD5E1` outline. Backdrops use a pure white wash with high translucency (`rgba(255, 255, 255, 0.8)`) coupled with `backdrop-filter: blur(8px)`.

### Border Discipline
Edges matter more than shadows. Always pair floating layers with crisp, sub-pixel borders (`#E2E8F0` or `#CBD5E1`) so that UI elements preserve their exact contours on high-DPI displays without relying on shadow dispersion.

## Shapes

The design system employs a soft corner curvature (`roundedness: 1`). Radii are deliberate, sharp, and compact to maintain an engineered, high-density tool aesthetic.

- **Base Radius (4px / 0.25rem):** Buttons, text inputs, status badges, shortcut tags, and table row focus indicators.
- **Medium Radius (6px / 0.375rem):** Dropdown menus, tooltips, flyout action sheets, and modal action dialogs.
- **Large Radius (8px / 0.5rem):** Central floating dialogs, command palettes (`Cmd+K`), and container sheets.
- **Pill (Fully Rounded):** Restricted exclusively to avatar indicators and status presence dots. Form controls, buttons, and badges must never be fully circular pills; they must retain crisp, soft-cornered rectangular architecture.

## Components

### Buttons
- **Primary:** Background `#0F172A`, text `#FFFFFF`, border `1px solid transparent`. Height: 32px (compact) or 36px (regular). Hover: `#1E293B`. Active: `#334155`. 4px radius. Font: `13px / 500`.
- **Secondary (Subtle Outline):** Background `#FFFFFF`, text `#0F172A`, border `1px solid #E2E8F0`. Shadow: `0 1px 2px rgba(0,0,0,0.02)`. Hover: `#F8FAFC`, border `#CBD5E1`.
- **Ghost:** Background `transparent`, text `#334155`. Hover: `#F1F5F9`, text `#0F172A`.
- **AI Action Button:** Background `#EEF2FF`, text `#4F46E5`, border `1px solid #C7D2FE`. Hover: `#E0E7FF`, border `#A5B4FC`. Includes a single, un-animated 14px monochrome sparkle icon. No loud gradients.

### Chips & Status Indicators
- **Issue Priority & State Chips:** Height: 20px. Font: `JetBrains Mono, 11px`. Padding: `0 6px`. Border-radius: `4px`.
  - *P1 Critical:* Text `#B91C1C`, surface `#FEF2F2`, border `1px solid #FCA5A5`.
  - *In Progress:* Text `#4338CA`, surface `#EEF2FF`, border `1px solid #C7D2FE`.
  - *Resolved:* Text `#047857`, surface `#ECFDF5`, border `1px solid #A7F3D0`.
- Status indicators prioritize a leading 6px colored dot before text over full solid fills.

### Lists & Tables
- Borderless table styling: Rows separated by 1px hairlines (`#F1F5F9`). Row height: 40px (compact) to 48px (standard).
- Hover state: Row switches background to `#F8FAFC` instantly (`transition: background 100ms ease-out`). Left-edge 2px vertical highlight appears on keyboard focus using `#0F172A`.

### Input Fields & Controls
- **Inputs:** Height: 32px or 36px. Background `#FFFFFF`, border: `1px solid #E2E8F0`, placeholder: `#94A3B8`. Focus state: border `#0F172A`, outline `none`, optional `box-shadow: 0 0 0 1px #0F172A`.
- **Checkboxes & Radios:** 14px x 14px. Border `1px solid #CBD5E1`, border-radius: 3px (checkbox) or 50% (radio). Checked state: fill `#0F172A` with crisp white mark.

### Cards & Structural Containers
- Cards are discouraged as generic wrappers. When encapsulating self-contained objects (e.g., Runbooks, Metric Summaries), use `#FFFFFF` background, 1px `#E2E8F0` border, `border-radius: 6px`, and no drop shadow. Grouping must rely on 16px to 24px vertical whitespace and clear `label-caps` headings.

### AI Assistance Components
- **Inline Copilot Suggestion:** Rendered inline directly below ticket context in `#F8FAFC` container with a 2px left border of `#6366F1`. Typography in `13px Geist`. Action controls ("Apply fix", "Reject") appear as quiet inline text buttons (`#4F46E5` and `#64748B`).
- **Command Palette (`Cmd+K`):** Width: 600px. Background `#FFFFFF`, 1px border `#CBD5E1`, elevation level 3. Top input 44px with 16px font size, followed by filtered interactive list items grouped under uppercase `label-caps` headings. Keyboard navigation hints rendered in `JetBrains Mono` tags (`#F1F5F9` background, `#475569` text).