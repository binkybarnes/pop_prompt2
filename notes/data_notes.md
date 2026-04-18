# Data notes

What the data actually looks like after running `pipeline/01_load.ipynb`. Update this file whenever you discover something non-obvious about the shape of the data — anything that would cause a future chat to waste time re-deriving.

## Scope — the data is a curated sample, not production

The POP hackathon pack is NOT the full 800-SKU production dataset. It's a curated slice:

- **83 unique SKUs in sales** over 3.3 years (`2023-01-03` → `2026-04-13`, 236,818 rows)
- **64 SKUs in item master** — where lead time, supplier, case pack live
- **73 inventory rows per DC** (SF, NJ, LA — one snapshot, not historical)
- **46 salesperson IDs** in the channel key
- **6,868 TPR / promo chargeback rows** (out of 18,804 total chargebacks)

When presenting, say "of the 83 SKUs in the sample…" — not "of 800 SKUs."

## File layout (Tier 1 only)

| File | Sheet name(s) | Rows × cols | Key column |
|---|---|---|---|
| `POP_SalesTransactionHistory.csv` | n/a | 236,818 × 23 | `ITEMNMBR` |
| `POP_InventorySnapshot.xlsx` | `Site 1 - SF`, `Site 2 - NJ`, `Site 3 - LA` | 73 rows each | `Item Number` |
| `POP_ItemSpecMaster.xlsx` | `Item Spec Master` | 65 × 15 | `Item Number` |
| `POP_VendorMaster.xlsx` | `Supplier Master` | 73 × 17 | `Brand` |
| `POP_PurchaseOrderHistory.XLSX` | `PO Order History 2023-2025` | 5,281 × 16 | `PO Number` |
| `POP_ChargeBack_Deductions_Penalties_Freight.xlsx` | `Data - Deductions & Cause Code` | 18,804 × 13 | `Customer Number` |
| `SLPRSNID_SALESCHANNEL_KEY.xlsx` | first sheet | 46 × 3 | `SLPRSNID` |

## Column naming gotchas (joins get these wrong easily)

- Sales uses **`ITEMNMBR`**; item master and inventory use **`Item Number`**.
- Sales uses **`SLPRSNID`** (one word); chargebacks use **`Salesperson ID`** (with space).
- Sales uses **`CUSTNMBR`**; chargebacks use **`Customer Number`**.
- Sales date column is **`DOCDATE`**; chargebacks use **`Document Date`**.

## SKU coverage — the long tail is not usable

- **37 / 83 sales SKUs (~14.6% of sales rows) have no item-master row.**
  Prefixed `A-`, `AC-`, `D-` — almost certainly **discontinued or assembly-only SKUs** that got pruned from active master data but remain in historical transactions.
- **33 / 83 sales SKUs have no inventory row in any DC.** Heavily overlaps with the 37 above.
- **Per-DC inventory coverage: SF / NJ / LA each cover 60.2% (50 / 83) of sales SKUs.**

**Implication for F1:** auto-recommend reorders for the ~46 well-covered SKUs. The rest get a "insufficient master data — manual review" flag. Don't hallucinate lead times for orphans.

## Salesperson → channel mapping — clean

**100% coverage.** All 46 salesperson IDs in sales appear in the key file. Notebook 06 will join cleanly with zero orphans.

Channel codes:
- **`MM`** = American Mainstream Market
- **`AM`** = Asian Ethnic Market
- **`HF`** = Health Food Market

The `SALESCHANNEL` column is the code; `SALESCHANNEL_DESC` is the full name.

> Don't trust the `Customer Type` field in sales — 181 unique free-text values, human-entered. Use Salesperson ID instead (confirmed by POP's president in conversation with the team).

## TPR / promo signal

**6,868 TPR chargeback rows (36.5% of all chargebacks).** Cause-code breakdown of the TPR subset:

| Code | Count | Share |
|---|---:|---:|
| `CRED03` | 4,113 | 60% |
| `CRED05` | 1,645 | 24% |
| `CRED02` | 571 | 8% |
| `CRED04` | 259 | 4% |
| `CRED10-D` | 150 | 2% |
| `CRED-PRO` | 130 | 2% |

Filter expression currently used: `Cause Code Desc` matches regex `TPR|promo|price reduction` (case-insensitive).

**Join method (important — not obvious):** chargebacks do NOT link to sales on `SOPNUMBE`. They use `RTN#` credit-memo numbers. Instead, join on `(Customer Number + extracted Brand + Year-Month)`. See `exploration_f1.ipynb` cells 11-12 (initial build) and cells 13-18 (brand extraction v2 with prefix map).

**Promo calendar currently has 637 `(cust × brand × ym)` tuples.** Some TPR rows have no MM/YY in their item description and get dropped; notebook `03_promo_calendar.ipynb` recovers them via lag imputation.

## Data quality gotchas

| Column | Issue | Fix |
|---|---|---|
| `item_master.Case Pack` | mixed `int` + `str` (`24` vs `"24 ct"`) | coerce to str before parquet |
| `item_master.Lead Time` | **mixed `float` + `str`** (e.g. `45.0` vs `"45 days"`) | **must re-parse to numeric in notebook 02/04** — F1 reorder math needs this numeric |
| `item_master.UPC#` | mixed `int` + `str` | coerce to str before parquet |
| `item_master.Case/ Pallet` | mixed `int` + `str` | coerce to str before parquet |
| `item_master.unit dimension (L*W*H) (in)` | mixed `int` + `str` | coerce to str before parquet |
| `item_master.Shelf Life (Months)` | mixed `int` + `str` | coerce to str before parquet |
| `vendor_master.Zip` | mixed `int` + `str` (`90210` vs `"90210-1234"`) | coerce to str before parquet |
| `sales.ZIPCODE / STATE / CITY` | 2,000–5,000 nulls each | unused for demand math, ignore |
| `sales.Product Type` | 490 nulls | not on the critical path |
| `sales.Customer Type` | 4 nulls | don't rely on this field anyway — see channel mapping note |
| `sales.SLPRSNID` | 4 nulls | tag as unknown-channel |

All mixed-type columns are auto-coerced to string by `src.load.write_cache()` — but that means reading `item_master.Lead Time` back from parquet gives strings, so downstream code must `pd.to_numeric(..., errors='coerce')` before using it in reorder math.

Clean columns (0 nulls, safe to trust): `LOCNCODE`, `XTNDPRCE_adj`, `UOM_Price`, `Margin_Pct_adj`, `DOCDATE`, `ITEMNMBR`, `CUSTNMBR`.

## DC / location codes

`LOCNCODE` mapping:
- `1` = SF, `2` = NJ, `3` = LA
- `E1` = Shopify SF, `W` = Weee, `ZD` = Returns

Only `1 / 2 / 3` correspond to the three DCs that appear in the inventory snapshot.

## Historical inventory — must be reconstructed

Only today's snapshot is provided. For stockout detection (F1 input, F2 `is_stockout_week` flag), historical per-SKU-per-DC inventory has to be rewound from the snapshot via `(−POs received, +shipments)` anchored on PO receipt dates. See notebook `04_inventory_rewind.ipynb`. Expect noise — document it as a listed assumption in the demo.

## Showcase SKU candidates

All verified to be in both item master and inventory snapshot:

- **`T-32206`** — Tiger Balm Patch Warm
- **`F-04111`** — POP Ginger Chews Original
- **`T-22010`**, **`T-31510`** — fill-ins

Selection criteria: ≥1,000 sales lines, ≥2 channels, recognizable brand, ideally has TPR activity.
