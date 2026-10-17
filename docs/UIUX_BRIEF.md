# SentinelAI | UI/UX Design Brief

**Version:** 1.1 approved baseline (revised 2026-10-16)  
**Status:** Owner approved; design direction only, not yet implemented  
**Visual objective:** Quiet, precise, trustworthy operational software, not an AI-themed marketing template.

## 1. Design principles

1. **Evidence before decoration:** Every figure is drawn from stored demo data, measured model results, or labeled sample fixtures. No simulated customer traction, bogus accuracy claims, or fake testimonials.
2. **Scannable under pressure:** Consistent location of search, filters, status, risk, timestamp and next action.
3. **Explain the score honestly:** Label composite score and supervised probability separately. Always show model version and screening caveat.
4. **Case work over novelty:** Alerts and case transitions require explicit confirmation/notes where needed; keep timelines easy to read.
5. **Accessible by default:** Full keyboard access, visible focus, form labels, status text independent of color, semantic headings.
6. **Mobile usable:** No horizontal **page** overflow. Prefer card views for compact data rather than hiding essential information in clipped tables.
7. **Functional feedback:** Show progress, completion, failure and recovery. No fake loading timers.
8. **Minimum motion:** Only subtle interface feedback that assists state changes and respects reduced-motion preferences.

## 2. Forbidden design shortcuts

Strictly avoid: purple gradients, pill-shaped buttons, fake social proof, fake metrics/reviews/counters, vague hero slogans, emoji icons, em dashes in **website copy**, synthetic AI-stock photos, generated generic marketing text, cursor trails, parallax effects, exaggerated scroll reveals, decorative animation, unfinished placeholder UI, broken actions, and unused navigation.

Do not expose unwanted “Made with AI” branding **where removal is legally and technically permitted**. Do not remove required attribution. If a provider makes compliant removal impossible, switch provider or block launch until the issue is resolved.

## 3. Visual direction and foundational tokens

| Element | Direction | Reason |
|---|---|---|
| Theme | **Light-first** MVP; optional dark theme in v2 | Dense analytics charts remain readable and low-cost to build |
| Background | Neutral off-white `#F7F8FA` | Reduces distraction |
| Surface | White `#FFFFFF` with very subtle borders | Distinguishes panels without floating-card overload |
| Main text | Near-black `#17212B` | Readable, restrained |
| Secondary text | Slate `#52616D` | Clear hierarchy |
| Primary action | Deep navy `#163A5F` with visible focus outline | Professional, not neon or purple |
| Interactive link | Accessible blue `#185A96`, underlined when embedded in body text | Recognizable without relying on shape |
| Risk LOW | Muted green `#216E4E` + label `Low` | Semantically distinct |
| Risk MEDIUM | Amber/brown `#8A5A00` + label `Medium` | Contrast on light background |
| Risk HIGH | Burnt orange `#B54708` + label `High` | Progressive urgency |
| Risk CRITICAL | Deep red `#B42318` + label `Critical` | Reserved for highest screening urgency |
| Unavailable/neutral | Slate gray `#667085` + explicit text | No invented meaning |
| Typography | System UI sans-serif until [Fonts: to be added] | Fast, familiar and readable |
| Buttons | Rectangular / 6px corners, 40–44px minimum hit area | No pill buttons; accessible tapping |
| Panels | 6–8px corners, 1px neutral border, no heavy shadow | Calm UI |
| Spacing | 4px base scale: 4/8/12/16/24/32 | Predictability |
| Grid | 12 columns desktop; 6 tablet; 1–2 mobile | Responsive consistency |

The hex suggestions are **initial tokens**, subject to contrast validation. Icons must be accessible non-emoji vector or CSS icons [source: to be added]. Never use red/green color as the only way to communicate risk.

## 4. Layout system

### Desktop >=1024px

