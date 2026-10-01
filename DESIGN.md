---
name: Needle Admin
description: A warm, institutional operational control plane for parliamentary intelligence.
colors:
  paper: "#F2EBD9"
  paper-deep: "#E8E0CB"
  surface: "#FBF6E7"
  surface-warm: "#F7F0DC"
  ink: "#1A1812"
  ink-secondary: "#4B463A"
  ink-muted: "#665F50"
  line: "#D4C9AF"
  line-strong: "#B9AB8F"
  needle-green: "#006A4D"
  chrome-green: "#17372C"
  green-tint: "#DFE9E2"
  saffron: "#C76A1A"
  red: "#8B2E1F"
  blue: "#23496B"
typography:
  display:
    fontFamily: "IBM Plex Serif, Georgia, Times New Roman, serif"
    fontSize: "30px"
    fontWeight: 600
    lineHeight: 1.12
    letterSpacing: "-0.01em"
  headline:
    fontFamily: "IBM Plex Serif, Georgia, Times New Roman, serif"
    fontSize: "22px"
    fontWeight: 600
    lineHeight: 1.2
    letterSpacing: "-0.005em"
  body:
    fontFamily: "IBM Plex Sans, system-ui, -apple-system, sans-serif"
    fontSize: "14px"
    fontWeight: 400
    lineHeight: 1.55
  label:
    fontFamily: "IBM Plex Mono, ui-monospace, SF Mono, Menlo, monospace"
    fontSize: "11px"
    fontWeight: 500
    lineHeight: 1.2
    letterSpacing: "0.08em"
rounded:
  sm: "5px"
  md: "7px"
  lg: "10px"
  xl: "16px"
  pill: "999px"
spacing:
  xs: "4px"
  sm: "8px"
  md: "12px"
  lg: "16px"
  xl: "24px"
  page: "30px"
components:
  button-primary:
    backgroundColor: "{colors.needle-green}"
    textColor: "{colors.surface}"
    rounded: "{rounded.md}"
    padding: "9px 20px"
  button-secondary:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink-secondary}"
    rounded: "{rounded.md}"
    padding: "9px 20px"
  panel:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.lg}"
    padding: "16px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.ink}"
    rounded: "{rounded.md}"
    padding: "9px 12px"
---

# Design System: Needle Admin

## Overview

**Creative North Star: "The Parliamentary Operations Ledger"**

Needle Admin is the operational/control-plane expression of the Briefcase visual language: warm paper, precise ink, and quiet institutional authority. It is dense enough for daily diagnosis without adopting a generic SaaS-dashboard aesthetic. Hierarchy comes from typography, tonal paper layers, and disciplined borders rather than decoration.

The system is built for operate mode. Frequent work is direct, state is explicit, and unavailable data never masquerades as healthy or empty. Motion is limited to brief state feedback and respects reduced-motion preferences.

**Key Characteristics:**

- Warm order-paper canvas with a solid dark command rail.
- Serif institutional headings, sans-serif controls, and mono operational metadata.
- Compact bordered surfaces, restrained elevation, and semantic color.
- Persistent domain navigation, contextual local navigation, and explicit loading/error/empty states.

## Colors

The palette pairs warm neutral paper with a restrained green command color; saffron, red, and blue appear only when their operational meaning requires them.

### Primary

- **Needle Green:** Primary actions, active navigation, ready/healthy emphasis, and focus context.
- **Chrome Green:** Global navigation rail and other persistent command chrome.

### Secondary

- **Saffron:** Attention and warning states.
- **Institutional Red:** Failure, critical state, and destructive action.
- **Operational Blue:** Neutral information and non-success system state.

### Neutral

- **Paper and Deep Paper:** Application background and structural separation.
- **Surface and Warm Surface:** Panels, controls, table headers, and hover layers.
- **Ink, Secondary Ink, and Muted Ink:** Primary copy through accessible metadata.
- **Line and Strong Line:** Default and emphasized boundaries.

**The Semantic Color Rule.** Never use saffron, red, or blue as ambient decoration; each must communicate an operational state.

**The Unavailable Rule.** Missing data uses explicit unavailable copy and never inherits a green, zero, or all-clear presentation.

## Typography

**Display Font:** IBM Plex Serif (with Georgia and Times New Roman fallbacks)

**Body Font:** IBM Plex Sans (with system UI fallbacks)

**Label/Mono Font:** IBM Plex Mono (with platform monospace fallbacks)

