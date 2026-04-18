# Project status

Rolling log of what's in progress, blocked, and next. Keep it short — update after finishing a pipeline step or hitting a blocker. This replaces the need to "catch up" a new chat.

## In progress

- **Pipeline step 04 (inventory rewind)** — rewind today's DC snapshot weekly, back to `min(DOCDATE)`, for SF/NJ/LA only. Plan:
  - **Anchor date** = `max(sales.DOCDATE)` (snapshot has no date column).
  - **Rewind formula** per (SKU, DC, week):
    `inv[w] = today_on_hand − Σ PO receipts in (w, today] − Σ transfers_in in (w, today] + Σ transfers_out in (w, today] + Σ sales_signed in (w, today]`
    (sales `QUANTITY_adj` is already sign-carrying, so returns handled naturally.)
  - **Scope filter:** sales `LOCNCODE ∈ {1, 2, 3}` (physical DCs); drop `E1` (Shopify), `W` (Weee), `ZD` (returns). PO `Location Code` already in {1,2,3}.
  - **New ingest:** `POP_InternalTransferHistory.XLSX` (Tier-2, 4,843 + 520 rows, **not currently in `01_load.ipynb`**). Load ad-hoc in 04 for now; promote to `load_all()` later if other steps need it. Biggest accuracy win — covers inter-DC moves that rewind would otherwise miss.
  - **Skipped on purpose:** assembly/repack (`POP_AssemblyOrders.XLSX`, niche); chargeback-side returns (financial-only, not inventory events).
  - **Confidence tag per (SKU, DC):** `min(on_hand_est)` across the series. Strongly negative = data gap → F1 treats this SKU as "low-confidence — manual review" (don't trust `is_stockout_week` here).
  - **Output:** `inv_weekly.parquet` with `ITEMNMBR, DC, week_start, on_hand_est, confidence`.

## Next

- **Pipeline step 05 (tag transactions)** — apply `is_promo` / `is_markdown` / `is_stockout_week` flags using `promo_cal` + SKU median price rule + `inv_weekly`. Import from `src.promo_cal`.

## Blocked

- (nothing blocking right now)

## Decisions needed

- (none open — the 10 open questions are all resolved in `feature_tree_v2.md`'s "Decisions locked" table)

## Recently completed

- `src/promo_cal.py` — promoted promo-calendar logic from `03_promo_calendar.ipynb`. Public API: `extract_promo_ym`, `fit_median_lag`, `impute_promo_ym`, `build_promo_calendar(tpr) -> (promo_cal, median_lag_days)`. Notebook re-executed end-to-end after the refactor; artifacts unchanged: `promo_cal.parquet` (1,391 × 3, 71 customers × 9 brands × 47 months), `promo_lag_meta.parquet` (median_lag_days = 128.0), regex coverage 98.1% → 100.0% with fallback.
- `src/brand.py` — promoted brand tagging from `02_brand.ipynb`. Exposes `tag_brands(sales, tpr)` which returns `{'sales', 'tpr', 'sku_brand'}`, plus lower-level helpers (`derive_prefix_map_auto`, `make_extract_brand_v2`, `apply_sku_prefix_override`, `fill_brand_from_sku_majority`). Verified: sales 100.0%, tpr 87.6% (remaining 12.4% are admin-only TPR rows with no brand — MIS/LOA/LOC/RETAILER).
- `pipeline/02_brand.ipynb` — verified coverage, 0 SKUs with conflicting brand labels, 84 unique brand-tagged SKUs, artifacts: `sales_with_brand.parquet` / `tpr_with_brand.parquet` / `sku_brand.parquet`.
- `src/load.py` — promoted `load_all()` / `write_cache()` / `load_cached()` from `01_load.ipynb`. Downstream notebooks should `from src.load import load_cached` instead of re-reading raw files.
- `pipeline/01_load.ipynb` verified end-to-end: all 8 parquets written (mixed-type `Case Pack`, `Lead Time`, `UPC#`, `Case/Pallet`, `unit dimension`, `Shelf Life`, `Zip` auto-coerced to str). Pandas4Warning silenced.
- `feature_tree_v2.md` — locked two-feature spec (F1 reorder alert, F2 demand curve), shared clean-demand pipeline, 10 locked decisions, 5 use cases.
- `pipeline/` scaffold — 9 notebooks (`01_load` through `09_reorder_alerts`) with consistent skeleton (Imports → Load upstream → Do the work → Validate → Save → Promote).
- `src/` stubs — empty module per pipeline step; code gets promoted here after notebook verification.
- `notes/data_notes.md` — codified the post-01_load findings (83 SKUs / 37 orphans / 100% salesperson coverage / TPR breakdown / column naming gotchas / full mixed-type column list).
