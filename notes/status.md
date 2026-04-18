# Project status

Rolling log of what's in progress, blocked, and next. Keep it short — update after finishing a pipeline step or hitting a blocker. This replaces the need to "catch up" a new chat.

## In progress

- **Pipeline step 02 (brand extraction)** — next up. Port `extract_brand_v2`, `PREFIX_MAP_AUTO`, `PREFIX_MAP_MANUAL` from `exploration_f1.ipynb` cells 13–18 into `pipeline/02_brand.ipynb`. Consume upstream via `src.load.load_cached()`. Run coverage report on both `sales` and `tpr`. Promote to `src/brand.py`.

## Next

- **Pipeline step 03 (promo calendar)** — build `(cust × brand × ym)` calendar with lag imputation. Lag distribution analysis exists in `exploration_f1.ipynb` cell 15.
- **Lead Time parsing** — when step 04 (inventory rewind) or F1 needs numeric lead time, remember it's stored as string in `item_master.parquet` (see `data_notes.md`). Use `pd.to_numeric(..., errors='coerce')`.

## Blocked

- (nothing blocking right now)

## Decisions needed

- (none open — the 10 open questions are all resolved in `feature_tree_v2.md`'s "Decisions locked" table)

## Recently completed

- `src/load.py` — promoted `load_all()` / `write_cache()` / `load_cached()` from `01_load.ipynb`. Downstream notebooks should `from src.load import load_cached` instead of re-reading raw files.
- `pipeline/01_load.ipynb` verified end-to-end: all 8 parquets written (mixed-type `Case Pack`, `Lead Time`, `UPC#`, `Case/Pallet`, `unit dimension`, `Shelf Life`, `Zip` auto-coerced to str). Pandas4Warning silenced.
- `feature_tree_v2.md` — locked two-feature spec (F1 reorder alert, F2 demand curve), shared clean-demand pipeline, 10 locked decisions, 5 use cases.
- `pipeline/` scaffold — 9 notebooks (`01_load` through `09_reorder_alerts`) with consistent skeleton (Imports → Load upstream → Do the work → Validate → Save → Promote).
- `src/` stubs — empty module per pipeline step; code gets promoted here after notebook verification.
- `notes/data_notes.md` — codified the post-01_load findings (83 SKUs / 37 orphans / 100% salesperson coverage / TPR breakdown / column naming gotchas / full mixed-type column list).
