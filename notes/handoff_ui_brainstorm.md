# Handoff — Reorder Alert UI brainstorm (mid-session)

Picking up mid-brainstorm on a different machine. A separate Claude is working on the pipeline (step 05 promotion / tweaks — see `notes/status.md`).

**Resume skill:** `superpowers:brainstorming`. When you continue, invoke it and tell it you're resuming from this handoff at **step 5** (approach D picked, now present design sections).

## IMPORTANT — what changed since the first draft of this handoff

F1 has evolved beyond "a list of today's reorder alerts." Pipeline step 10 (`pipeline/10_backtest.ipynb`) is now committed. F1 is a **time-series-per-lane** system with three layers:

1. **Operational** — per (SKU, DC, week): `reorder_point`, `run_rate_wk`, `on_hand_est`, `reorder_flag`, `suggested_qty`, `confidence`, `lead_time_wk`. What a buyer acts on today.
2. **Historical walk-forward** — same columns repeated for every historical `as_of_week`, plus ground-truth columns (`fresh_stockout`, `weeks_until_stockout`, `inv_at_asof`). Did our alerts precede real dips? (Mean: recall 0.33, median warning 10 wk. P90: recall 0.5, same 10 wk.)
3. **Strategy variants + counterfactual** — mean vs p90 run-rate, plus "if POP had followed our alerts, here's the simulated inventory trajectory." E.g. `T-32206 SF` min goes from -330k (actual) → -212k (p90-followed). This is the money slide.

Artifacts produced by step 10:
- `pipeline/artifacts/backtest_alerts.parquet` (7084 × 31)
- `pipeline/artifacts/backtest_per_lane.parquet` (107 × 13)
- `pipeline/artifacts/backtest_compare.parquet` (2 × 15) — mean vs p90 scoring
- `pipeline/artifacts/backtest_summary.parquet` (1 row)
- `pipeline/artifacts/figures/backtest_*.png` (4 static plots for reference)

Because F1 is now time-series, the earlier A/B/C approaches (all framed around a static reorder-alert table) are **stale**. They were replaced by D/E/F (below).

## Where we are in the brainstorming checklist

| Step | Status |
|------|--------|
| 1. Explore project context | done |
| 2. Offer visual companion | accepted on prior machine; server dead, restart only if a question benefits from visuals |
| 3. Ask clarifying questions | done — Q1–Q4 answered, plus new Q5 (approach) |
| 4. Propose 2–3 approaches | done — revised set D/E/F presented |
| 5. Present design sections, get approval | **next — D picked, prototype scope** |
| 6. Write design doc to `docs/superpowers/specs/2026-04-18-reorder-alert-ui-design.md` | pending |
| 7. Spec self-review | pending |
| 8. User reviews written spec | pending |
| 9. Invoke `superpowers:writing-plans` | pending |

## Decisions locked

