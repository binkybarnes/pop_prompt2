# Reorder Alert UI — Design Spec

**Date:** 2026-04-18
**Status:** Approved, ready for implementation planning
**Project:** Hack the Coast 2026 · POP Problem 1 (Demand & Order Intelligence)

---

## 1. Purpose

Build a prototype web UI on top of the F1 reorder-alert pipeline (`pipeline/09_reorder_alerts.ipynb` + `pipeline/10_backtest.ipynb`). Two goals, in priority order:

1. **Demo narrative** — a "TradingView-style" per-lane drilldown that carries the money-slide story: *"If POP had followed these alerts, the 2023 `T-32206 SF` stockout would have been largely prevented."*
2. **Operational utility** — a Linear-style list view a buyer could actually open on a Monday morning to see what needs a PO this week.

**What a "lane" means in this UI:** a `(SKU × DC)` pair. Inventory and reorder decisions live at that grain. Channel and customer are demand-side breakdowns shown inside a lane, never lane dimensions. There are 107 lanes in the backtest.

**Scope:** prototype, not production. No auth, no backend, no writes, no real-time. Demo-first, buyer-usable second.

---

## 2. Architecture

### Shell
Two-tab Next.js app:
- **Reorder Alerts** (tab 1) — fully built.
- **Demand Curves** (tab 2) — stubbed to `"coming soon"`. Route exists; shell reserves the slot for F2 without rework.

### Routes
- `/` → redirects to `/alerts`
- `/alerts` → List view (home)
- `/alerts/lane/[slug]` → Lane view. Slug format: `SKU-DC`, e.g. `T-32206-NJ`.
- `/curves` → F2 stub.

### Data model: JSON on disk, no server
- Static export (`next.config.mjs: output: 'export'`). Build produces `ui/out/`, deployable as static files.
- Data lives in `ui/data/` as committed JSON. Pipeline notebooks (09, 10) each get a new final cell that dumps artifacts to `ui/data/`.
- UI never reads parquet, never parses Excel, never sees row-level transactions.
- Rebuild cycle: pipeline re-runs → `ui/data/*.json` updates → commit → `npm run build` → redeploy.

### Rendering strategy
- Next.js 15 App Router, React 19, TypeScript (strict).
- **Server components by default.** Read JSON from `ui/data/` at request/build time in server components.
- **Client components only for interactive leaves:** filter chips, sortable table headers, chart canvas, tab switcher, counterfactual toggle. Push `'use client'` down the tree, never at the page level.

### State
- **URL is the source of truth.** Filters encoded as query params (`?dc=NJ&confidence=high&status=flagged`). Lane identity encoded in route slug.
- No Redux / Zustand / Context-for-state. The only React state is ephemeral UI (chart hover, tab selection, counterfactual toggle).
- Deep-linking works for demo URLs ("here's `T-32206 SF`'s lane pre-set to P90 view").

### Stack
- Next.js 15, React 19, TypeScript strict
- Tailwind CSS (Linear-density tokens)
- Recharts for all charts
- No state library, no auth library, no API client
- Vercel React best-practices guidance applied (server components first, co-located components, minimal client boundaries)

---

## 3. Data contract

Pipeline notebooks write to `ui/data/`. The directory is committed to git (small, rebuildable, enables UI builds without re-running the pipeline).

