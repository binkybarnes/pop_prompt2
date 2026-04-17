# Data Files Guide

Total: 10 files + 1 folder in `data/`. Most of these are **not needed for Problem 1**.

## TL;DR — tier 1 is all you need for Problem 1

| Tier | File | Rows | Use |
|---|---|---|---|
| **1. CORE** | `POP_SalesTransactionHistory.csv` | ~237k | Sales for demand signal |
| **1. CORE** | `POP_InventorySnapshot.xlsx` | 73 × 3 DCs | Current stock levels |
| **1. CORE** | `POP_ItemSpecMaster.xlsx` | 65 SKUs | SKU metadata (lead time, MOQ, shelf life) |
| **1. CORE** | `POP_VendorMaster.xlsx` | 73 | Supplier info |
| **1. CORE** | `POP_PurchaseOrderHistory.XLSX` | 5,281 | PO arrivals for inventory reconstruction |
| **1. CORE** | `POP_ChargeBack_Deductions_Penalties_Freight.xlsx` (only sheet: `Data - Deductions & Cause Code`) | 18,804 | **TPR cause codes = promo proxy** |
| **1. CORE** | `POP_DataDictionary.xlsx` | 84 + 33 | Field definitions & glossary |
| 2. useful | `POP_InternalTransferHistory.XLSX` | 4,843 + 520 | Inter-DC transfers (matters more for Problem 3) |
| 3. skip | `POP_AssemblyOrders.XLSX` | 1,038 | Internal assembly/repack (niche) |
| 3. skip | `POP_ImportShipmentStatus.xlsx` | multi-year mess | Ocean container tracking; per-year sheets w/ Unnamed cols |
| 3. skip | `POP_InternalTransferRequests.xlsx` | 6 lane-logs | Weekly request spreadsheets, messy format |
| 3. skip | `POP_Catalog_2024.pdf` / `POP_CatalogSellSheets_2024/` | — | Marketing material |

**On format:** pandas reads `.xlsx` natively (`pd.read_excel`). No conversion needed. The noisy files have `Unnamed: 0 ... Unnamed: N` columns because the original spreadsheets use merged header rows — those are hard to parse and mostly not core, so skip them.

---

## Tier 1 file details

### 1. POP_SalesTransactionHistory.csv (THE main file)
~237k rows. Jan 2023–Dec 2025 (assumed). Every shipment line.

| Column | Meaning |
|---|---|
| `LOCNCODE` | Shipping DC: `1`=SF, `2`=NJ, `3`=LA, `E1`=Shopify SF, `W`=Weee marketplace, `ZD`=Returns |
| `SLPRSNID` | Salesperson ID (anonymized) |
| `CUSTNMBR` | Internal Customer ID |
| `CUSTNAME` | Customer name (anonymized) |
| `CITY` / `STATE` / `ZIPCODE` | Shipping geo |
| `SOP TYPE` | `Invoice` or `Return` |
| `SOPNUMBE` | Order number |
| `DOCDATE` | Document/ship date |
| `ITEMNMBR` | **SKU code** (primary join key everywhere) |
| `ITEMDESC` | SKU description |
| `QUANTITY_adj` | Units shipped (anonymized/adjusted) |
| `UOFM` | Unit of measure (`CASE`, `EACH`, `BOX`, `TIN`, etc. — see glossary) |
| `QTYBSUOM` | Sellable units (after UOM conversion) |
| `XTNDPRCE_adj` | Wholesale price (extended) |
| `EXTDCOST_adj` | COGS (extended) |
| `Customer Type` | Sub-account type — **likely our channel proxy** |
| `Product Type` | Sub-product category |
| `Source_File` | Provenance tag |
| `Gross_Profit_adj` | Pre-computed gross profit |
| `Margin_Pct_adj` | Pre-computed margin |
| `UOM_Price` / `Unit_Price_adj` | Per-unit price — **compare to median → detect markdowns** |

**Notes:**
- `_adj` suffix = anonymized/scaled (directionally correct, not real $).
- Returns appear as `SOP TYPE = Return`; filter or net them when computing demand.
- To compute **organic vs markdown demand:** per SKU, get the typical unit price distribution; flag transactions below e.g. the 25th percentile or with matching TPR chargeback in same week.

### 2. POP_InventorySnapshot.xlsx
3 sheets: `Site 1 - SF`, `Site 2 - NJ`, `Site 3 - LA`. 73 rows each.

| Column | Meaning |
|---|---|
| `Item Number` | SKU (join → sales/SKU master) |
| `Description` | SKU description |
| `Available` | On-hand minus allocated |
| `On Hand` | Physical stock |

**Notes:**
- `On Hand − Available = Allocated` (the polluted field — hold-PO stale holds live here).
- **Today only** — no history. We reconstruct past inventory from sales + POs.

### 3. POP_ItemSpecMaster.xlsx (SKU master)
65 rows, 1 sheet.

