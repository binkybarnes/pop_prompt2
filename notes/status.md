# Project status

Rolling log of what's in progress, blocked, and next. Keep it short — update after finishing a pipeline step or hitting a blocker. This replaces the need to "catch up" a new chat.

## In progress

- **Pipeline step 10 (F1 backtest)** — scaffolded at `pipeline/10_backtest.ipynb`. Walk-forward harness: for each `as_of_week` re-runs `build_reorder_alerts` on truncated history + synthetic snapshot from `inv_weekly`, then attaches forward-window ground truth (`forward_stockout`, `min_forward_on_hand`, `weeks_until_stockout`). Produces confusion matrix + lead-of-warning histogram + T-32206 SF timeline + per-lane summary. **Run preconditions**: this fresh pull is missing several artifacts (pipeline/artifacts/ is gitignored) — re-run notebooks 01→09 before 10 so `clean_demand_weekly.parquet`, `inv_weekly.parquet`, `item_master.parquet`, `reorder_alerts.parquet` exist. Test window: 2023-04-03 → 2025-10-13, 4-week step (~131 as-of weeks). After validation, promote helpers to `src/backtest.py` with `run_backtest(...)` entry point.
  - **Lead-time fallback chain** added to `src/reorder.py` (2026-04-18): `compute_lead_time_from_po` now returns `(per_dc, per_sku)`; precedence is `po_history` (≥3 PO receipts on this SKU×DC) → `po_pooled` (≥2 receipts across DCs for this SKU) → `parsed` → `default`. Motivation: backtest early iterations (2023-Q2) had 0 SF POs for T-32206, so lead fell back to parsed "Half a year or more" = 26 wk — 9× longer than actual ~3 wk. Fix moved 1,090 backtest lanes from parsed/default into `po_pooled`.
  - **Total-demand run rate** (2026-04-18): switched both `09_reorder_alerts.ipynb` and `10_backtest.ipynb` to feed `build_reorder_alerts` a `total_weekly` panel (raw sales grouped by SKU×DC×week) instead of `clean_demand_weekly`. Rationale: the warehouse drains at total outflow, so reorder math must size against total. Clean demand stays the input for forecasting / elasticity (separate concerns). Counterfactual sim impact on T-32206 SF: p90 variant now recall_fresh **100%** (was 83%), sim_p90 min on_hand **-20k** and final **+32k** (was -38k/-38k); mean variant recall **83%** (was 50%).
  - **Defaults bumped Z=1.65→2.33, forward_cover=4→6** (2026-04-18). Motivation: backtest trace showed dips happen during demand bursts (20k vs p90 of 15k) that outrun safety stock sized at 95%, and the 4-wk forward cover leaves too-short cycles. 99% service + 6-wk post-arrival cover prioritize "never run out" over "never hold extra" — POP already holds ~250k on T-32206 SF so the cash trade is ours to spend. T-32206 SF sim result: p90 min −20k→**−15k**, final +32k→**+30k**, orders 16→**12** (bigger & less frequent). Mean variant flipped ending from −34k → **+23k**, recall 83% → **100%**. Production alerts (step 09) now 202/233 flagged (was 199) — modest increase because reorder_point is higher.

## Next

- **Pick next backend feature** to build in parallel with the UI layer being built in a separate Claude session on top of `reorder_alerts.csv`. Candidates: stockout lost-demand dollars, YoY per SKU × channel, channel-mix-shift alert, vendor lead-time variance from PO history.
- **Open question for the president**: on-invoice vs off-invoice TPRs. Post-filter, `MBE591A` shows an 8% invoice discount during real TPR months but `MRE800A` and `MWA662A` show 0% — suggesting some customers invoice at list and take the TPR as a later rebate (chargeback settles the discount out-of-band). This means `Unit_Price_adj` is NOT a reliable signal for detecting promo windows for those customers, and elasticity fits at the customer-channel level may permanently underestimate promo-price response. Confirm with POP before investing in more elasticity work.
- **Revisit elasticity model (after step 09)** — v1 is log-log only (constant-elasticity assumption). If showcase scatters show kinked demand curves (flat above some price, steep below), add isotonic regression as a per-SKU fallback. See feature_tree_v2 decision #5.
- **Revisit feature scope (F1/F2) after pipeline** — stockout-caused demand loss is <0.2% of rows even at `LOST_DEMAND_COVER_K=10` (K=1 -> 55 rows, K=10 -> 440). That's a real finding: POP's demand is mostly promo/markdown-polluted (14.7%), not stockout-polluted. The F1 forecaster's main cleaning job is promos, not stockout imputation. Worth discussing whether that shifts F1/F2 framing after all steps are wired.

