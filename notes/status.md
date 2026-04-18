# Project status

Rolling log of what's in progress, blocked, and next. Keep it short — update after finishing a pipeline step or hitting a blocker. This replaces the need to "catch up" a new chat.

## In progress

- **Pipeline step 03 (promo calendar)** — notebook wired and verified; **ready to promote** to `src/promo_cal.py` once we resume. Results on real data:
  - Regex hit 98.1% of TPR rows directly; lag imputation filled the last 1.9% → **100% promo_ym coverage**.
  - Median lag = 128 days (IQR 89–194, right-skewed with long tail — typical retailer billing).
  - `promo_cal.parquet` = **1,391 unique `(CUSTNMBR, brand, promo_ym)` tuples** across 71 customers × 9 brands × 47 months. 2x the prior-run count, because step 02's better brand extractor (87.6% TPR coverage vs v1's 25%) labeled many more rows.
  - Decision: ship global median imputation as-is. Blast radius is only 131 rows, and more sophisticated per-customer / per-cause-code medians would still fall back to global for most customers. Note as assumption on demo slide.
  - Side outputs also saved: `promo_lag_meta.parquet` (1 row, holds `median_lag_days = 128`).

## Next

- **Promote step 03** — extract the logic from `pipeline/03_promo_calendar.ipynb` into `src/promo_cal.py`. Entry point: `build_promo_calendar(tpr_with_brand) -> (promo_cal, median_lag_days)`. Expose `extract_promo_ym`, `fit_median_lag`, `impute_promo_ym`, `build_promo_calendar`.
- **Pipeline step 04 (inventory rewind)** — rewind today's DC snapshot via POs + shipments. Needs `Lead Time` parsed numeric (stored as string in `item_master.parquet`, see `data_notes.md`; use `pd.to_numeric(..., errors='coerce')`).
- **Pipeline step 05 (tag transactions)** — apply `is_promo` / `is_markdown` / `is_stockout_week` flags using `promo_cal` + SKU median price rule.

## Blocked

- (nothing blocking right now)

## Decisions needed

- (none open — the 10 open questions are all resolved in `feature_tree_v2.md`'s "Decisions locked" table)

## Recently completed

- `src/brand.py` — promoted brand tagging from `02_brand.ipynb`. Exposes `tag_brands(sales, tpr)` which returns `{'sales', 'tpr', 'sku_brand'}`, plus lower-level helpers (`derive_prefix_map_auto`, `make_extract_brand_v2`, `apply_sku_prefix_override`, `fill_brand_from_sku_majority`). Verified: sales 100.0%, tpr 87.6% (remaining 12.4% are admin-only TPR rows with no brand — MIS/LOA/LOC/RETAILER).
- `pipeline/02_brand.ipynb` — verified coverage, 0 SKUs with conflicting brand labels, 84 unique brand-tagged SKUs, artifacts: `sales_with_brand.parquet` / `tpr_with_brand.parquet` / `sku_brand.parquet`.
- `src/load.py` — promoted `load_all()` / `write_cache()` / `load_cached()` from `01_load.ipynb`. Downstream notebooks should `from src.load import load_cached` instead of re-reading raw files.
- `pipeline/01_load.ipynb` verified end-to-end: all 8 parquets written (mixed-type `Case Pack`, `Lead Time`, `UPC#`, `Case/Pallet`, `unit dimension`, `Shelf Life`, `Zip` auto-coerced to str). Pandas4Warning silenced.
- `feature_tree_v2.md` — locked two-feature spec (F1 reorder alert, F2 demand curve), shared clean-demand pipeline, 10 locked decisions, 5 use cases.
- `pipeline/` scaffold — 9 notebooks (`01_load` through `09_reorder_alerts`) with consistent skeleton (Imports → Load upstream → Do the work → Validate → Save → Promote).
- `src/` stubs — empty module per pipeline step; code gets promoted here after notebook verification.
- `notes/data_notes.md` — codified the post-01_load findings (83 SKUs / 37 orphans / 100% salesperson coverage / TPR breakdown / column naming gotchas / full mixed-type column list).
