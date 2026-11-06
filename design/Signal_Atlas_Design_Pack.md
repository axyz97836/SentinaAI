# SentinelAI — Signal Atlas
## Final proposed visual direction and implementation handoff

**Status:** Design proposal for owner review. **No frontend implementation is authorized by this document.** Phase 7 backend work must remain undisturbed. Implement only when the owner explicitly authorizes the relevant frontend phase (planned Phase 9 onward). The 11 approved planning/security documents and `AGENTS.md` remain authoritative and unchanged unless specifically approved.

## 1. Creative north star

**Design name:** Signal Atlas  
**Positioning:** Editorial Risk Intelligence  
**Personality:** expressive but credible; analytical but human; visually memorable without compromising the operational workflow.

Translate the user's references into an original product language:
- **Oversized editorial type** and asymmetric poster compositions, inspired by the Change of Perspective visual.
- **Controlled abstract orbital geometry**, inspired by sculptural loops, but without copying images, purple gradients or glossy 3D marketing clichés.
- **Dramatic dark chapter panels**, inspired by high-contrast editorial pages, used sparingly for storytelling, not for dense tables.
- **Atlas-like contour lines, annotations, index numbers and footnotes**, inspired by cartographic editorial research layouts.

**Key distinction:** Landing/marketing surfaces can be artistic. Authenticated risk operations must be instantly legible, auditable and navigable.

**Writing tone:** Precise, calm and evidence-based. Do not claim real-world fraud accuracy. Do not use fake reviews, fake counters, invented ratings or vague AI promises. Avoid em dashes in website UI copy.

## 2. Brand and functional color system

| Token | Color name | Hex | Use |
|---|---|---|---|
| `--sa-ivory` | Warm Ivory | `#F9EBD7` | Editorial hero, warm landing background |
| `--sa-paper` | Soft Paper | `#FFF9F1` | Product cards and high-readability surfaces |
| `--sa-canvas` | Neutral Canvas | `#F5F3EB` | Product workspace background; less saturated than hero |
| `--sa-emerald` | Emerald Green | `#046A38` | Brand, analytical accents, active navigation, primary actions |
| `--sa-vermilion` | Vermilion | `#E34222` | Editorial art, callouts, large accents; avoid small low-contrast text |
| `--sa-navy` | Midnight Navy | `#1B1E4A` | Primary typography, dark editorial panels, navigation |
| `--sa-atlas` | Deep Atlas Navy | `#0E1D61` | Research charts, alternate dark section |
| `--sa-stone` | Warm Stone Grey | `#AFAEA2` | Quiet decorative lines and background fills, NOT small body text |
| `--sa-gold` | Antique Gold | `#B89A5A` | Mapping lines, selected accents, not body text |
| `--sa-crimson` | Crimson | `#D21319` | Critical risk, supported warning states |
| `--sa-ink` | Deep Ink | `#17271F` | Optional dark text where navy is not ideal |
| `--sa-border` | Linen Border | `#D9D4C8` | Dividers, restrained grid lines |

Suggested CSS design tokens:

```css
:root {
  --sa-ivory: #F9EBD7;
  --sa-paper: #FFF9F1;
  --sa-canvas: #F5F3EB;
  --sa-emerald: #046A38;
  --sa-vermilion: #E34222;
  --sa-navy: #1B1E4A;
  --sa-atlas: #0E1D61;
  --sa-stone: #AFAEA2;
  --sa-gold: #B89A5A;
  --sa-crimson: #D21319;
  --sa-ink: #17271F;
  --sa-border: #D9D4C8;
  --sa-radius-control: 6px;
  --sa-radius-panel: 4px;
}
```

Color accessibility: navy on ivory is high contrast; emerald on ivory is appropriate for regular text at about 5.7:1. Vermilion on ivory is about 3.5:1, below WCAG AA 4.5:1 for ordinary small text; use it for decorative geometry, larger marks, or pair a compliant darker variant for text. Gold and Stone Grey are decorative/secondary backgrounds, not standalone small-text colors. Ensure any semantic risk status has both text and icon/pattern, not color alone. Check all actual UI combinations with automated and manual contrast testing.

**Never use** lavender/chartreuse as the main SentinelAI product system; do not use purple gradients, arbitrary neon accents or excessively ornamental dashboard visuals.

## 3. Typography and hierarchy

- **Display / section headlines:** `Space Grotesk` weights 600–700, tightly tracked, editorial scale; large but responsive.
- **Editorial accent words:** `Instrument Serif` regular/italic for occasional emphasis in marketing and reports, not in compact tables or form fields.
- **Product UI / table content:** `DM Sans` weights 400–700.
- **Technical metadata (optional):** system monospace or `IBM Plex Mono` for transaction IDs, timestamps, version labels and trace annotations. Use tabular numbers.

