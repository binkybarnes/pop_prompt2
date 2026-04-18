# Problem 1 — Feature Tree (MoSCoW + Layer + Risk)

Every feature is tagged with:
- **Priority:** MUST / SHOULD / COULD / WON'T
- **Layer:** which of POP's 5 layers it lives in (1=Ingest, 2=Clean, 3=Channel, 4=Reorder, 5=Present)
- **Demo value:** what judges see

```
POP Problem 1 Solution
│
├── FEATURES (what we build)
│   │
│   ├── [MUST] MVP Core — these must all work or we fail
│   │   │
│   │   ├── F0. CSV ingestion pipeline                      [Layer 1]
│   │   │    └─ Load sales, inventory, POs, open POs, supplier, chargebacks, SKU master
│   │   │       - joins everything on SKU / customer / date
│   │   │       - handles missing fields, date parsing
│   │   │       demo: "we loaded 3 years × 1000 SKUs cleanly"
│   │   │
│   │   ├── F1. Promo/markdown separation  ✅ DONE           [Layer 2]
│   │   │    └─ Use TPR cause codes from chargebacks to flag promo weeks per SKU per customer
│   │   │       - split each SKU's sales into "organic" vs "promo"
│   │   │       - outputs two demand numbers per SKU
│   │   │       - implemented in exploration_f1.ipynb cells 11–12:
│   │   │         `promo_cal` (Customer×Brand×YearMonth) + `tag_sales()` adds
│   │   │         `is_promo`, `is_markdown`, `is_clean_demand` columns
│   │   │       demo: SKU X reports $50k revenue → really $25k organic + $25k promo
│   │   │
│   │   ├── F2. Lost-sales / suppressed-demand detector     [Layer 2]
│   │   │    └─ Find SKU-days where inventory hit zero mid-period or shipments < typical orders
│   │   │       - estimate lost units (customer's normal pattern − actual shipped)
│   │   │       - use chargeback "short-ship" cause codes as corroboration
│   │   │       demo: "in 2024 we detect ~$XXXk of unrecorded demand"
│   │   │
│   │   ├── F3. Channel-aware demand view                   [Layer 3]
│   │   │    └─ Run F1+F2 outputs separately per channel (American / Health Food / Asian / eCom)
│   │   │       - per-channel run rate, variance, seasonality flag
│   │   │       demo: same SKU across channels → 4 different demand curves
│   │   │
│   │   ├── F4. Reorder alert per SKU per DC                [Layer 4]
│   │   │    └─ On-hand − allocated − (run_rate × lead_time) < safety_stock → flag
│   │   │       - subtract open POs from "need to order"
│   │   │       - uses cleaned demand from F1/F2/F3
│   │   │       demo: weekly Excel with 20 flagged SKUs + recommended qty
│   │   │
│   │   └── F5. Before/after comparison view                [Layer 5]
│   │        └─ Pick 2–3 showcase SKUs. Side-by-side:
│   │           - raw demand chart vs cleaned demand chart
│   │           - show the delta in recommended reorder qty
│   │           demo: THE money slide. Judges remember this.
│   │
│   ├── [SHOULD] Differentiators — big uplift if time allows
│   │   │
│   │   ├── F6. Assumption transparency layer               [Layer 5]
│   │   │    └─ Every number in output has a provenance tag:
│   │   │       - "estimated" vs "measured"
│   │   │       - confidence score or assumption note
│   │   │       demo: hover/footnote on each alert shows "assumed lead time = 45 days
│   │   │         (median of 2024 POs for this supplier)"
│   │   │
│   │   ├── F7. Backtesting / ROI proof                     [Layer 5]
│   │   │    └─ Replay 2024 with our system; compare to actual reorders
│   │   │       - count stockouts avoided, markdown overreorders prevented
│   │   │       demo: "if POP used this in 2024, Y stockouts avoided, $Z saved"
│   │   │
│   │   ├── F8. Lunar-calendar seasonality module           [Layer 3]
│   │   │    └─ Overlay Lunar NY, Mid-Autumn, etc. as date-shifting holidays
│   │   │       - for Asian Market SKUs, adjust run rate around these dates
│   │   │       demo: show spike correctly anticipated for 2025 Lunar NY
│   │   │
│   │   ├── F9. Stale hold-PO detector                      [Layer 2]
│   │   │    └─ Flag allocated-inventory records older than N days
│   │   │       - treat that inventory as likely-available in reorder math
│   │   │       demo: "$XXk of inventory is held on stale POs; we surface it"
│   │   │
│   │   └── F13. Price–demand curve per SKU                  [Layer 2 / 5]
│   │        └─ Per SKU, plot unit price (X) vs units sold (Y) across all invoices;
│   │           fit/interpolate a curve (e.g. isotonic or log-log regression)
│   │           - visually separates organic demand at full price from promo-lift
│   │             spikes at lower prices — richer than F1's binary flag
│   │           - read "organic baseline" off the curve at the SKU's list price;
│   │             cross-check vs F1's clean-demand run rate
│   │           - becomes a judge-friendly visual proof that F1 is working
│   │           demo: Tiger Balm Patch — at $3.50 curve says ~400 cases/mo, at
│   │             $2.00 promo spikes to ~900; reorder math uses the $3.50 point
│   │
│   ├── [COULD] Stretch — only if core + differentiators are solid
│   │   │
│   │   ├── F10. Product-family forecasting                 [Layer 2/3]
│   │   │     └─ Forecast Ginger Chew family total, split by historical mix
│   │   │        - handles new SKU cold-start and cannibalization
│   │   │
│   │   ├── F11. Quarter-end push detector                  [Layer 2]
│   │   │     └─ Flag demand spikes near quarter-ends in Asian Market
│   │   │        → discount them as artificial in forecast
│   │   │
│   │   └── F12. Draft PO generator with MOQ basket         [Layer 4]
│   │         └─ When SKU X needs reorder, bundle other SKUs from same supplier
│   │            to hit MOQ / fill container
│   │
│   └── [WON'T] Out of scope for hackathon
│       ├── Live ERP integration (no API at POP)
│       ├── Full bullwhip modeling for Health Food
│       ├── Full OTIF/chargeback reconciliation (that's P3)
│       └── Supplier performance scoring
│
└── RISKS / CONSTRAINTS (things that shape HOW we build)
    │
    ├── [HIGH] Data risks
    │   ├── R1. No historical inventory snapshots
    │   │      → Must reconstruct by running sales + POs backward from today
    │   │      → Mitigation: use PO receipt dates as anchor points; accept noise;
    │   │        DOCUMENT the reconstruction method as a listed assumption
    │   ├── R2. "Allocated" includes stale hold-POs
    │   │      → "Available" is systematically understated
    │   │      → Mitigation: age allocations; treat >30-day holds as likely-real-inventory
    │   ├── R3. No clean promo calendar
    │   │      → Must infer from TPR cause codes
    │   │      → Mitigation: make TPR-flag → promo-period a documented rule
    │   └── R4. Health Food end-retailer demand invisible
    │          → Seen through UNFI/KeHE (distributor) orders, bullwhip-distorted
    │          → Mitigation: flag this channel's signal as lower-confidence
    │
    ├── [HIGH] Adoption / format risks
    │   ├── R5. Must ingest & output CSV/Excel only
    │   │      → No fancy live dashboards; no API assumptions
    │   │      → Mitigation: pipeline reads CSV, outputs xlsx (openpyxl etc.)
    │   └── R6. Buyers must stay in control (review-and-approve)
    │          → Not auto-execute
    │          → Mitigation: all outputs are suggestions with reasoning attached (F6)
    │
    ├── [MEDIUM] Model risks
    │   ├── R7. Lunar-calendar shifts break standard seasonality
    │   ├── R8. Cold-start for new SKU variants (no history)
    │   ├── R9. Low-data SKUs (long-tail) can't support fancy models → fall back to rules
    │   └── R10. Defining "lost sale" requires a threshold — arbitrary, defend in slide
    │
    └── [LOW] Business / org risks
        ├── R11. Salespeople may resist hold-PO transparency (demo angle: we just surface it)
        └── R12. Chargeback post-audit lag 8–12 mo (affects P3, not directly P1)
```

---

## Build order (48 hr hackathon)

| Hour | Features | Notes |
|---|---|---|
| 0–6 | F0 (ingest) | Nothing else works without this; get it rock solid |
| 6–14 | F1 (promo split) | Most mechanical; gives visible output early |
| 14–22 | F2 (lost sales) | The "wow" insight |
| 22–28 | F3 (channel split) | Layer F1+F2 by channel |
| 28–34 | F4 (reorder alert) | Ties it all into a buyer-usable output |
| 34–40 | F5 (before/after) + F6 (assumption tags) | Presentation-critical |
| 40–44 | Pick ONE: F7 (backtesting) / F8 (lunar) / F9 (stale holds) | Go with strongest data signal |
| 44–48 | Slide deck + demo polish + kill broken stuff | |

**Rule:** if F0–F5 aren't solid by hour 36, CUT everything below and polish what works. A working MVP beats an ambitious half-done build.