**Character:** The pairing reads as an institutional document translated into an operational interface. Serif establishes authority; sans-serif carries task density; mono is reserved for identifiers, timestamps, metrics, and machine state.

### Hierarchy

- **Display:** Major command context and exceptional headings only.
- **Headline:** Page titles and primary section identity.
- **Title:** Panel and workflow headings, normally compact and sentence case.
- **Body:** Operational explanation and table content, usually constrained to readable line lengths.
- **Label:** Uppercase or compact metadata, filter labels, IDs, counts, and timestamps.

**The Three-Voice Rule.** Serif names the institution, sans-serif runs the work, and mono reports machine state; do not interchange them casually.

## Layout

Desktop uses a fixed global rail and a bounded content canvas. Each domain can add one persistent horizontal secondary navigation. Pages lead with task context, then operational state, then the principal working surface; equal-weight promotional card grids are not the default.

At tablet widths the global rail becomes a labelled overlay menu with a dismissing backdrop. Header actions wrap, metric strips collapse, and dense tables retain a labelled horizontal scroll region. Phone layouts stack filters and preserve operable controls rather than compressing data into illegibility.

Spacing follows a compact four-pixel-derived rhythm, with larger page gutters and section breaks used to separate workflows rather than decorate them.

## Elevation & Depth

The system is flat by default. Tonal surface changes and hairline borders establish most hierarchy. Low ambient shadows are reserved for bounded panels; stronger elevation belongs to modal dialogs, drawers, and mobile navigation overlays.

**The Flat-at-Rest Rule.** A surface does not receive extra lift merely to look interactive; state, layering, or obstruction must justify elevation.

## Shapes

Controls and ordinary panels use gently restrained corners. Small and medium radii belong to buttons, inputs, tabs, and compact notices; larger 10px and 16px radii are reserved for substantial panels, dialogs, and legacy deep-work surfaces. Pills are limited to compact status badges and the Admin identity marker.

Borders remain thin and even. Avoid thick one-sided accent borders, decorative glass, and gradient-filled chrome or buttons.

## Components

### Buttons

- **Shape:** Compact, gently curved, with primary and secondary controls sharing the same geometry.
- **Primary:** Needle green on a light text surface; one clear primary action per local context.
- **Secondary:** Paper surface with an ink border and green hover emphasis.
- **Focus:** A visible green focus ring remains present for keyboard navigation.
- **Destructive:** Institutional red, paired with confirmation when access or data is removed.

### Chips

- **Style:** Tinted semantic surface with dark semantic text; optional dot communicates machine state.
- **State:** Selected filters use the green tint. Pills do not become decorative labels.

### Cards / Containers

- **Corner Style:** Restrained for standard panels; larger only for dialogs and major legacy workspaces.
- **Background:** Surface over paper, with warm surface for subordinate rows and hover state.
- **Shadow Strategy:** Low ambient shadow at rest; structural border does most of the work.
- **Internal Padding:** Compact enough for operations, with stronger section gaps between workflows.

### Inputs / Fields

- **Style:** Warm light surface, visible line, compact radius, persistent label.
- **Focus:** Green border plus a visible outer focus ring.
- **Error / Disabled:** Error text is explicit; disabled state reduces emphasis without hiding the value.

### Navigation

The global rail is solid command green with cream typography. Active items use a restrained tint and small edge marker. Secondary navigation is horizontally scrollable, sentence case, and persists across sibling tools. Narrow screens use a labelled menu button and focus-visible controls.

### Operational Data State

Loading reserves layout with skeleton rows. Errors name the unavailable source and provide a safe retry where possible. Empty states are used only after a successful response proves that no records match.

## Do's and Don'ts

### Do:

- **Do** preserve customer, tenant, seat, message, or case context in headings and links.
- **Do** keep retry actions limited to states whose backend semantics make another attempt safe.
- **Do** use responsive table regions, explicit labels, visible focus, and keyboard-operable dialogs.
- **Do** keep platform-wide and tenant-scoped authority visible in the interface copy.

### Don't:

- **Don't** turn failed requests into zero counts, healthy badges, or empty tables.
- **Don't** duplicate tenant geography or government workflows merely to fill an Admin navigation slot.
- **Don't** introduce decorative gradients, thick side accents, oversized promotional cards, or gratuitous motion.
- **Don't** expose credentials, tokens, sensitive payloads, or raw secret-bearing diagnostics.