- Sidebar 232px with brand, navigation, role label, account menu; main max-width about 1440px.
- Sticky top row: page title, optional short description, page-level action, last updated indicator.
- KPI summary with 3–4 compact cards, actual values only.
- Core operational tables show filters above column headers; detail pages use two-column layout (main context + side actions).

### Tablet 768–1023px

- Collapsible navigation rail; filters can wrap to second row.
- Two-column cards; transaction details become one main column plus side panel below.

### Phone 320–767px

- Accessible menu button opens drawer with labeled navigation, focus trap and dismiss control.
- Single column, controls at least 44px touch height, filter panels stack; details use top-to-bottom priority.
- Transaction/case table becomes a list of structured summary cards (reference, score, status, date, action). A wide data chart may scroll *inside its labelled container* without moving the page horizontally.
- Prevent overflow from long IDs using wrap/break and carefully constrained flex items.
- Fixed viewport never clips primary buttons or legal footer links.

## 5. Full screen inventory and components

The route names are contractually identical to `APP_FLOW.md`.

| Route | Audience | Components and main actions |
|---|---|---|
| `/login` | Public | Logo, form with labels, inline error, submit loading state, demo-data note, legal footer |
| `/dashboard` | All signed in | Actual period-scoped metrics, risk band chart, alert timeline, recent alerts, case status summary, date filter, last updated |
| `/transactions` | All signed in | Search/filter, paginated transaction list or mobile cards, `New simulated transaction` form, `Upload CSV` link |
| `/transactions/upload` | All; training only ADMIN | Purpose and source/provenance selector, verified license field for public data, schema checklist, file drop/select, 10 MiB notice, upload button, job status/progress, row validation summary |
| `/transactions/[id]` | All signed in | Transaction header, score/band, component breakdown, top feature explanations, fired rules, model version, related alert and case action |
| `/alerts` | All signed in | Priority counts, `NEW`/`IN_CASE`/`DISMISSED` filters, risk badges, alert list, open-case/dismiss action with required reason |
| `/cases` | All signed in | Status filters, assigned user, case list, latest update, links to detail |
| `/cases/[id]` | All signed in | Linked transaction/alert, immutable facts, assigned analyst, workflow controls, note entry, append-only timeline, resolve dialog |
| `/reports` | All signed in | Date range, observed totals, outcomes chart, export button, queued job status, authenticated download |
| `/admin/settings` | ADMIN | Model version/status card, labeled TRAINING datasets, train/activate buttons, risk band threshold editor, versioned rule toggles/parameters, recent audit summary |
| `/admin/users` | ADMIN | Demo user roster, role selector, confirmation, last-admin guard explanation |
| `/privacy` | Public | Accurate project-specific Privacy Policy, update date, contact only when authorized |
| `/terms` | Public | Accurate Terms and Conditions, demo/data disclaimer, update date |
| `not-found` (custom 404) | Public | Explanation, accessible path to home/login, no broken navigation |

**No separate marketing landing page in MVP.** Root route simply routes to login or dashboard. Add no empty “Features”, “Pricing”, or “Customers” navigation items.

## 6. Components and states

| Component | Required states and behavior |
|---|---|
| Primary/secondary button | Default, focus, hover, disabled, busy; never claim action completed before server confirms |
| Form input | Label, hint, required marker, invalid message connected to field, character limit where applicable |
| Risk badge | Text (Low/Medium/High/Critical) + accessible contrast; optional simple shape/icon, not emoji |
| Status label | NEW / IN_CASE / DISMISSED and OPEN / IN_REVIEW / CLOSED shown as human-readable text |
| Pagination | Stable next/previous cursor navigation; filter reset behavior clear |
| Alerts/cases actions | Destructive or consequential choices ask for reason/confirmation |
| Toast/feedback | Success after verified API response; persistent actionable error for failure; live region announcements |
| Loading | Skeleton only if useful, with accessible text; no fake progress bars or forced delays |
| Data missing | “Not evaluated” or “Unavailable”; never translate unknown into zero |
| Empty state | Explain what is absent and offer a relevant next action |
| Session expired | Message, clear protected state, redirect to sign-in |