Load only necessary weights/subsets after license/availability verification. System fallbacks required. Product table font sizes generally 13–14px, body 15–16px, avoid sub-12px live controls. Landing hero: clamp(3.5rem, 9vw, 9rem) subject to viewport and reading tests. Editorial annotations may use 11–12px where supplementary; essential information remains accessible.

## 4. Visual vocabulary

- Original vector concentric rings, orbit lines and contour-map paths, not downloaded stock imagery.
- Crosshair, index labels `01 / 02 / 03`, hairline rules, annotations and calibrated visual noise used sparingly.
- One strong illustration per main editorial section; avoid overwhelming functional surfaces.
- Square-to-6px radius controls; generally flat panels; restrained borders; no frosted-glass cards, pill controls or strong shadows.
- Prefer real charts supported by persisted synthetic/demo transactions. If no data exists, show explicit empty states, never imaginary KPI values.

## 5. Landing page wireframe

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ S/ SENTINELAI       PLATFORM  METHOD  SECURITY                    OPEN APP │
├───────────────────────────────────────────────────────────────────────────┤
│  01 / INTELLIGENCE                                  ATLAS FIELD / 2026    │
│                                                                           │
│  SEE THE                   [original editorial orbit / contour graphic]    │
│  SIGNAL.                                                                  │
│  TRACE THE                                                                │
│  REASON.                                                                  │
│                                                                           │
│  Risk scoring and investigation for fictional transaction data.           │
│  [EXPLORE PLATFORM]    [HOW IT WORKS]                                      │
├───────────────────────────────────────────────────────────────────────────┤
│  INPUT / VALIDATE         MODEL / SCORE        EVIDENCE / INVESTIGATE      │
├───────────────────────────────────────────────────────────────────────────┤
│  02 / THE METHOD: honest four-step flow and actual product screenshots    │
│  03 / EXPLANATIONS: component comparison, with real labels/caveats        │
│  04 / LIMITATIONS: synthetic-demo transparency and privacy/terms drafts  │
└───────────────────────────────────────────────────────────────────────────┘
```

**Hero copy**
- Eyebrow: `TRANSACTION INTELLIGENCE / DEMONSTRATION PLATFORM`
- Headline: `SEE THE SIGNAL. TRACE THE REASON.`
- Subcopy: `Score synthetic transactions, inspect risk signals and keep the evidence behind each decision in view.`
- Primary action: `Explore the platform` (must lead to working route).
- Secondary action: `How it works` (must scroll to a real section).
- Transparency note: `Demonstration data only. Scores are screening signals, not proof of fraud.`

Hero composition desktop: approximately 55% type / 45% original procedural illustration; mobile stacks readable type, then reduced artwork. Do not mimic or reproduce user-provided websites verbatim.

## 6. Authenticated product dashboard wireframe

```text
┌───────────────────────────────────────────────────────────────────────────┐
│ S/ SENTINELAI   RISK INTELLIGENCE                [ORG] [SESSION / ACCOUNT]│
├─────────────┬─────────────────────────────────────────────────────────────┤
│ OVERVIEW    │  OVERVIEW / 01                  [DATE RANGE] [REFRESH]        │
│ TRANSACTIONS│  Transaction intelligence                                │
│ ALERTS      │  [real observed totals only / actionable empty state]      │
│ CASES       │  ┌────────────────────────────┬────────────────────────┐   │
│ REPORTS     │  │ RISK DISTRIBUTION          │ REVIEW QUEUE           │   │
│ MODELS      │  │ real chart + text summary  │ real recent alerts     │   │
│ SETTINGS*   │  └────────────────────────────┴────────────────────────┘   │
│             │  TRANSACTION LEDGER                                       │
│             │  [Search] [Band] [Period]                                 │
│             │  TIME    TRANSACTION     AMOUNT      SCORE    STATE        │
│             │  ... actual organization-scoped rows only ...             │
│             │                                                             │
│             │  Selected transaction opens full detail/reason workspace.  │
└─────────────┴─────────────────────────────────────────────────────────────┘
```

*ADMIN only. Avoid fake pages and inactive navigation before the relevant phase exists.*

Product principles: one restrained utility/navigation rail, large editorial section title, then efficient charts/tables. Do not fill the screen with oversized KPI cards. For analysts, transaction table and alert queue get priority over decorative charts. Use accessible density settings and sticky headings on desktop if useful. The left navigation collapses behind a real menu control on mobile; transaction tables reflow to cards or scroll within their own region, not the full viewport.

## 7. Transaction explanation page

- Top: compact transaction metadata, risk band, 0–100 risk score, event timestamp, immutable model version.
- Main: component breakdown (`supervised`, `anomaly percentile`, `rule signal`) with the persisted weights and matching arithmetic; clearly mark screening score vs probability.
- Rules: evidence by state (`Fired`, `Evaluated / no hit`, `Not evaluated`, `Disabled`) with stored parameters, never inferred historical evidence.
- ML contributions: up to five genuine supervised-model contributions when available, with correct units and `COMPLETE`/`PARTIAL` status.
- Side panel: linked alert/case (only when endpoints exist), immutable scoring snapshot and cautious caveat.
- Empty or incomplete explanations remain informative, never fabricate attribution.

## 8. Components and interaction rules

| Component | Appearance | Behavior |
|---|---|---|
| Primary button | Emerald rectangle, 4–6px radius | Working action, focus ring, loading and error state |
| Secondary button | Border + navy text | No decorative dead ends |
| Critical action | Dark compliant red with clear wording | Confirmation when destructive; not color alone |
| Panels | Flat paper surface, 1px linen border | Strong headings, consistent spacing |
| Data table | Dense, readable, tabular figures | Search/filter/sort/pagination where supported |
| Risk label | Text plus small shape/icon + semantics | Distinguish LOW/MEDIUM/HIGH/CRITICAL accessibly |
| Charts | Emerald/navy with vermilion highlight | Real data only; legends, data table and empty state |
| Form controls | Consistent 44px minimum interactive target | Validation and success/error messaging |
| Loading state | Subtle skeleton or progress label | No invented values or animated counters |

Motion: hover/focus transitions 120–220ms; restrained section reveal where appropriate; respect `prefers-reduced-motion`. Motion.dev may be used selectively later only after package review. No cursor-follow, heavy parallax or background motion that obscures data.

## 9. Responsive and accessibility QA

Test 320, 375, 768, 1024, 1440 and wide desktop widths. No page-level horizontal overflow; no cut-off buttons, illegible annotations or table content. Keyboard navigation and visible focus outlines. Semantic heading structure, form labels, text alternatives for charts, WCAG AA contrasts, reduced-motion checks. Functional mobile menu with logical focus management. Custom 404, real favicon, unique titles/descriptions, useful footer, current copyright year, accessible link targets and no placeholders. Protect routes, don't display ADMIN navigation to unauthorized users and enforce permissions in backend regardless of presentation.

## 10. Page-by-page rollout boundaries

- **Phase 7 (current):** backend rules/explainability only. This pack is for review, not implementation authorization.
- **Phase 8:** backend alert/case workflows only, per approved plan.
- **Phase 9:** implement responsive design system, shared shell, login, accessible navigation, legal drafts for review.
- **Later approved frontend phases:** wire actual transactions, risk overview, explanations, alerts, cases, reports and admin forms to existing APIs. Avoid dead nav and fake data in earlier phases.

Keep all approved code/stack architecture and project policies. Do not rewrite backend to suit the visual identity.

## 11. Acceptance criteria

1. Editorial identity visibly distinct from generic startup dashboard, with authentic illustrated concepts.
2. Brand colors and contrast rules applied consistently, no unintended purple/pills/glassmorphism.
3. Landing is visually memorable but text remains accessible and not deceptive.
4. Authenticated product prioritizes real data and analyst tasks, not decorative art.
5. Mobile, keyboard and WCAG AA readiness verified at agreed breakpoints.
6. Every route/control used is functional or visibly not yet available; no dead links.
7. Numbers are backed by database data; synthetic demo provenance disclosed.
8. No frontend implementation until owner explicitly approves relevant phase.
9. Existing 11 planning documents and AGENTS.md remain unchanged without approval.

## 12. Recommended process for a future frontend implementation phase

1. Confirm preceding backend phase merged and sync main safely.
2. Read the original documents, this approved design pack, UI UX Pro Max and Ponytail skills.
3. Present visual tokens/layout and owner-reviewed screenshot first, if visual sign-off is requested.
4. Implement page scope for that authorized phase only, with real application states.
5. Run lint, typecheck, production build, browser tests, mobile, a11y, link and security checks.
6. Ponytail Review, verified feature-branch commits, CI success, PR, owner approval before merge.

**Design decision:** Choose the `Signal Atlas` hybrid system: Warm Ivory + Emerald + Vermilion for expressive brand pages, Midnight Navy + Neutral Canvas for high-readability data operations. Do not use one giant ornamental landing-page composition inside the transaction table.
