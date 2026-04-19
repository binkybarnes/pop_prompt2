# UI vs. production-signal mismatch — to resolve

**Observation (2026-04-18):** The production alert model is *one signal, today* — `09_reorder_alerts.ipynb` runs `build_reorder_alerts()` once using all history up to the latest inventory snapshot, producing a single `alerts_today.json` with one row per (SKU × DC).

**But the UI (Phase A–F, on `origin/main`) ships more than that:**

1. **Alerts list view** (`ui/app/alerts/page.tsx` → `alerts_today.json`) — matches the production model. One row per lane, `reorder_flag`, `suggested_qty`, sparkline. ✓
2. **Backtest tab per lane** (`ui/components/lane/BacktestTab.tsx` → `lane/{SKU}-{DC}.json`) — shows 34 historical as-of weeks with `reorder_point_mean` / `reorder_point_p90` / `alert_fired_mean` / `alert_fired_p90` side by side. This is **backtest replay**, not today's signal.
3. **Strategy comparison** (`backtest_summary.json`) — compares `mean` vs `p90` run-rate strategies with precision/recall/TP/FP. This is a **forecaster selection** view.

**The mismatch:** the list view says "here's what to order today." The lane detail view says "here's how two different strategies would have performed historically." These are two different products stapled together — the user has to context-switch.

**Decisions needed before demo:**

- Does the lane detail view show *today's* ROP + SS trajectory, or the *backtest* ROP curve? Currently it's the backtest — useful for judging the policy but confusing as a planner tool.
- Does the strategy comparison (`mean` vs `p90`) belong in the operational UI at all, or is it a separate "model-tuning" view?
- If we promote 10c (trend-aware + hybrid 70%), should the UI show three strategies (mean / p90 / trend-hybrid) or just replace mean?
- The user's mental model is "one signal." The UI should match that by default, and bury the strategy comparison behind a "diagnostic" tab or separate page.

**Suggested resolution:** talk to the frontend friend. Options in rough order of effort:
1. **Rename the tab** — "Historical replay" instead of "Backtest," clarifies what the curves mean.
2. **Add a "today" line** — overlay the current `reorder_point` on the lane chart as a single horizontal line, so the reader sees both "where we are now" and "how we would have performed."
3. **Split views** — operational (alerts list + lane today) vs. diagnostic (backtest/strategy comparison). Different tabs at the shell level.

**Not a blocker for integration** — UI works with current `src/reorder.py`. Just flag for post-integration cleanup.