## 7. Data visualization plan

| Question | Chart / representation | Why it fits | Fallback |
|---|---|---|---|
| How many transactions are in each risk band? | Horizontal bar chart, sorted Low to Critical | Exact categorical comparison | Accessible table and counts |
| Is activity changing over time? | Line chart of daily transaction count | Trend without deceptive area | Date/value table |
| Where are high-risk alerts concentrated? | Stacked bar of alert status by day (only if enough observed records) | Shows status mix over time | Status count list |
| How are cases being resolved? | Bar chart of `CONFIRMED_FRAUD`, `FALSE_POSITIVE`, `INCONCLUSIVE` outcomes | Better comparison than a decorative donut | Numbered summary table |
| Why this score? | Three labelled proportional bars (supervised contribution, anomaly component, rule component) plus SHAP feature list | Shows additive parts without implying probability | Text breakdown |
| What happened to this case? | Chronological event timeline | Causality and attribution | Ordered event list |
| Which transactions need action? | Sortable table on desktop, prioritized cards on phone | Supports analyst triage | Plain accessible list |

**Chart honesty:** Always label units, timezone, range, denominator, and missing-data behavior. Do not show a chart with invented data. Tooltips must be keyboard reachable or have equivalent visible text. Use accessible contrast and text in addition to color.

## 8. Interaction and motion rules

- Fast state transitions: 120–180ms simple opacity/background change only when informative; avoid entrances for every card.
- No smooth-scrolling spectacle, sticky animated cursors, page-wide parallax, or automatic chart count-up animations.
- Respect `prefers-reduced-motion: reduce` by removing non-essential transitions.
- File job status may poll; do not animate percentage unless actual processed-row counts exist.
- Buttons provide immediate pressed/loading feedback, then display server-confirmed outcome.
- Unavailable actions are disabled with explanation, not inert clickable controls.

[Frontend animations: Motion (motion.dev) is the preferred choice; Anime.js (animejs.com) only for a documented custom interaction; neither is mandatory]

### Approved motion budget and library selection

| Interaction | Duration target | Default implementation |
|---|---|---|
| Button/input feedback | 100–150ms | Native CSS |
| Menu/sidebar | 150–200ms | CSS or Motion |
| Modal/dialog | 150–250ms | CSS or Motion with focus handling |
| Chart filter update | 200–350ms, if helpful | Bklit UI chart motion or instant update |
| Upload/ML job progress | Reflect real job status; no invented time | Accessible polling state, optional subtle transition |

Never animate every KPI number, display fake progress, smooth-scroll the entire site, or add 3D elements merely because a source website demonstrates them. Support reduced motion and avoid multiple overlapping animation libraries. Test layout shift and interaction responsiveness on a mobile device or emulation.

## 9. Accessibility requirements

- Aim for WCAG 2.2 AA on key workflows; do not claim formal certification without audit.
- Semantic header/nav/main/footer, logical heading structure, correctly labelled controls, descriptive links.
- Visible focus ring; no keyboard trap outside modal behavior; Escape closes menus/dialogs and restores focus.
- At least 4.5:1 contrast for normal text, 3:1 for large text and meaningful UI visuals where applicable.
- Announce submit success/error and asynchronous job updates politely; avoid noisy continual live announcements.
- Touch targets 44px where possible, no actions that only work on hover.
- Data tables with headers, meaningful empty states, export alternatives for complex charts.
- Automated a11y scans plus manual keyboard and screen reader spot checks.

## 10. Microcopy style and examples

**Voice:** Specific, factual, calm, concise, unambiguous. Prefer verb-object buttons such as “Upload CSV”, “Open case”, “Resolve case”, “Export report”. Avoid hype or claims of AI certainty.

