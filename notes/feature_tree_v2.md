# Feature Spec v2 — Locked

This is the **spec** we're building. It supersedes `feature_tree.md` (kept as the original MoSCoW brainstorm).

Two headline features, sharing one clean-demand pipeline.

---

## F1 — Reorder Alert (operational)

**Who uses it:** the buyer, weekly. Today they eyeball 1,000 SKUs by memory. This tool hands them a short list.

**What it answers:** "which SKUs need a PO placed this week, and roughly how many cases?"

**Inputs (per SKU × DC):**
- clean transactions (tagged by the shared pipeline below)
- current available inventory (`on_hand − allocated`, with stale-hold aging as a stretch)
- lead time (from `POP_ItemSpecMaster.xlsx`; missing → supplier median → flat fallback 90d overseas / 45d domestic)
- elasticity slope (from F2, used for safety stock)

**Math:**

```
organic_run_rate   = mean(units_per_week) over rows where
                     NOT is_promo AND NOT is_markdown AND NOT is_stockout_week
safety_weeks       = base + k × |elasticity_slope|     # from F2; flat SKU → thin buffer, steep SKU → fat buffer
safety_stock       = safety_weeks × organic_run_rate
reorder_point      = organic_run_rate × lead_time_weeks + safety_stock
alert              = available < reorder_point
suggested_qty      = organic_run_rate × replenishment_cycle − available + safety_stock
```

**Plain-English behavior:**
- Take the weeks where nothing weird was happening (no TPR promo, no clearance markdown, no stockout).
- Average the units sold in those weeks — that's the honest weekly demand.
- Multiply by how long a PO takes to arrive. Add a buffer that's bigger for SKUs with choppy demand (from F2).
- If you have less than that in the warehouse, fire an alert.

**Low-data SKUs:** if fewer than N clean weeks exist, flag the SKU as "low-confidence — manual review" and skip the auto-alert. Don't fake a number.

**Output shape:** one row per alerted SKU × DC. Columns — SKU, DC, on_hand, available, organic_run_rate, lead_time, reorder_point, suggested_qty, confidence, *why* (plain-English reason string). Format decided later (webapp first, CSV/Excel trivial to add).

---

## F2 — Demand Curve Drill-Down (strategic)

**Who uses it:** the buyer when they need to *understand* a SKU — planning a promo response, negotiating with a retailer, investigating a declining item, or sanity-checking an F1 alert that feels wrong.

**What it answers:** "at what price does this SKU sell how much, per channel, and how has that changed over time?"

### The graph

User picks: **SKU + channel + time window** (e.g. "Tiger Balm Patch, American Mainstream Market, 2024 H2").

What they see:
- **Scatter plot**, one dot per transaction (or per customer-week roll-up for readability).
  - X axis = unit price
  - Y axis = units sold
- **Color coding of dots:**
  - Blue = clean (no promo, no markdown, inventory was healthy)
  - Orange = `is_promo` (TPR-driven, chargeback evidence)
  - Red = `is_markdown` (invoice price well below SKU median — clearance)
  - Greyed/excluded = `is_stockout_week` (inventory hit zero or shipped < typical — the dot would lie about demand)
