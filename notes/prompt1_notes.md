# POP Hackathon — Problem 1 (Demand & Order Intelligence)

## The Company
- **Prince of Peace (POP):** CPG importer/distributor, founded 1983, HQ Livermore CA.
- Does NOT manufacture most of what it sells. Imports + warehouses + sells + ships ~800 SKUs (~1,000 with variants) to 100,000+ retail outlets.
- Proprietary brands: Ginger Chews, Ginger Honey Crystals, American Ginseng, teas.
- Distributed brands: Tiger Balm, Ferrero Rocher, Nutella, Ricola, Bee & Flower Soap.
- 3 US distribution centers (DCs). 5 full-time + 2 part-time buyers manage ~1,000 SKUs manually in Excel.

## Two Divisions, Same Warehouses
- **American Market** (Walmart, CVS, etc.): planogram-driven, predictable, annual category reviews, but can be dropped with 1–2 months notice.
- **Asian Market** (ethnic grocery chains): opportunistic, reactive, lumpy demand, holiday spikes (Lunar New Year, Mid-Autumn, etc.), salesperson-driven pushes.
- **Health Food** (via UNFI/KeHE distributors): POP can't see end retailers, steady-ish with quarterly promo swings.
- **eCom** (Amazon 1P/3P, Shopify DTC): ~10% of business, long-tail.

## Tech Stack (the constraint)
- **Microsoft Dynamics GP** (on-prem ERP) + **Cavallo SalesPad** (orders/purchasing/picking).
- **No WMS, no inventory planning software, no API layer, no cloud data warehouse.**
- Solutions must ingest **CSV/Excel** and output **CSV/Excel** to be adoptable.

## Vocabulary
- **Buyer:** POP employee who decides what to reorder from suppliers. Each manages ~200 SKUs.
- **SKU:** unique product variant (flavor + pack size). Same product can have 5–10+ SKUs serving different channels; NOT interchangeable.
- **Customer:** a retail store/chain buying from POP (not end consumer).
- **Demand:** number of units customers WANTED in a period. ≠ Sales (what shipped).
- **Stockout:** out of a SKU.
- **Markdown:** selling discounted to clear inventory.
- **Backorder:** promising to ship later when stock arrives. POP's big customers don't accept these → demand vanishes.
- **Safety stock:** buffer inventory for unexpected spikes/delays.
- **Reorder point:** trigger level for placing a new order (above safety stock).
- **Lead time:** days between ordering from supplier and receiving. Variable for ocean freight (port congestion, FDA holds, customs).
- **Chargeback:** penalty fee from retailer when POP ships late/incomplete.
- **TPR (Temporary Price Reduction):** a promo the retailer runs and deducts from POP's invoice → identifiable via chargeback cause code → **serves as our promo-calendar proxy.**
- **Hold PO:** salesperson locks inventory in SalesPad for an in-progress deal, no time limit.
- **Planogram:** literal shelf map decided in annual category reviews.
- **MOQ:** supplier's Minimum Order Quantity.

## The Three Stated Data Issues
1. **Lost sales are invisible.** Partial fills cancel the unmet demand from the record. Backorder feature unusable because big retailers (Walmart) won't accept them. Causes **death spiral**: low recorded sales → smaller reorders → more stockouts → even weaker signal.
2. **Markdown volume inflates apparent demand.** Blended revenue hides fire-sale clearance as "healthy demand." Buyer over-reorders dying products.
3. **Hold POs cherry-pick inventory.** Salespeople lock fresher stock for their customers; no time limit; others forced to sell short-dated → markdowns/waste. Inventory shows unavailable even when deals may never close.

## Inferred Problems (not stated)
- **No historical inventory snapshots.** Only today's snapshot. Past positions must be reconstructed by running sales + POs backward → noisy.
- **No clean promo calendar.** Must be inferred from TPR chargeback cause codes.
- **"Allocated" field polluted by stale holds.** "Available" is systematically understated.
- **Cold start** for new SKU variants (no history).
- **Lunar-calendar seasonality** shifts 3–4 weeks per year; standard models misalign.
- **Bullwhip effect** in Health Food channel — UNFI/KeHE orders amplify small consumer swings.
- **Cannibalization** between SKU variants (new flavor steals from old).
- **Customer-level lumpiness hidden by channel aggregation.**
- **MOQ + container economics force basket ordering** across SKUs from same supplier.
- **Salesperson quarter-end pushes** distort demand; look like real spikes.
- **Buyer long-tail neglect** — 200 SKUs each → low-revenue SKUs go unmanaged.
- **No forecast-accuracy feedback loop** — nobody measures if past forecasts were right.
- **Chargebacks as reverse signal** — short-ship chargebacks can be used to *find* historical lost-sale events.

## From the Delivery/Requirements Doc (what POP explicitly grades on)

### Required capabilities
- **Demand signal cleaning:** separate full-price from promo/markdown; estimate or flag lost demand.
- **Channel-aware analysis:** demand views per channel, not one-size-fits-all.
- **Reorder intelligence:** reorder-point alerts using inventory + lead times; optional draft POs.
- **Output & usability:** buyer-consumable format; **show raw vs cleaned signal**; **clearly mark assumptions**.

### Suggested 5-layer architecture (use as our skeleton)
1. **Data ingestion** — load CSVs (sales, inventory, POs, supplier master, chargebacks).
2. **Demand cleaning** — TPR-based promo flagging; stockout/lost-demand flagging.
3. **Channel segmentation** — don't force one model across all channels.
4. **Reorder logic** — inventory vs run rate vs lead time; alert (+ optional draft PO).
5. **Presentation** — dashboard or report: cleaned demand, alerts, recommendations.

### 5 presentation deliverables (6–8 min talk)
1. How we cleaned demand signal (promo separation + lost-sales estimation).
2. Channel-level analysis showing pattern differences.
3. Reorder alerting logic + draft PO output.
4. **Before/after comparison of raw vs cleaned demand for 2–3 specific SKUs.**
5. Key assumptions, limitations, lessons learned.

### Team role split (POP's suggestion)
- **Data & Pipeline:** CSV ingestion, joins, gap handling.
- **Analytics & Logic:** demand separation, lost-sales estimation, reorder math, channel segmentation.
- **Frontend & Presentation:** dashboard/report, before/after comparisons, draft PO output.

## Data Inputs Provided
- Sales transaction history (Jan 2023–Dec 2025, anonymized)
- Current inventory snapshot (today only — must reconstruct history)
- PO history + Open POs
- Supplier master (MOQ, lead time, country, port)
- Chargeback/deduction data (TPR codes = promo proxy)
- SKU master (pack size, shelf life, supplier)

## Student Must Research
- CPG forecast accuracy benchmarks
- Safety stock formulas for variable lead times
- Ocean freight transit times from Asian ports

## Why "Easy Fixes" Are Hard
- Fixes require changing human behavior, salesperson commissions, customer contracts, or third-party software with no API.
- Solution must work ON TOP of exported data, not require ERP changes.
- Buyer stays in control: **review-and-approve**, never auto-execute.