Key columns: `Item Number`, `Description`, `Case Pack`, `Case/Pallet`, `Country of Origin`, **`Shelf Life (Months)`**, **`Lead Time`**, **`MOQ`**, `Allergens`, `Manufacturer/CoPacker`, + dimensions.

Used for: reorder math (lead time, MOQ), shelf-life-aware decisions, container packing (units/pallet).

### 4. POP_VendorMaster.xlsx (Supplier master)
73 rows, 1 sheet.

Key columns: `Brand`, `Product Line`, `Category`, `Vendor ID` (join key), `Country`, **`Seasonality`** (Y/N), `# of SKUs (active)`, `A&P (Y/N)` (promo support), `Shipment Terms` (FOB/CIF/EXW/ToDoor), `Payment Terms`.

Used for: grouping SKUs by supplier for MOQ basket ordering, seasonality flag.

### 5. POP_PurchaseOrderHistory.XLSX
5,281 rows. 2023–2025 PO receipts.

| Column | Meaning |
|---|---|
| `PO Number` / `POP Receipt Number` | Ids |
| `PO Date` | When PO was placed |
| `Required Date` / `Promised Ship Date` | Supplier commitments |
| `Receipt Date` | **When it actually arrived at the DC** |
| `Item Number` | SKU |
| `QTY Shipped` / `QTY Invoiced` | Units |
| `Unit Cost` / `Extended Cost` | Landed cost |
| `Vendor ID` | Supplier |
| `Location Code` | Receiving DC |
| `Shipping Method` | Ocean / air / truck |

Used for: **inventory reconstruction** (walk backward from today using sales out + PO in), measuring **actual vs promised lead time** per supplier.

### 6. POP_ChargeBack_Deductions_Penalties_Freight.xlsx (MULTI-SHEET)
Only one sheet matters for Problem 1: **`Data - Deductions & Cause Code`** (18,804 rows).

| Column | Meaning |
|---|---|
| `Location Code` | DC |
| `Salesperson ID` / `Customer Number` | Who & what |
| `SOP Number` | Link back to original sales order |
| `Document Date` | When the chargeback hit |
| **`Cause Code`** | The code (e.g., TPR, short-ship, late) |
| **`Cause Code Desc`** | Human-readable reason |
| `Item Description` | SKU description |
| `Extended Price` | $ amount of the deduction |

**This is where TPR codes live → our promo-calendar proxy.** Also where short-ship codes live → our **lost-sales corroboration signal**.

First thing to do: `df['Cause Code'].value_counts()` to see all codes + their frequencies.

Other sheets in this file (ignore for P1):
- `Data-Items Returns` (returns — matters if we net returns)
- `Data-Damage Allowance` (damaged product deductions)
- `Data-Penalty` (explicit penalty fees — P3 relevant)
- `Data-Outbound Freight` (freight costs — P3 relevant)
- `Data-Transfer Cost` / `Data-Pallet Cost` / `Data-Damaged Write Off Whse` (accounting detail — ignore)
- `Summary` (merged-cell pivot — unreadable programmatically)

### 7. POP_DataDictionary.xlsx
2 sheets: `Data Dictionary` (field defs) and `Glossary` (decoders for LOCNCODE, UOFM, payment/shipment terms). Read once, keep open as reference.

---

## Key join keys

- `ITEMNMBR` / `Item Number` joins: Sales ↔ Inventory ↔ ItemSpecMaster ↔ POHistory ↔ ChargeBack
- `Vendor ID` joins: POHistory ↔ VendorMaster
- `CUSTNMBR` / `Customer Number` joins: Sales ↔ ChargeBack
- `SOPNUMBE` / `SOP Number` joins: Sales line ↔ ChargeBack line (lets us tie a chargeback back to the original order)
- `LOCNCODE` / `Location Code` joins: everything across DCs

## Location code decoder (memorize)

| Code | Site |
|---|---|
| 1 | San Francisco DC |
| 2 | New Jersey DC |
| 3 | Los Angeles DC |
| E1 | SF Shopify eCom warehouse |
| W | Weee! marketplace (eCom) |
| ZD | Returns / write-off |
| L | Copackaging site (assembly) |
| U | Production/packaging site (assembly) |

## Quirks to watch for

- **Sales: ~237k rows × ~65 SKUs** — that's ~3,600 sales lines per SKU over 3 years. Plenty of data per SKU. No cold-start problem in provided data.
- **Only 65 SKUs in ItemSpecMaster** but briefing says POP has ~1,000. Hackathon dataset is a **curated subset** — don't be surprised.
- **Only 73 inventory rows per DC** — same subset. All 73 should have an entry in every DC (some at 0).
- **Inventory snapshot is single-day.** Use PO receipt dates + sales ship dates to reconstruct history.
- **`_adj` suffix** columns are anonymized. Real $ amounts scrambled but relative patterns preserved.
- **Returns** in sales file have `SOP TYPE = Return`. Decide if you net them against demand or track separately.
- **Location E1 / W** are eCom channels — different dynamics from DC 1/2/3.