| File | Source notebook | Shape | Consumer |
|------|-----------------|-------|----------|
| `alerts_today.json` | 09 | Array ~233 rows (one per `SKU × DC`), flagged + unflagged. Columns match `reorder_alerts.parquet` plus SKU description / brand for display. Embeds a 26-point `on_hand_sparkline` per row for the List-view sparkline. | List view |
| `lanes_index.json` | 10 | Array of 107 lane summaries: `sku, dc, sku_desc, brand, fresh_rate, today_flag, today_confidence, precision, recall, median_warning_weeks`. Used for lane navigation and summary stats. | List view, side-list fallback |
| `lane/{SKU}-{DC}.json` | 10 | Per-lane time series (weekly): `week_start`, `on_hand_est`, `reorder_point_mean`, `reorder_point_p90`, `run_rate_mean`, `run_rate_p90`, `alert_fired_mean`, `alert_fired_p90`, `fresh_stockout`, `weeks_until_stockout`. Plus a `today` object with today's recommendation (from step 09). Plus `metadata` object: `case_pack, vendor, country, lead_time_wk, lead_time_source, brand, sku_desc`. | Lane view (Chart + Backtest + Strategy tabs, Side panel) |
| `lane/{SKU}-{DC}_demand.json` | new cell in 10 | Same time axis as the lane JSON. Weekly demand split by channel: `{ week_start, MM, AM, HF }`. Plus `top_customers` array: `[{ custnmbr, name, share_pct, weekly_cadence }]` for up to 5 customers. | Lane view demand breakdown |
| `lane/{SKU}-{DC}_counterfactual.json` | 10 | **Written for all 107 lanes.** Three simulated `on_hand` trajectories along the same time axis: `actual`, `mean_followed`, `p90_followed`. Plus `simulated_pos` array: `[{ strategy, order_week, arrival_week, qty }]` for the green-circle markers. Plus `trough_delta` object: `{ actual: -330000, mean: -242000, p90: -212000 }` for the delta readout card. Authored `narrative` object (three toggle-aware taglines) **only populated for showcase lanes**; `null` otherwise. | Lane view counterfactual overlay + delta card |
| `backtest_summary.json` | 10 | Aggregate metrics: mean recall, median warning weeks, per-strategy scoring, flagged-alert count by confidence tier. | List view summary row |

### Lane file naming
Slug = `SKU` + `-` + `DC code`. Total: 107 × 3 (lane + demand + counterfactual) = 321 files under `ui/data/lane/`. Each file is small (~160 weekly rows × a handful of columns).

### Showcase lanes
Three lanes get authored narrative taglines and extra counterfactual polish:
- `T-32206-SF` — the canonical money slide (−330k trough → −212k under P90)
- `T-32206-NJ` — same SKU, different DC, demonstrates multi-DC behavior
- `F-04111-NJ` — POP Ginger Chews Original, demonstrates non-Tiger-Balm SKU

Non-showcase lanes get the same structural data but no authored taglines; the chart speaks for itself with computed numeric deltas.

### What is *not* in the contract
Raw sales rows, raw chargebacks, inventory snapshots, item master rows. The UI only sees pre-aggregated lane-level data.

---

## 4. List view (`/alerts`)

### Purpose
Monday-morning landing. Buyer glances and sees "OK, 109 high-confidence alerts today" and clicks the first row.

### Layout
- Tab bar across top.
- Filter chip row (`DC` / `Confidence` / `Status`).
- Summary stats row ("165 alerts · 109 high · 28 medium · 28 low", filter-responsive).
- Sortable data table.

### Filter chips
- **DC**: `SF / NJ / LA / all`
- **Confidence**: `high / medium / low / all`
- **Status**: `flagged / not flagged / all`
- Chip state lives in URL query params. Default: `status=flagged` (so the landing page only shows actionable items; one-click chip to expand to all).

### Table columns
`SKU │ Product │ DC │ On hand │ Cover (wk) │ Suggested (cases) │ Confidence │ Sparkline │ Alert?`

- **Sparkline**: inline SVG of the last 26 weeks of `on_hand_est`. Data embedded in `alerts_today.json` row (no extra fetch). ~80px wide, trailing reorder-point reference dashed behind it.
- **Row click**: entire row is the link target → `/alerts/lane/[slug]`. Linear-style.
- **Default sort**: confidence desc, then cover asc. Sort state is *not* in URL (ergonomic, not shareable).

### Empty state
If filters produce zero rows: "No alerts match these filters. [Clear filters]"

### No search
107 lanes is small enough to scroll/filter. Search deferred.

### Density
Compact rows (~36px), monospace for numeric columns, sans-serif for text. Linear-style visual vocabulary.

---

## 5. Lane view (`/alerts/lane/[slug]`)

### Layout (3 regions, desktop ≥1200px)

```
┌───────────────────────────────────────────────────────────────┐
│  Header: SKU · Product · DC · Confidence · Today's recommendation │
├───────────────────────────────────────────────────────────────┤
│  Tab bar: [Chart] [Backtest] [Strategy]                       │
├──────────────────────────────────────┬────────────────────────┤
│                                      │  Side panel (fixed ~280px) │
│           Main chart area            │  - Why firing? (plain English) │
│                                      │  - SKU metadata        │
│                                      │  - Lane stats          │
├──────────────────────────────────────┴────────────────────────┤
│  Demand breakdown: stacked-by-channel area chart + top customers │
└───────────────────────────────────────────────────────────────┘
```