| Q | Decision |
|---|---|
| Audience / phasing | **C — phased.** Utility first, then polish + before/after story on 2–3 showcase SKUs. |
| Tech stack | **B — Next.js + React.** Bake backtest + current-alert artifacts → JSON as an extra step at the end of pipeline notebooks (09 for current, 10 for backtest). UI is static-ish, reads JSON, no xlsx parsing in-browser. |
| Visual reference | **Linear** for the operational list (filter chips visible above the table, no hidden-filter drawer). **TradingView** for the per-lane drilldown (chart-first, time scrub, overlays, alert markers, strategy tester panel). |
| Shell scope | **B — two-tab shell** ("Reorder Alerts" \| "Demand Curves"). Only tab 1 built. F2 is in conflict on the data side right now, so leave room, don't build. |
| Approach (NEW) | **D — Hybrid.** Home view is the Linear-style operational list (today's alerts, filter chips, sortable table). Click a row → full-route "Lane view" that looks like TradingView: on_hand line over time, reorder_point dashed overlay, alert markers on the timeline, mean/p90 toggle, counterfactual overlay, tabs for chart / backtest performance / strategy. |
| Scope (NEW) | **Prototype**, not production. Minimal auth/error/empty states. Focus on the demo narrative. 2–3 showcase lanes get the full story; rest of the ~107 lanes use the same views with less polish. |

## Approaches that were presented at step 4 (for reference — D won)

- **D. Hybrid *(chosen)*.** Operational list home + TradingView-style Lane view drilldown. Buyer gets utility; demo gets the chart-first narrative. Money slide (counterfactual) lives in the Lane view on a tab or overlay.
- **E. Full trading-tool.** Chart-first everywhere, no separate operational list. Lanes in a left sidebar with sparklines. Looks incredible but loses the "this week's action list" view buyers actually want.
- **F. Lightweight.** Keep a simple alerts table, add a small chart modal per row. Fastest to build but throws away the counterfactual story, which is the strongest demo asset.

## Open questions (resuming agent: ask these during step 5 or fold into the design)

1. **Customer dimension.** User said "per dc, sku, customer (maybe)". The backtest is currently per (SKU, DC) only (107 lanes). If we want customer-level lanes, upstream pipeline + backtest need a customer dim added, which is out of scope for a prototype. **Default assumption: customer is a filter/facet, not a lane dimension.** Confirm before locking.
2. **Which 2–3 showcase lanes?** `T-32206 SF` is explicitly the demo money-slide in the backtest notebook (counterfactual chart saved). Candidates from `per_lane` high fresh_rate: `T-32202 SF`, `A-61117 NJ`, `T-32206 SF`, `D-15206 LA`. CLAUDE.md's existing candidates: `T-32206` (Tiger Balm Patch Warm), `F-04111` (POP Ginger Chews Original), `T-22010`, `T-31510`.
3. **Gitignore subfolder** — still pending answer. Plan: put UI at `ui/`, add `ui/node_modules/`, `ui/.next/`, `ui/out/` to root `.gitignore`, plus `.superpowers/`.

## Shape of the design sections to present next (suggested order)

1. **Top-level architecture** — two-tab shell, Alerts tab has two sub-routes (`/` = list, `/lane/[sku]-[dc]` = lane view). JSON-on-disk data model. No server.
2. **Data contract** — what JSON files notebook 09 and notebook 10 produce. Probably `alerts_today.json` (rows from step 09), `backtest_alerts.json` (rows from step 10), `backtest_per_lane.json`, `backtest_compare.json`. Maybe `counterfactual_{sku}_{dc}.json` per showcase lane.
3. **List view (home)** — filter chips (DC / confidence / alert-status), sortable columns, row click → lane route. Linear-style.
4. **Lane view** — layout: header (SKU, DC, confidence, today's recommendation) / main chart (on_hand + reorder_point + alert markers, time-scrub) / side panel (alert reasoning, case pack, lead time). Tabs: Chart / Backtest / Strategy.
5. **Counterfactual overlay** — how the "if POP had followed our alerts" line is layered onto the Lane chart (toggle button; show mean / p90 / actual as three lines).
6. **File layout** — `ui/` Next.js project, `ui/app/` routes, `ui/data/` JSON inputs copied from `pipeline/artifacts/` at build time.
7. **Out of scope for prototype** — auth, multi-user, real-time updates, editing, saving filter sets, F2 (demand curves) tab content.

Walk the user through these sections one by one, get approval at each, then write the spec.

## Project context the resuming agent needs

- Source of truth for the feature: `notes/feature_tree_v2.md` (F1 spec, decisions locked, build order).
- F1 output shape is defined in `feature_tree_v2.md` around line 41.
- Pipeline step 09 (`pipeline/09_reorder_alerts.ipynb`) produces today's alerts. Step 10 (`pipeline/10_backtest.ipynb`) produces the walk-forward + counterfactual. Both already exist on main; step 10 was the most recent commit (`95d5b00`).
- The UI will live in a **separate Next.js project at `ui/`** under repo root.
- The implementing Claude will work in a **separate session** and only needs the JSON contract — it does NOT need pipeline context.
- Project conventions: Python env is `mamba run -n 3.11mamba …`. Data gitignored. Notebooks edited with `NotebookEdit`.

## Companion server

- URL on prior machines: dead after machine switches.
- Screen dir was: `.superpowers/brainstorm/14675-1776534000/content`
- To resume visuals: restart with `scripts/start-server.sh --project-dir /path/to/pop_prompt2` from the brainstorming skill scripts dir.
- No visual mockups were written — only terminal conversation so far. For the Lane view, a mockup would probably help before writing the spec.