## Blocked

- (nothing blocking right now)

## Decisions needed

- (none open — the 10 open questions are all resolved in `feature_tree_v2.md`'s "Decisions locked" table)

## Recently completed

- **Pipeline step 09 (reorder alerts / F1)** — verified end-to-end. Per (SKU × DC) reorder table using classic `run_rate × lead + Z·σ·√lead` math (Z=1.65, 95% service), 4-week forward-cover order-up-to, case-pack rounding via `math.ceil`.
  - `reorder_alerts.parquet` / `.csv` **233 × 25** (~57 SKUs × 3 DCs, after left-merge on inv snapshot). 165 flagged.
  - Confidence: **109 high / 28 medium / 96 low**. Low mostly = SKUs in clean demand but missing from item_master (no lead time / case pack).
  - Lead-time parsing: 51/65 item_master rows parsed. Rules: ranges → upper bound, bare numbers → months (ocean freight from China/Singapore), "Half a year or more" → 26 wk. 14 nulls fall back to `DEFAULT_LEAD_WEEKS=13`.
  - T-32206 spot check: NJ (17.7k/wk, 18 wk cover → flag, suggest 272k u / 7,571 cases of 36); LA (5.0k/wk, 27 wk cover → flag, suggest 38k u / 1,056 cases); SF (5.1k/wk, 49 wk cover → no flag — the post-2023-dip over-correction we saw in step 04). Matches hand calc.
  - **CV-based safety stock**, not elasticity-based, because the off-invoice TPR finding (below) means β under-estimates real promo responsiveness for MRE800A / MWA662A-type customers. Using weekly std directly avoids compounding that bias.
  - `src/reorder.py` public API: `build_reorder_alerts(weekly, inv, im, **tunables) -> DataFrame`, plus `compute_dc_stats`, `prepare_item_master`, `parse_lead_time_weeks`, `parse_case_pack`. Notebook re-executed after promote; outputs byte-identical.
- **Promo-calendar TPR filter (step 03 bugfix)** — `src/promo_cal.py` now calls `filter_true_tpr()` before building the calendar. The chargeback file mixes real CRED03 scan-downs with CRED02 publication / shelf-talker / trade-show / admin fees that don't change invoice price; previously every chargeback tagged a customer-brand-month as promo, so `is_promo` was firing on marketing-invoice months. New `classify_chargeback(desc, cause_code)` returns `tpr | fee | other` using PRICE_KW (scan / billback / TPR / `$N x M@` / % off / rebate / in-ad) and FEE_ONLY_KW (publication fee / shelf talker / catalog / trade show / front end kit / distributor charges / etc); CRED03 is kept unconditionally.
  - Filter impact: 6,868 chargebacks → **5,004 real TPRs** (73%). 1,309 dropped as fee, 555 as other (no price-cut signal).
  - `promo_cal.parquet`: **1,391 → 1,134 tuples** (71 customers → 63 — some customers had only fee-type chargebacks).
  - Downstream re-run (05 → 06 → 07 → 08): `is_promo` share **55% → 10.2%**; `is_clean_demand` share **~45% → 77.2%**; elasticity fits unchanged (slopes don't depend on `is_promo`).
  - Spot check on MBE591A × T-32206 timeline: previously showed 25 "promo" months with no invoice-price change; now shows 9 real TPR months with an 8% invoice discount during those weeks. MRE800A/MWA662A still show 0% invoice discount during their (real) TPR windows — evidence that those customers use off-invoice TPR (chargeback-based rebate, not on-invoice price cut). Logged as open question for the president.
  - Notebook 03 updated to report filter stats by cause code × kind. No API break — `build_promo_calendar(tpr)` still returns `(promo_cal_df, median_lag_days)` but now filters internally.
- `src/elasticity.py` — promoted elasticity-fit logic from `08_elasticity_curves.ipynb`. Public API: `fit_elasticity(sales, *, min_obs=20, min_log_price_iqr=0.1) -> DataFrame` plus `filter_eligible(sales)`. Notebook re-executed end-to-end after refactor; outputs identical (207 × 11, 135 fitted, T-32206 MM slope −5.07).
- **Pipeline step 08 (elasticity curves)** — verified end-to-end. Log-log `log(qty) = α + β·log(price)` fit per (SKU × channel) over non-stockout rows with `Unit_Price_adj > 0 & QTY_BASE > 0`.
  - Output: `elasticity.parquet` **207 × 11**. Columns: ITEMNMBR, SALESCHANNEL, n_obs, log_price_iqr, median_price, slope, intercept, r_squared, is_low_data, method, predicted_qty_at_median.
  - **135 fitted / 72 low-data** (35% gated by either `n_obs < 20` or `log_price_iqr < 0.1` — the latter fires when a channel sells a SKU at near-constant price, e.g. F-04111 AM where price barely varies).
  - **124 / 135 negative slopes** — expected direction for normal goods.
  - **Slope-by-channel** (median): AM −3.96 (most elastic) · MM −3.33 · HF −1.31 (most inelastic). Matches feature_tree_v2 intuition that HF is distributor-mediated and less price-responsive.
  - **Showcase SKUs**: T-32206 MM β=-5.07 R²=0.37 n=17,771; F-04111 MM β=-4.26 R²=0.40 n=5,078; T-31510 MM β=-5.99 R²=0.34 n=17,833; T-22010 MM β=-4.80 R²=0.38 n=12,822.
  - **Figure**: 4×3 showcase scatter grid (blue=clean / orange=promo / red=markdown / grey=stockout) with fitted curves saved to `pipeline/artifacts/figures/elasticity_showcase.png`.
  - **Scope cut**: v1 is log-log only. Isotonic + bucketed-mean methods from feature_tree_v2 decision #5 deferred until we see whether showcase scatters show kinked curves that log-log under-fits.
- `src/demand.py` — promoted clean-demand aggregation from `07_clean_demand.ipynb`. Public API: `build_clean_demand(sales, *, low_data_weeks=8) -> (weekly, summary, meta)` plus `aggregate_weekly`, `compute_organic_run_rate`. Notebook re-executed end-to-end after refactor; outputs identical (weekly 35,103 × 8, summary 568 × 11, 70 low-data cells).
- **Pipeline step 07 (clean demand)** — verified end-to-end. Filters `is_clean_demand == True & SALESCHANNEL notna & DC notna`, aggregates to weekly + summary.
  - `clean_demand_weekly.parquet` **35,103 × 8** — per (SKU × channel × DC × week_start). Columns: qty_base, revenue, n_txn, unit_price_wt (QTY_BASE-weighted mean unit price). Feeds F2 scatter/trend-stack.
  - `organic_run_rate.parquet` **568 × 11** — per (SKU × channel × DC). Columns: n_clean_weeks, mean_weekly_qty, std_weekly_qty, total_qty, cv_weekly, first_week, last_week, is_low_data. Feeds F1 reorder math.
  - **Null-DC filter**: dropped 1,762 rows / 482,213 base units (Shopify E1 / Weee W / Returns ZD / U / L) — documented in notebook cell 3. None belong in per-DC reorder math.
  - **Unit conservation**: clean_dc_qty == weekly_qty == summary.total_qty (35,040,918). Assertions pass.
  - **Low-data cells**: 70 / 568 (12.3%) at threshold `LOW_DATA_WEEKS=8`. Median n_clean_weeks = 101, mean = 75.2.
  - **T-32206 spot check** (Tiger Balm Patch Warm): MM-NJ 15,348/wk (157 weeks), MM-LA 4,421 (157), MM-SF 4,153 (153); HF-NJ 952 (128), HF-LA 917 (32, `cv=0.80`), HF-SF 667 (101); AM lanes 95–278/wk. Channel mix matches expectation (Tiger Balm MM-dominant).
  - **Channel coverage**: AM 206 / MM 195 / HF 97 non-low-data cells.
- **Markdown detector recalibrated (step 05 + step 06 re-verified)** — switched from pooled SKU median @ factor 0.70 to per-(SKU × channel) median @ factor 0.85 with pooled-median fallback when a (SKU, channel) cell has < 5 non-promo positive-price rows. Motivation: pooled median was dragged down by HF shelf premiums (HF median ratio 0.864) which under-flagged MM markdowns and over-flagged HF. Factor bumped 0.70 → 0.85 calibrated from demand-response curve (qty_ratio jumps 1.2× → 2.6× between 10–20% below median, per SKU with MAD ~$0.24 on $3.36 median).
  - Row-level only — empirically confirmed no post-markdown demand trough (offsets +1..+6 identical to −3..−1 in zero-qty rate and mean_ratio), so no propagation needed.
  - New flagged totals: `is_markdown` **5,491 → 31,486 (2.3% → 13.3%)**; `is_clean_demand` **85.5% → 75.1%**.
  - Per-channel markdown share: AM 13.9% / MM 13.3% / HF 9.4%. Clean-demand share: AM **85.9%** / MM **67.5%** / HF **56.2%**.
  - `src/tagging.py` API: `tag_markdown(sales, factor, channel_col='SALESCHANNEL', min_n=5)`; `tag_transactions(..., markdown_factor=0.85, markdown_channel_col='SALESCHANNEL', markdown_min_n=5)`. Adds `markdown_denom` column (per-channel median, pooled fallback).
  - Step 05 notebook now calls `attach_channel()` upstream before tagging; step 06 cell made idempotent (detects existing `SALESCHANNEL` and skips merge). `sales_tagged.parquet` now 236,818 × 44; `sales_tagged_channel.parquet` still 236,818 × 44 (same schema after step 06 no-op).
  - Side-experiment notebook: `pipeline/05b_markdown_channel_exp.ipynb` (diagnosis + calibration, keep for reference).
- `src/channel.py` — promoted channel-attachment logic from `06_channel.ipynb`. Public API: `attach_channel(sales, slprsn_key) -> sales_with_channel` (thin wrapper around the left-merge on SLPRSNID). Notebook re-executed end-to-end after refactor; outputs identical (236,818 × 43, 4 null SALESCHANNEL rows matching 4 null SLPRSNID).
- **Pipeline step 06 (channel mapping)** — verified end-to-end. All 236,818 rows preserved, 2 columns added (`SALESCHANNEL`, `SALESCHANNEL_DESC`). 100% coverage minus 4 rows with null SLPRSNID.
  - Channel mix: **MM** (American Mainstream) 113,226 / **AM** (Asian Ethnic) 107,399 / **HF** (Health Food) 16,189.
  - Channel × DC: MM concentrated in NJ (63,768), AM spreads across all three, HF heavily NJ (9,795).
  - Channel × brand sanity check (expected): Tiger Balm is MM-dominant (61,803 vs AM 6,484); am gsg and Ferrero are AM-dominant; kjeldsens/kwan loong/totole are AM-only. POP Tea and ginger chew span channels.
  - **Clean-demand share by channel**: AM 97.2% / MM 78.2% / HF 57.2%. HF is the most polluted channel — worth flagging when segmenting the F1 forecaster (may want per-channel markdown/promo thresholds).
  - Artifact: `sales_tagged_channel.parquet` (236,818 × 43).
- `src/tagging.py` — promoted tagging logic from `05_tag_transactions.ipynb`. Public API: `tag_transactions(sales, promo_cal, inv_weekly, *, markdown_factor, lost_demand_cover_k, lost_demand_order_f, lost_demand_min_n) -> (sales_tagged, meta)`. Helpers: `tag_promo`, `tag_markdown`, `tag_stockout_week`, `tag_lost_demand_week`. Notebook re-executed end-to-end after refactor; outputs identical (440 TRUE at K=10, is_clean_demand 85.4%, shape 236,818 × 41).
- **Pipeline step 05 (tag transactions)** — verified end-to-end. All 236,818 sales rows preserved, 5 flags added (`is_promo`, `is_markdown`, `is_stockout_week`, `is_lost_demand_week`, `is_clean_demand`).
  - `is_promo` = exact (CUSTNMBR, brand, sale_ym) match against `promo_cal`. **12.4%** of rows (29,421). Brand mix: tiger balm 22k / ginger chew 7.3k / am gsg 86. Sell-in-window refinement deferred.
  - `is_markdown` = `Unit_Price_adj < 0.70 × SKU median` (median computed on non-promo positive-price rows to avoid self-anchoring low). **2.3%** (5,491). Median markdown depth 35% off.
  - `is_stockout_week` = `on_hand_est ≤ 0` at sales week_start AND inv `confidence == 'high'`. **0.04%** (98 rows — all T-32206 SF, which dips to -17k within its 26k tolerance). Nullable boolean: NA for 30,563 rows without inv coverage.
  - `is_lost_demand_week` = `low_stock_week` AND `cust_below_normal`, where `low_stock_week = week_on_hand < 1.0 × typical_weekly_base` (and `confidence='high'`) and `cust_below_normal = QTY_BASE < 0.70 × cust_median` (per-customer-SKU median from ≥3 orders). **0.02%** (55 rows). NA = 38,817 rows (no inv or no customer baseline).
    - LD.1 magnitude: 52 / 55 are T-32206 in SF (the known-dip SKU); rest are 2 ferrero + 1 am gsg.
    - LD.2 timing: flagged rows cluster tightly in 4 consecutive weeks (2023-05-29 → 2023-06-19) when SF on_hand went -1.5k → -17.5k. No flags fire when on_hand is positive.
    - LD.3 DC substitution: **61%** of flagged (cust, sku, week) events had another DC ship the SAME customer's SKU above-median the same week → strong evidence POP rerouted from NJ/LA when SF was out.
    - LD.4 backfill: flagged rows show 17% next-order-above-normal vs 29% baseline for `cust_below_normal` without an inv dip. Lower backfill rate is explained by the 61% same-week DC substitution — customer already got product, no catch-up needed.
    - LD.5 spot check (T-32206 SF deepest dip week 2023-06-19 ±4w): flagged=16,12,11,13 on weeks with negative on_hand; flagged=0 on weeks before/after when on_hand is positive despite 6–22 cust-below-normal rows. Detector correctly gates on inventory.
  - `is_clean_demand` = none of `is_promo / is_markdown / is_stockout_week / is_lost_demand_week` fire. **85.5%** (202,473 rows — the F1 forecaster's input).
  - Markdown threshold (0.70) + rev-lookup on SKU median shown with histogram validation.
  - Artifact: `sales_tagged.parquet` (236,818 × 41) — adds `QTY_BASE`, `typical_weekly_base`, `low_stock_week`, `cust_median_qty`, `cust_below_normal`, `is_lost_demand_week`.
  - **Known tradeoff:** detector is very conservative (low recall, high precision). At `K=1` → 55 rows; `K=10` → 440 rows (still 0.19%). Ceiling won't cross ~1% — the real finding is that POP's stockout footprint is genuinely tiny.
  - Current notebook ships at `K=10` — broader window (4 → 11 flagged weeks for T-32206 SF) and LD.3 substitution rate climbs to 71.4%.
- **Pipeline step 04 (inventory rewind)** — verified end-to-end. Anchor `2026-04-13`, rewind start `2023-01-02`, 173 weekly snapshots × 219 (SKU × DC) = 37,887 rows.
  - Identity check PASS (`max |today_rewind − snapshot| = 0.000`).
  - UOM fix: `sales.QTY_BASE = QUANTITY_adj × QTYBSUOM` row-level; `transfers.QTY_BASE = TRX QTY × pack` via per-(SKU, UOM) median QTYBSUOM learned from sales (fallback: per-SKU median, then 1.0). POs verified in base units (T-32206 lifetime PO/sales ratio 0.92).
  - Confidence breakdown: **191 high / 28 low** (12.8% low-confidence, down from pre-UOM-fix where T-32206 alone was dipping to -3M base units).
  - T-32206 spot check all-high: SF min=-17,450 / NJ min=+117,196 / LA min=+90,529 against today = 264k/365k/144k.
  - Artifacts: `inv_weekly.parquet` (37,887 × 5), `inv_rewind_meta.parquet` (anchor/start/tolerance).
  - **Known small gap:** 865 nulls in `on_hand_est` (2.3%) — not investigated yet, low priority.
- `src/inventory.py` — promoted rewind logic from `04_inventory_rewind.ipynb`. Public API: `build_inv_weekly(sales, po, transfers, inv_snap, dc_map, tolerance_floor=50, tolerance_pct=0.10) -> (inv_weekly, meta)`. Helpers: `learn_uom_pack`, `normalize_sales_to_base`, `normalize_transfers_to_base`, `weekly_sum`. Notebook re-executed end-to-end after refactor; outputs identical (191 high / 28 low, identity check PASS, T-32206 SF min=-17,450).
- `src/promo_cal.py` — promoted promo-calendar logic from `03_promo_calendar.ipynb`. Public API: `extract_promo_ym`, `fit_median_lag`, `impute_promo_ym`, `build_promo_calendar(tpr) -> (promo_cal, median_lag_days)`. Notebook re-executed end-to-end after the refactor; artifacts unchanged: `promo_cal.parquet` (1,391 × 3, 71 customers × 9 brands × 47 months), `promo_lag_meta.parquet` (median_lag_days = 128.0), regex coverage 98.1% → 100.0% with fallback.
- `src/brand.py` — promoted brand tagging from `02_brand.ipynb`. Exposes `tag_brands(sales, tpr)` which returns `{'sales', 'tpr', 'sku_brand'}`, plus lower-level helpers (`derive_prefix_map_auto`, `make_extract_brand_v2`, `apply_sku_prefix_override`, `fill_brand_from_sku_majority`). Verified: sales 100.0%, tpr 87.6% (remaining 12.4% are admin-only TPR rows with no brand — MIS/LOA/LOC/RETAILER).
- `pipeline/02_brand.ipynb` — verified coverage, 0 SKUs with conflicting brand labels, 84 unique brand-tagged SKUs, artifacts: `sales_with_brand.parquet` / `tpr_with_brand.parquet` / `sku_brand.parquet`.
- `src/load.py` — promoted `load_all()` / `write_cache()` / `load_cached()` from `01_load.ipynb`. Downstream notebooks should `from src.load import load_cached` instead of re-reading raw files.
- `pipeline/01_load.ipynb` verified end-to-end: all 8 parquets written (mixed-type `Case Pack`, `Lead Time`, `UPC#`, `Case/Pallet`, `unit dimension`, `Shelf Life`, `Zip` auto-coerced to str). Pandas4Warning silenced.
- `feature_tree_v2.md` — locked two-feature spec (F1 reorder alert, F2 demand curve), shared clean-demand pipeline, 10 locked decisions, 5 use cases.
- `pipeline/` scaffold — 9 notebooks (`01_load` through `09_reorder_alerts`) with consistent skeleton (Imports → Load upstream → Do the work → Validate → Save → Promote).
- `src/` stubs — empty module per pipeline step; code gets promoted here after notebook verification.
- `notes/data_notes.md` — codified the post-01_load findings (83 SKUs / 37 orphans / 100% salesperson coverage / TPR breakdown / column naming gotchas / full mixed-type column list).