- **Fitted curve line** through the full cloud (blue + orange + red — markdowns belong on the curve because they're real low-price demand points; only stockouts are excluded because they hide real demand).
- **Organic baseline marker** — a horizontal annotation at the list-price column showing "organic = ~400 cases/mo at $3.50". That number is what F1 uses.

### The trend stack

For one SKU × one channel, overlay several 2D curves, **one per 6-month window**:

```
2024 H1 curve  ─── at $3.50 → 420 cases/mo
2024 H2 curve  ─── at $3.50 → 400 cases/mo
2025 H1 curve  ─── at $3.50 → 370 cases/mo   ← organic decline
```

Six-month windows → ~6 curves across three years of data. Quarterly is too noisy; yearly gives too few. If a SKU doesn't have enough data in a window, that slice is omitted (not faked).

### The price predictor

A small input on the same page: the user types a price, the tool reads off the curve and returns predicted units at that price (plus a confidence band if the curve fit supports one). This is what powers "retailer asks for July TPR at $2.50, how many extra cases should we pre-build?".

### The five use cases this enables

1. **"Is this promo worth it?" — pre-promo inventory planning.**
   Retailer says "TPR at $2.50 in July." Today POP guesses how much extra to build. The curve answers: at $3.50 → 400 cases/mo (baseline); at $2.50 → predicts 850 cases/mo → pre-build an extra 450 cases → lead-time back from July = place the PO in April. This is probably the single biggest actual-dollars use case.

2. **Safety stock tiering (feeds F1).**
   The *slope* of the curve tells you if a SKU is elastic or inelastic.
   - Flat curve (Tiger Balm Medicated Plaster — volume barely moves with price) → inelastic → 1-week buffer is plenty.
   - Steep curve (POP Ginger Chews — volume swings with every promo or competitor move) → elastic → 3-week buffer.
   Today POP uses one safety-stock rule for all ~800 SKUs. The curve gives a per-SKU rule.

3. **Organic trend detection — "is this SKU fading?"**
   Year over year, if the $3.50 point on the curve drifts from 420 → 370 cases/mo, that's a *real* demand decline, not pricing noise. Today that signal is buried because raw YoY numbers mix in promo variation. Buyers want to catch fading SKUs early — the trend stack isolates it.

4. **Channel-specific pricing insight.**
   POP's American channel is promo-heavy; Asian Ethnic Market barely runs promos; Health Food is distributor-mediated and noisy. Same SKU plotted per channel → three different curves. Tells the sales team "don't try to run a TPR in Asian Market, the curve there is flat, you'll just give away margin." Reflex from sales people is to assume a promo lift will work everywhere — the curve shows which channels it actually will.

5. **Counter-offer ammo for chargeback / TPR negotiations.**
   Retailer demands a bigger TPR. Buyer pulls up the curve: "last time we cut to $2.50, the lift was 200 units, not the 450 they're projecting. The deal doesn't pay back its discount." POP today has no data to push back with — they just accept or eat it.

**Low-data SKUs:** if the scatter is too thin to fit a curve, show the dots only, no line. Label the panel "insufficient data for fit."

---

## Shared pipeline (how we get "clean demand")

Both features sit on top of the same pipeline. Build once, both consume.

```
raw sales + chargebacks + inventory snapshot + POs
    │
    ├── brand extraction (prefix map + keyword fallback — see exploration_f1.ipynb cells 13-18)
    │
    ├── promo calendar: tpr chargebacks → (Customer × Brand × YearMonth)
    │   └── lag-imputation for missing promo dates (median doc_date − promo_start)
    │
    ├── historical inventory reconstruction
    │   └── start from today's snapshot, rewind via (−POs received, +shipments)
    │       anchored on PO receipt dates; noisy but documented
    │
    ├── tag each transaction row
    │   ├── is_promo       ← customer+brand+month matches promo_cal
    │   ├── is_markdown    ← unit_price < threshold × SKU median
    │   └── is_stockout_wk ← inventory=0 that week OR shipped < customer's typical weekly order
    │
    ├── channel mapping: Salesperson ID → {MM, AM, HF}
    │   └── SLPRSNID_SALESCHANNEL_KEY.xlsx (deterministic; replaces unreliable Customer Type field)
    │
    └── clean_transactions (fully tagged, channel-assigned)
            │
            ├──→ aggregate over clean rows → organic_run_rate per SKU × channel × DC → F1
            └──→ scatter + tags → per-window curves per SKU × channel → F2
```

---

## Decisions locked

| # | Question | Decision |
|---|---|---|
| 1 | How do we detect stockouts? | `inventory hit zero that week` OR `shipped < customer's typical weekly order`. Chargeback short-ship codes ruled out (unreliable). |
| 2 | Where does lead time come from? | `POP_ItemSpecMaster.xlsx`; missing → supplier median; else flat fallback 90d overseas / 45d domestic. |
| 3 | How do we get historical inventory? | Reconstruct: today's `POP_InventorySnapshot.xlsx` + rewind via transactions + POs. Anchor on PO receipt dates. Accepted noise, documented as an assumption. |
| 4 | Safety stock rule? | `safety_weeks = base + k × \|elasticity_slope\|` — per-SKU, driven by F2 curve. This is the tool's differentiator over one-size-fits-all rules. |
| 5 | Curve fit method? | Try log-log regression, isotonic, and bucketed mean. Pick per-SKU by best fit on holdout. Decide later during build. |
| 6 | Low-data SKUs? | Mark as "insufficient data," don't fake a number. No auto-alert, no fitted curve — scatter only. |
| 7 | Trend-stack window width? | 6-month windows (H1 / H2) → ~6 curves across 3 years. Quarterly too noisy; yearly too few. |
| 8 | Pre-promo planning UX? | User sets SKU + channel + window → curve plot. Separate price input → tool returns predicted quantity off the fitted curve. |
| 9 | Output format? | Webapp first. CSV/Excel export trivial to add later — not an MVP concern. |
| 10 | Showcase SKUs? | Decide at demo time. Working list: `T-32206` (Tiger Balm Patch Warm), `F-04111` (POP Ginger Chews Original), `T-22010`, `T-31510`. |

---

## Non-blocking notes (conscious scope cuts)

- **No forecasting.** Organic run rate = trailing-window average. We don't fit ARIMA/Prophet. Easier to explain, harder to game, and the data density per SKU won't support fancy forecasting anyway. Note this out loud in the demo.
- **No auto-promo-price recommender.** The curve *shows* elasticity; it doesn't *suggest* a better TPR price. A v2 feature.
- **No multi-DC allocation.** Reorder alerts are per DC. Transfers between SF / NJ / LA are out of scope.
- **No OTIF / chargeback reconciliation.** That's Problem 3, separate effort.
- **No live ERP integration.** POP has no API. CSV/XLSX in, webapp out.

---

## Build order (revised 48 hr)

| Hour | Work | Notes |
|---|---|---|
| 0–6 | Ingest (shared pipeline, data load + joins) | Nothing else works without this |
| 6–14 | Tagging: is_promo (done), is_markdown (done), is_stockout (new) | Stockout needs historical inventory rewind |
| 14–20 | Channel mapping + clean_transactions aggregation | Drops in once tagging is done |
| 20–28 | F1 reorder math + output | Uses a flat safety stock initially; plug in elasticity once F2 exists |
| 28–38 | F2 curves + scatter + trend stack + price predictor | The heavy lift; also the money slide |
| 38–42 | Loop elasticity back into F1 safety stock | Makes F1 sharper and justifies "per-SKU" claim |
| 42–46 | Showcase SKU polish, before/after comparison | Demo-critical |
| 46–48 | Slide deck, kill broken stuff, rehearse | |

**Kill rule:** if the shared pipeline + F1 aren't solid by hour 28, CUT F2 features (trend stack, price predictor) and ship F2 as a static scatter for 2 showcase SKUs. A working F1 + one good curve beats an ambitious half-broken surface.
