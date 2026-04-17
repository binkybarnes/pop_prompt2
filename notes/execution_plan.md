# Problem 1 — Execution Plan

The *how* and *when*. Read `prompt1_notes.md` for context and `feature_tree.md` for full feature details.

## Target outcome (one sentence)
A CSV-in / Excel-out tool that takes POP's raw sales, inventory, PO, and chargeback files and produces: (1) cleaned demand per SKU per channel, (2) lost-sales estimates, (3) weekly reorder alerts with draft POs, with every number tagged as *measured* or *estimated*.

## The 5-layer architecture (POP's own skeleton)

| Layer | Purpose | Our features | Files in/out |
|---|---|---|---|
| **1. Ingest** | Load and join CSVs | F0 | Raw CSVs → typed dataframes |
| **2. Clean** | Strip promo, estimate lost demand, age holds | F1, F2, F9 (+F10/F11 stretch) | dataframes → `cleaned_demand.parquet` |
| **3. Segment** | Per-channel views, seasonality | F3, F8 | cleaned → `channel_demand.parquet` |
| **4. Reorder** | Alerts + draft POs | F4, F12 | channel_demand + inventory → `reorder_alerts.xlsx` |
| **5. Present** | Buyer-readable report, before/after, assumptions | F5, F6, F7 | → `buyer_report.xlsx` + slides |

Keep each layer in its own Python module. Layer N only reads Layer N-1's output. This lets three people work in parallel.

## The 5 presentation deliverables (drive everything back to these)

| # | Deliverable | Feature | Demo artifact |
|---|---|---|---|
| 1 | How demand signal was cleaned | F1 + F2 | Chart: raw vs cleaned for 1 SKU |
| 2 | Channel-level demand analysis | F3 (+F8) | 4 mini-charts, 1 per channel |
| 3 | Reorder alerting + draft PO | F4 (+F12) | Excel screenshot w/ 10 alerts |
| 4 | **Before/after for 2–3 SKUs** | F5 | Side-by-side: raw reorder qty vs cleaned reorder qty |
| 5 | Assumptions, limitations, lessons | F6 | One slide + footnotes throughout |

**Deliverable #4 is the money slide.** Reverse-plan from it: pick the 2–3 SKUs EARLY (ideally end of Day 1) so you can stress-test the whole pipeline on them.

## Team role split (3 tracks, run in parallel)

### Track A — Data & Pipeline (owns Layer 1, supports 2)
- CSV schemas, date/type cleanup, key joins (SKU / customer / channel / DC / date)
- Inventory reconstruction from today + sales + POs (risk R1)
- Unit tests on joins so downstream folks trust the data

### Track B — Analytics & Logic (owns Layers 2, 3, 4)
- F1: TPR-based promo period flagging
- F2: lost-sales detection (stockout events + shipped < normal)
- F3: per-channel aggregation & run rate
- F4: reorder math (on-hand − allocated − run_rate × lead_time < safety_stock)
- Stretch: F8 Lunar overlay, F10 family forecast, F12 basket PO

### Track C — Frontend & Presentation (owns Layer 5)
- Output formatter: Excel with conditional formatting, sheets per channel, top sheet = buyer summary
- F5: before/after SKU comparison views (picks 2–3 SKUs, builds the money slide)
- F6: assumption tags (every number has a provenance note)
- F7: backtesting harness (replays 2024, outputs ROI numbers)
- Pitch deck (6–8 min, 5 deliverables structured)

**Glue:** decide intermediate file formats (parquet or CSV) Day 1 morning. A and B agree on sales_clean schema; B and C agree on alerts schema. Contracts > collaboration.

## 2-day schedule (adapt hours for your start time)

### Day 1 — Data mastery + cleaning
**Morning (4h)**
- All: 45 min reading the actual data files, noting quirks
- All: decide intermediate file schemas; commit a `schemas.md`
- Pick the 2–3 showcase SKUs (must span ≥2 channels for the demo)
- A: CSV ingest skeleton; B: explore TPR cause codes; C: Excel output skeleton

**Afternoon (4h)**
- A: finish F0 joins; reconstruction of past inventory working for showcase SKUs
- B: F1 promo separation; first per-SKU cleaned-demand numbers
- C: first draft Excel output

**Evening (3h)**
- B: F2 lost-sales detector (the hardest logic; give it a block of uninterrupted time)
- A: clean up edge cases A+B found during afternoon
- C: before/after chart template; build it once so B can hand data in later

### Day 2 — Integration, reorder, demo
**Morning (4h)**
- B: F3 channel-aware views; F4 reorder alert logic
- C: integrate F1+F2+F3 outputs into Excel report
- A: performance (run full 3-year dataset in <2 min)

**Afternoon (4h)**
- C: F5 before/after (finalize the money slide), F6 assumption tags
- B: pick ONE of F7/F8/F9 based on what data is clean; build just that one
- A: full pipeline end-to-end run; fix last bugs

**Evening (3h)**
- All: pitch deck, dry run (target 6 min, have 8)
- Cut any feature that's flaky for the demo
- Back up everything; bring spare laptop

## Hard rules
1. **Commit to scope at hour 36.** No new features after that; only polish + cut.
2. **Every number in output has a provenance tag.** Either it's measured from raw data, or it's a flagged assumption. No silent defaults.
3. **Demo runs on pre-computed outputs.** Don't run the pipeline live on stage; pre-generate the Excel the night before.
4. **Showcase SKUs picked Day 1.** The whole pipeline gets validated against them before we worry about full-dataset scale.
5. **One person owns the pitch deck** by Day 2 noon. Don't collaboratively edit slides in panic.

## Key assumptions to document (don't skip, judges love honesty)
- Past inventory reconstruction from sales + POs is approximate (no adjustments data).
- Promo periods inferred from TPR chargeback codes only; non-TPR promos invisible.
- Lost-sales estimate uses rule: "customer's 90-day avg order vs actual ship quantity when inventory reached zero."
- Lead time = median of 2024 supplier POs (or whatever we choose; note it).
- Safety stock = X weeks of cleaned run rate (or industry formula; note it).
- Health Food channel signal is bullwhip-distorted; confidence lower.

## Anti-patterns to avoid
- Spending Day 1 on a beautiful dashboard with no analytics.
- Building for all 1000 SKUs before the showcase SKUs work end-to-end.
- Chasing F7/F8/F9/F10/F11/F12 before F1–F5 are solid.
- Auto-generating reorder POs without a human-review column.
- Glossy ML models hiding assumptions; judges will ask and you'll stumble.
- Live pipeline runs during demo.