Narrow viewports (<1200px) get a stacked fallback — chart then side panel then breakdown. Not a redesign; just readable.

### Header
- Back link to `/alerts`.
- `SKU · Product name · DC` as primary title.
- Confidence badge (high / medium / low).
- One-line today's recommendation: *"Alert firing · suggest 7,571 cases · lead time 12 wk · run rate 17.7k/wk"*. If no alert: *"No alert. 49 wk cover. Run rate 5.1k/wk."*

### Tab A — Chart (default)

**Main chart** (Recharts):
- X: time, 3 years weekly.
- Y: units.
- Lines:
  - `on_hand_est` — solid blue
  - `reorder_point` — dashed amber (mean or p90 depending on current strategy selection)
  - Counterfactual overlay (when active) — dotted green (mean) or teal (p90)
- **Alert markers**: triangle glyphs on timeline at every historical alert firing. Red triangles precede real stockouts (true positives); gray are benign. Hover reveals `fired, warned N wk before stockout`.
- **Stockout markers**: small red X on weeks where `fresh_stockout = True`.
- **Counterfactual toggle** (segmented control above chart): `Actual only / + Mean / + P90`. Adds/removes overlay lines (Actual is always drawn).
- **Zoom**: drag-select to zoom X range; double-click to reset. Keyboard `[` / `]` to pan by 4 weeks.
- **Simulated PO arrival markers** (when a counterfactual overlay is active): small green circles along the overlay line at `arrival_week`. Hover shows `ordered {qty} u at {order_week} ({lead_time_wk} wk lead)`.

**Showcase-lane banner** (only for showcase lanes): short authored tagline above the chart, updates with the toggle state. Non-showcase lanes get a computed numeric tagline ("Trough improvement: Actual −330k → P90 −212k = +118k units saved").

**Delta readout card** (always visible when a counterfactual overlay is active): `Actual trough: −330k · Mean-followed: −242k · P90-followed: −212k (improvement: +118k units)`.

### Tab B — Backtest

"Show your work" table:
- Every historical `as_of_week` with an alert firing for this lane.
- Columns: `as_of_week, reorder_point, on_hand_at_asof, alert_fired, weeks_until_stockout, was_true_positive`.
- Summary block above: `precision, recall, median_warning_weeks` for this lane.

### Tab C — Strategy

Mean vs. P90 comparison for this lane:
- Side-by-side card comparing: alerts fired, true positives, false positives, median warning weeks, total suggested units ordered.
- Takeaway line: *"P90 fires 2× more alerts but catches 50% more real stockouts — recommended for volatile lanes like this one."*
- For showcase lanes, an authored prose caption from the backtest notebook.

### Side panel (fixed, always visible)

