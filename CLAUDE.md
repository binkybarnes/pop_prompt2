# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

Before starting any task, read notes/README.md for the index to all project docs.

## Project context

Hack the Coast 2026 submission for **Prince of Peace Enterprises (POP)** Problem 1 (Demand & Order Intelligence) + Problem 3 (Inventory & Fulfillment). POP is a CPG importer/distributor (Tiger Balm, POP Ginger Chews, Ferrero, etc.) with 3 DCs (SF / NJ / LA), ~800 SKUs, and two very different sales channels (American mass/supermarket vs Asian herbal/specialty). No API, no WMS, no cloud warehouse — everything is CSV/Excel exports out of Microsoft Dynamics GP + Cavallo SalesPad.

The user is **not a business person**; prefer plain-English over jargon, explain CPG/ERP terms on first use, and ground every recommendation in what exists in `notes/`.

## Repo layout

- `notes/` — **source of truth** for context, plans, and decisions. **Always start with `notes/README.md`** — it indexes every other doc and tells you which ones to read for your current task. Key files behind that index: `feature_tree_v2.md` (locked spec), `data_notes.md` (what the data actually looks like), `status.md` (what's currently in progress).
- `pipeline/` — step-by-step pipeline notebooks (`01_load.ipynb` through `09_reorder_alerts.ipynb`). Each notebook follows the same skeleton: Imports → Load upstream artifact → Do the work → Validate → Save → Promote note. Intermediate parquets live in `pipeline/artifacts/` (gitignored).
- `src/` — production Python modules. Logic gets promoted here from notebooks once verified (see each notebook's `## 6. Promote` section). Start with stubs; fill in as each step is validated.
- `data/` — **gitignored**. Raw POP files (CSV + XLSX). The only Tier-1 files that matter for Problem 1 are `POP_SalesTransactionHistory.csv`, `POP_InventorySnapshot.xlsx`, `POP_ItemSpecMaster.xlsx`, `POP_VendorMaster.xlsx`, `POP_PurchaseOrderHistory.XLSX`, `POP_ChargeBack_Deductions_Penalties_Freight.xlsx` (only the `Data - Deductions & Cause Code` sheet), `SLPRSNID_SALESCHANNEL_KEY.xlsx`, `POP_DataDictionary.xlsx`.
- `exploration_f1.ipynb` — earlier scratch notebook for F1 (promo/markdown tagging + brand extraction). Being migrated into `pipeline/02_brand.ipynb` + `pipeline/05_tag_transactions.ipynb`. Reference only; don't extend it.
- `exploration.ipynb` — scratch notebook.

## Architecture: the 5-layer pipeline

POP's own framing, which we follow. **Each layer only reads the previous layer's output** so three people can work in parallel:

1. **Ingest** (F0) — load CSV/XLSX → typed dataframes, join on SKU/customer/date.
2. **Clean** (F1, F2, F9) — strip promo-inflated sales, estimate lost demand from stockouts, age out hold-POs → `cleaned_demand`.
3. **Segment** (F3, F8) — per-channel views, lunar seasonality overlay → `channel_demand`.
4. **Reorder** (F4, F12) — `on_hand − allocated − run_rate × lead_time < safety_stock` → `reorder_alerts.xlsx`.
5. **Present** (F5, F6, F7) — buyer-readable Excel, before/after comparison, assumption tags.

**Deliverable #4 (before/after for 2–3 showcase SKUs) is the money slide** — reverse-plan from it.

## Key domain concepts (frequently needed)

- **TPR (Temporary Price Reduction)** = retailer discounts product on the shelf, bills POP later via a chargeback. Invoice price looks normal at the time of sale; the discount surfaces 1–3 months later as `CRED02/03/04/05/-PRO/15/10-D/-DIS/19` rows in the chargeback file.
- **Markdown** = POP sells cheap directly on the invoice (short-dated clearance). Shows up as `Unit_Price_adj` well below SKU median.
- F1 must flag **both** and subtract them from "clean demand" fed to the forecaster.
- **Chargebacks do NOT join to sales on `SOPNUMBE`** — they use `RTN#` credit-memo numbers. Join instead on `Customer Number + extracted Brand + extracted MM/YY from Item Description`.
- **Location codes (`LOCNCODE`)**: `1`=SF, `2`=NJ, `3`=LA, `E1`=Shopify SF, `W`=Weee, `ZD`=Returns.
- **SOP** = Sales Order Processing (Microsoft Dynamics GP term); an SOP number is an order number.

## Working conventions

- **Environment**: the user runs this project in a **mamba env named `3.11mamba`** (Python 3.11). The Jupyter kernel is this env. Any CLI invocation (pytest, pip install, running a `src/` module directly) must be prefixed with `mamba run -n 3.11mamba …` — a bare `python3` on this machine resolves to a different miniforge env (Python 3.10, missing deps). If you want to install a package, use `mamba run -n 3.11mamba pip install <pkg>`.
- **Edit notebooks with `NotebookEdit`**, not by pasting code for the user to copy manually.
- **Consume upstream pipeline artifacts via `from src.load import load_cached`** rather than re-reading raw files. `load_cached()` returns the 8-dict of dataframes. Only `pipeline/01_load.ipynb` should touch `data/` directly. Each pipeline notebook self-loads what it needs at the top — don't rely on shared kernel state across notebooks.
- Treat `notes/` files as durable project memory — update them when scope/decisions change; don't silently delete prior ideas without showing the mapping.
- Data files are gitignored; never commit anything from `data/`.

## Common tasks

- **Start the notebook**: `jupyter lab` (or run via the VS Code / Antigravity Jupyter extension). Kernel must be the `3.11mamba` env.
- **Reload data after raw-file schema changes**: re-run `pipeline/01_load.ipynb` end-to-end (rewrites the parquets under `pipeline/artifacts/`). All other notebooks then pick up the change via `load_cached()` — no manual rewire needed.
- **Pick showcase SKUs**: criteria are `lines ≥ 1000`, `channels ≥ 2`, brand recognizable, ideally has TPR activity. Current candidates: `T-32206` (Tiger Balm Patch Warm), `F-04111` (POP Ginger Chews Original), `T-22010`, `T-31510`.
