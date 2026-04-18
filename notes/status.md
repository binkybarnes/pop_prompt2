# Project status

Rolling log of what's in progress, blocked, and next. Keep it short — update after finishing a pipeline step or hitting a blocker. This replaces the need to "catch up" a new chat.

## In progress

- (nothing actively in progress — step 06 promoted to `src/channel.py`, next up is step 07)

## Next

- **Pipeline step 07 (clean demand)** — produce `cleaned_demand.parquet` filtered to `is_clean_demand == True`, aggregated to the level F1/F2 need (per-SKU per-week or per-customer-week). Upstream is `sales_tagged_channel.parquet`.
- **Revisit feature scope (F1/F2) after pipeline** — stockout-caused demand loss is <0.2% of rows even at `LOST_DEMAND_COVER_K=10` (K=1 -> 55 rows, K=10 -> 440). That's a real finding: POP's demand is mostly promo/markdown-polluted (14.7%), not stockout-polluted. The F1 forecaster's main cleaning job is promos, not stockout imputation. Worth discussing whether that shifts F1/F2 framing after all steps are wired.

## Blocked

- (nothing blocking right now)

## Decisions needed

- (none open — the 10 open questions are all resolved in `feature_tree_v2.md`'s "Decisions locked" table)

## Recently completed

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