| Situation | Approved example |
|---|---|
| Success | “Transaction scored. Risk: High.” Display the actual computed score alongside it. |
| New alert | “This transaction crossed the configured alert threshold.” |
| Model nuance | “Risk score is a screening signal, not a fraud probability.” |
| Missing history | “Transaction history is insufficient to evaluate device changes.” |
| File validation | “CSV missing required column: occurred_at.” |
| Export queued | “Report requested. You can leave this page while it is prepared.” |
| Case resolved | “Case closed as Inconclusive. The decision was added to the timeline.” |
| No results | “No alerts match these filters.” |
| Error | “Could not save the rule. Check the value and try again.” |

Avoid invented text like “Trusted by 10,000 teams” or “Revolutionize your financial future.” If actual numbers appear in a demo screenshot, clearly label the page as sample/demo data.

## 11. SEO, content, and release UX gate

- Accurate per-page `<title>` and meta description; private operational pages should not be marketed as public indexable content. Login, Privacy, and Terms have appropriate metadata.
- Favicon installed; accurate copyright year at launch; footer Privacy/Terms links function from every route.
- Custom 404 links home/login; clickable brand logo; `mailto:` and `tel:` where real contact info appears.
- Image sizes optimized; prefer SVG/CSS for charts/marks and omit filler photography.
- Test for broken links/buttons, mobile overflow, menu focus, success/error states, abandoned placeholder copy, unused navigation, and slow assets.
- Launch requires actual custom domain and HTTPS, privacy policy, terms, and compliant removal of any unwanted builder badge.

## 12. Reference placeholders to fill later

| Type | Owner-supplied reference | Decision needed |
|---|---|---|
| UI inspirations | Manus (https://manus.im), ThreeUI (https://threeui.com/browse) as **reference only**; [Additional references: to be added] | Exclude heavy 3D/shader effects from MVP |
| Components | Kokonut UI (https://kokonutui.com), only selectively | Accessible primitives, shape overrides and license |
| Charts | Bklit UI (https://bklit.com/docs/components) | Readability, reduced motion, license, bundle size |
| Motion | Motion (https://motion.dev) primary; Anime.js (https://animejs.com) optional | Only purposeful state feedback |
| Agent skill | UI UX Pro Max (https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | Verify local skill installed; treat as optional design reference |
| Icons | [Icons: to be added] | Non-emoji SVG set |
| Typography | [Fonts: to be added] | Typeface, loading and license |
| Chart details | [Selected Bklit component variants: to be chosen] | Labels, contrast, keyboard equivalence, no gradients |
| Imagery | [Images: to be added, if actually needed] | No AI-slop visuals; verify licenses |
| Data | [Datasets: to be added] | License, non-sensitive provenance and label limitations |

### Approval hierarchy and component intake

1. SentinelAI product truthfulness, UX restrictions, WCAG target, responsiveness and this design brief come first.
2. UI UX Pro Max is **suggestion-only** in VS Code. Verify that the skill file is present and the agent can read it. The user previously requested its installation; do not assume it succeeded.
3. External UI libraries are **not** a blanket design system or theme. Before installing a component: check license, dependencies, security, sizes, touch/keyboard behavior, color/shape customization and production bundle impact. Prefer simple native components when a dependency adds little value.
4. Reject demo content included with libraries, including fake charts, testimonials, users, revenue, counters, vague hero text and decorative photos. All KPI/card/chart values must come from live API data or be conspicuously marked local synthetic demo fixtures with genuine counts.
5. Keep full-page screenshots at desktop and 375px mobile for key routes; record any visual/interaction issues before marking a phase complete.

## 13. Design deliverables and sign-off

During Phase 9, create a simple sitemap and low-fidelity wireframes for `/dashboard`, `/transactions/[id]`, `/alerts`, and `/cases/[id]` **before** visual polishing. Review one desktop and one 375px phone view for each key screen. Do not code a full marketing site or add decorative content that does not support the operational tasks.