**"Why firing?" block** (only when today's alert fires):
- Plain-English derivation: "We project 12 weeks of lead time × 17,700 units/wk = 213k needed, + 147k safety stock = 360k reorder point. You have 318k."
- Concrete numbers: `on_hand`, `reorder_point`, `gap`, `suggested_qty` in both units and cases.

**SKU metadata**: `case_pack, vendor, country, lead_time (wk + source), brand, SKU`.

**Lane stats**: `fresh_rate, avg_run_rate (mean + p90), coefficient of variation, weeks of data available`.

### Demand breakdown (always visible, bottom region)

- Stacked-area chart, same X axis as main chart. Colored by channel (MM / AM / HF).
- Pulls from `lane/{slug}_demand.json`.
- Below it: top 5 customers by volume for this lane, each with `custnmbr, name, share_pct`, and a small sparkline-style bar indicating weekly order cadence.

---

## 6. Counterfactual overlay (detailed)

### The three lines

| Line | Color | Source | Meaning |
|------|-------|--------|---------|
| Actual | Solid blue | `lane/{slug}.json → on_hand_est` | What really happened in POP's inventory rewind. |
| Mean-followed | Dotted green | `lane/{slug}_counterfactual.json → mean_followed` | Simulated: at each `as_of_week`, if mean-strategy alert fired, inject simulated PO arrival `lead_time_wk` later, sized by mean-strategy `suggested_qty`. |
| P90-followed | Dotted teal | `lane/{slug}_counterfactual.json → p90_followed` | Same, using P90 run-rate — fatter safety stock, more alerts, earlier / larger POs. |

### Toggle semantics
- Three-state segmented control: `Actual only / + Mean / + P90`.
- Actual is always drawn; the toggle only adds/removes overlay lines.
- Default: `Actual only`. Reveal happens on click so the demo can land the narrative one layer at a time.

### Simulated PO markers
Small green circles along the overlay trajectory at `arrival_week`. Hover reveals `(strategy, order_week, arrival_week, qty)`. Visualizes the warning-lead time: markers land before the actual line starts crashing.

### Banner callout (showcase lanes only)
Authored taglines per overlay state. Three strings per showcase lane, loaded from `narrative` object in counterfactual JSON. Example for `T-32206-SF`:
- Actual only: *"T-32206 SF ran out of stock June 2023 — trough of −330k units."*
- +Mean: *"Mean-strategy would have flagged 10 wk earlier; trough reduced to −242k."*
- +P90: *"P90 strategy would have prevented most of the dip. Trough reduced to −212k."*

### Delta readout card
Below the chart, always visible when an overlay is active. Three numbers: `actual_trough, mean_trough, p90_trough`, plus computed improvement delta in units. Concrete ROI proxy.

### Non-showcase lanes
Overlay works identically, just no authored tagline. Banner falls back to computed numeric statement.

---

## 7. File layout

```
pop_prompt2/
├── ui/                                    ← all UI code
│   ├── app/
│   │   ├── layout.tsx                     shell + tab bar
│   │   ├── page.tsx                       redirects / → /alerts
│   │   ├── alerts/
│   │   │   ├── page.tsx                   List view
│   │   │   └── lane/[slug]/page.tsx       Lane view
│   │   └── curves/page.tsx                F2 stub
│   ├── components/
│   │   ├── shell/                         TabBar, Header
│   │   ├── list/                          AlertTable, FilterChips, SummaryStats, Sparkline
│   │   ├── lane/                          LaneHeader, ChartTab, BacktestTab, StrategyTab,
│   │   │                                  SidePanel, DemandBreakdown, CounterfactualToggle,
│   │   │                                  DeltaCard
│   │   └── ui/                            primitives (Button, Chip, Table, Badge)
│   ├── lib/
│   │   ├── data.ts                        JSON loaders (server-side)
│   │   ├── types.ts                       TS types matching data contract
│   │   └── format.ts                      number / date formatters
│   ├── data/                              COMMITTED JSON artifacts
│   │   ├── alerts_today.json
│   │   ├── lanes_index.json
│   │   ├── backtest_summary.json
│   │   └── lane/
│   │       ├── T-32206-NJ.json
│   │       ├── T-32206-NJ_demand.json
│   │       ├── T-32206-NJ_counterfactual.json
│   │       └── ... (107 lanes × 3 files each = 321 files)
│   ├── public/                            static assets
│   ├── package.json
│   ├── tsconfig.json
│   ├── next.config.mjs                    output: 'export'
│   ├── tailwind.config.ts
│   └── README.md                          build + run instructions
├── pipeline/
│   └── (09 + 10 get a new final cell that dumps to ../ui/data/)
└── .gitignore   (add: ui/node_modules/, ui/.next/, ui/out/)
```

### Gitignore additions (root `.gitignore`)
```
# UI build output
ui/node_modules/
ui/.next/
ui/out/
```

`ui/data/` is deliberately committed. `ui/app/`, `ui/components/`, etc. all committed normally.

### Dev workflow
```
cd ui
npm install
npm run dev    # http://localhost:3000
```

### Build for demo
```
npm run build  # outputs ui/out/ — static HTML/CSS/JS
```

### Pipeline integration
- `pipeline/09_reorder_alerts.ipynb` final cell: writes `ui/data/alerts_today.json` and updates `ui/data/lanes_index.json` today-flag fields.
- `pipeline/10_backtest.ipynb` final cell: writes per-lane JSON, `_demand.json`, `_counterfactual.json` (for showcase lanes + computed for all), `backtest_summary.json`.
- Pipeline → UI is one-way. UI never writes back.

---

## 8. Out of scope (for the prototype)

Not building:
- Auth / login / users.
- Editing / writing back. Read-only.
- Saving filter sets / user preferences beyond URL params.
- Real-time updates (data is static-at-build).
- Server / API layer.
- **F2 — Demand Curves** tab content (route stub only).
- Customer-level lanes (customer is a breakdown inside a lane, not a lane dimension).
- Multi-DC allocation / transfers.
- Mobile-first responsive polish (desktop ≥1200px primary; narrow viewports get stacked fallback, not redesign).
- Error / empty / loading states beyond a single shared boundary.
- Accessibility audit (semantic HTML + focus styles; no WCAG claim).
- Tests. No unit / Playwright / visual regression.
- Analytics / telemetry.
- Printable / PDF export.
- Search / free-text query.
- Dark mode (light theme only).

Deferred, likely v2:
- Per-lane notes / comments (needs persistence).
- Client-side "what-if" strategy tester (slide run-rate live, re-simulate).
- Multi-select lane compare.
- Threshold-editing UI for confidence tiers.

---

## 9. Showcase lanes

The demo narrative polishes these three:
- **`T-32206-SF`** — the money slide. Tiger Balm Patch Warm, San Francisco DC. Actual trough: −330k. P90-followed trough: −212k. Primary counterfactual story.
- **`T-32206-NJ`** — same SKU, different DC. NJ is MM-heavy, SF is mixed. Shows multi-DC behavior.
- **`F-04111-NJ`** — POP Ginger Chews Original. Non-Tiger-Balm SKU, demonstrates the tool generalizes.

Showcase lanes get authored narrative taglines in their counterfactual JSON. All 107 lanes get computed counterfactual data and fallback numeric taglines.

---

## 10. Open questions resolved during brainstorm

| Question | Resolution |
|---|---|
| Customer dimension — lane grain or facet? | **Facet inside a lane.** Lanes stay at `(SKU × DC)`. Customer shown in demand breakdown + top-customers panel. |
| Which showcase lanes? | `T-32206-SF`, `T-32206-NJ`, `F-04111-NJ`. |
| Static export vs. Next.js server? | **Static export** (`output: 'export'`). |
| URL-as-state vs. persistent filters? | **URL-as-state.** Filters in query params, no persistence. |
| Default List filter — flagged only? | **Yes**, `status=flagged` default, one-click to expand. |
| Per-row sparkline in List? | **Yes**, 26-week inline SVG. |
| Charting library? | **Recharts** for all charts. |
| Side panel — fixed or collapsible? | **Fixed** width ~280px, always visible on desktop. |
| Demand breakdown — always visible or own tab? | **Always visible** as bottom region. |
| Counterfactual for all lanes or just showcase? | **Computed for all**; authored taglines for showcase only. |
| Delta readout card? | **Yes**, visible whenever overlay is active. |
| `ui/data/` committed or gitignored? | **Committed.** |
| Per-lane files vs. one big file? | **Per-lane**, enables lazy-loading and clean dynamic routes. |

---

## 11. Definition of done (for the implementation plan)

The prototype is done when:
1. `npm run build` in `ui/` succeeds, produces `ui/out/`.
2. `/alerts` lists all 233 rows from `alerts_today.json`, filters work, sparklines render.
3. Clicking a row navigates to `/alerts/lane/[slug]` and loads that lane's chart.
4. Lane view renders: main chart with `on_hand` + `reorder_point` + alert markers, tabs for Chart / Backtest / Strategy, side panel, demand breakdown.
5. Counterfactual toggle on showcase lanes shows authored banner taglines, delta readout card, simulated PO markers.
6. `/curves` renders a "coming soon" stub.
7. Pipeline notebooks 09 + 10 dump to `ui/data/` and the UI builds against those artifacts without touching raw `data/`.
8. A full demo walkthrough on `T-32206-SF` lands all three counterfactual states without console errors.

Not required for done:
- Test suite.
- Accessibility audit.
- Polished narrow-viewport layout.
- Any F2 content.
