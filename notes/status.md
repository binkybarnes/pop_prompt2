# Project status

Rolling log of what's in progress, blocked, and next. Keep it short — update after finishing a pipeline step or hitting a blocker. This replaces the need to "catch up" a new chat.

## In progress

- (nothing actively in progress — step 05 just verified, next up is step 06)

## Next

- **Pipeline step 06 (clean demand)** — produce `cleaned_demand.parquet` filtered to `is_clean_demand == True`, aggregated to the level F1/F2 need (per-SKU per-week or per-customer-week). Promote step 05 to `src/tagging.py` first.

## Blocked

- (nothing blocking right now)

## Decisions needed

- (none open — the 10 open questions are all resolved in `feature_tree_v2.md`'s "Decisions locked" table)

## Recently completed

- **Pipeline step 05 (tag transactions)** — verified end-to-end. All 236,818 sales rows preserved, 4 flags added (`is_promo`, `is_markdown`, `is_stockout_week`, `is_clean_demand`).
  - `is_promo` = exact (CUSTNMBR, brand, sale_ym) match against `promo_cal`. **12.4%** of rows (29,421). Brand mix: tiger balm 22k / ginger chew 7.3k / am gsg 86. Sell-in-window refinement deferred.
  - `is_markdown` = `Unit_Price_adj < 0.70 × SKU median` (median computed on non-promo positive-price rows to avoid self-anchoring low). **2.3%** (5,491). Median markdown depth 35% off.
  - `is_stockout_week` = `on_hand_est ≤ 0` at sales week_start AND inv `confidence == 'high'`. **0.05%** (98 rows — all T-32206 SF, which dips to -17k within its 26k tolerance). Nullable boolean: NA for 30,563 rows without inv coverage (E1/W/ZD + SKUs not in snapshot).
  - `is_clean_demand` = none of the three fire. **85.5%** (202,476 rows — the F1 forecaster's input).
  - Markdown threshold (0.70) + rev-lookup on SKU median shown with histogram validation.
  - Artifact: `sales_tagged.parquet` (236,818 × 35).
  - **Not yet promoted** to `src/tagging.py` — do before step 06.
- **Pipeline step 04 (inventory rewind)** — verified end-to-end. Anchor `2026-04-13`, rewind start `2023-01-02`, 173 weekly snapshots × 219 (SKU × DC) = 37,887 rows.
  - Identity check PASS (`max |today_rewind − snapshot| = 0.000`).
  - UOM fix: `sales.QTY_BASE = QUANTITY_adj × QTYBSUOM` row-level; `transfers.QTY_BASE = TRX QTY × pack` via per-(SKU, UOM) median QTYBSUOM learned from sales (fallback: per-SKU median, then 1.0). POs verified in base units (T-32206 lifetime PO/sales ratio 0.92).
  - Confidence breakdown: **191 high / 28 low** (12.8% low-confidence, down from pre-UOM-fix where T-32206 alone was dipping to -3M base units).
  - T-32206 spot check all-high: SF min=-17,450 / NJ min=+117,196 / LA min=+90,529 against today = 264k/365k/144k.
  - Artifacts: `inv_weekly.parquet` (37,887 × 5), `inv_rewind_meta.parquet` (anchor/start/tolerance).
  - **Known small gap:** 865 nulls in `on_hand_est` (2.3%) — not investigated yet, low priority.
  - **Not yet promoted** to `src/inventory.py` — do after step 05 validates it.
- `src/promo_cal.py` — promoted promo-calendar logic from `03_promo_calendar.ipynb`. Public API: `extract_promo_ym`, `fit_median_lag`, `impute_promo_ym`, `build_promo_calendar(tpr) -> (promo_cal, median_lag_days)`. Notebook re-executed end-to-end after the refactor; artifacts unchanged: `promo_cal.parquet` (1,391 × 3, 71 customers × 9 brands × 47 months), `promo_lag_meta.parquet` (median_lag_days = 128.0), regex coverage 98.1% → 100.0% with fallback.
- `src/brand.py` — promoted brand tagging from `02_brand.ipynb`. Exposes `tag_brands(sales, tpr)` which returns `{'sales', 'tpr', 'sku_brand'}`, plus lower-level helpers (`derive_prefix_map_auto`, `make_extract_brand_v2`, `apply_sku_prefix_override`, `fill_brand_from_sku_majority`). Verified: sales 100.0%, tpr 87.6% (remaining 12.4% are admin-only TPR rows with no brand — MIS/LOA/LOC/RETAILER).
- `pipeline/02_brand.ipynb` — verified coverage, 0 SKUs with conflicting brand labels, 84 unique brand-tagged SKUs, artifacts: `sales_with_brand.parquet` / `tpr_with_brand.parquet` / `sku_brand.parquet`.
- `src/load.py` — promoted `load_all()` / `write_cache()` / `load_cached()` from `01_load.ipynb`. Downstream notebooks should `from src.load import load_cached` instead of re-reading raw files.
- `pipeline/01_load.ipynb` verified end-to-end: all 8 parquets written (mixed-type `Case Pack`, `Lead Time`, `UPC#`, `Case/Pallet`, `unit dimension`, `Shelf Life`, `Zip` auto-coerced to str). Pandas4Warning silenced.
- `feature_tree_v2.md` — locked two-feature spec (F1 reorder alert, F2 demand curve), shared clean-demand pipeline, 10 locked decisions, 5 use cases.
- `pipeline/` scaffold — 9 notebooks (`01_load` through `09_reorder_alerts`) with consistent skeleton (Imports → Load upstream → Do the work → Validate → Save → Promote).
- `src/` stubs — empty module per pipeline step; code gets promoted here after notebook verification.
- `notes/data_notes.md` — codified the post-01_load findings (83 SKUs / 37 orphans / 100% salesperson coverage / TPR breakdown / column naming gotchas / full mixed-type column list).
