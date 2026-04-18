● Walkthrough of what each cell says, in plain English.

  Cell 5 — "What did we load?"

  inv_snap : (219, 5)     DCs=['LA','NJ','SF']
  sales    : (236,818, 23)  LOCNCODEs=['1','2','3','E1','L','U','W','ZD']
  po       : (5,281, 16)    Location Codes=[1,2,3]
  transfers: (4,843, 12)    statuses={'Posted': 4843}
  73 SKUs × 3 DCs = 219 inventory rows. 236k sales lines. 5.3k PO receipts. 4.8k internal transfer
  moves — all "Posted" (actually happened, not drafts). One surprise: sales has location codes 'L' and
  'U' I wasn't expecting — those are rare non-physical codes that get dropped in the next step.

  Cell 7 — "Do the rewind"

  sales phys : 234,639 / 236,818 (99.1%)   dropped 2,179 e-comm/return rows
  anchor (today)  : 2026-04-13
  rewind start    : 2023-01-02
  rewind end      : 2026-04-20  (one Monday past today's week)
  week count      : 173
  inv_weekly: (37,887, 5)     unique (SKU, DC): 219
  confidence breakdown:  high: 188   low: 31
  - We kept 99.1% of sales after filtering to physical DCs (the 2,179 dropped are Shopify/Weee/returns
  — they don't affect DC inventory).
  - "Today" = 2026-04-13 (the most recent sales invoice in the data).
  - We go back 173 weeks to Jan 2, 2023.
  - Final artifact: 37,887 rows (219 series × 173 weeks).
  - 188 of 219 series (86%) are high confidence. The other 31 (14%) have data gaps we can't explain.

  Cell 9 — "Validation"

  today_rewind vs snapshot: max |diff| = 0.000   identity check: PASS
  The rewind at "next Monday" exactly equals today's snapshot. This proves the math is self-consistent
  — we're not losing or gaining inventory in the bookkeeping.

  min_on_hand_est distribution:
    25th pct : +463
    median   : +3,832
    75th pct : +25,594
    min      : −3,046,361  ← worst case
  Translation: the typical SKU-DC series never dips below +463 units (good). But some series dip
  catastrophically — one went 3 million units negative. That's a SKU where sales over 3 years vastly
  exceed what we can account for via POs + transfers + today's stock.

    clean (min >= 0)               :  84.9%
    minor (0 > min >= −tolerance)  :   0.9%
    low-confidence (min < −tol)    :  14.2%
  85% of series never go negative at all. 14% go meaningfully negative → "low confidence" tag.

  T-32206 SF [low]: today=264,417  min=−1,307,293
  T-32206 NJ [low]: today=364,715  min=−3,046,361
  T-32206 LA [low]: today=144,207  min=  −639,183
  Bad news for our showcase SKU. Tiger Balm Patch is in the 14% low-confidence bucket across ALL 3 DCs.
   The rewind thinks SF was 1.3M patches in the hole in early 2023. That's not real — it means we're
  missing something (probably inbound POs that happened before 2023 that our data doesn't capture, or
  SKU renumbering). We should pick a different showcase SKU for the "before/after" demo slide, or show
  this as a teaching moment about data quality.

  duplicate (ITEMNMBR, DC, week_start): 0
  null on_hand_est: 865
  No duplicates (good). 865 nulls = ~5 SKU-DC combos have no On Hand value in the snapshot file, so
  their rewind is all-NaN. Acceptable — we'll handle them downstream.

  ---
  The two graphs

  Graph 1 — "Rewind noise histogram"
  - What's on it: one dot-worth-of-bar per SKU-DC series. The bar's position = "how far negative did
  this series dip, as a percent of today's stock?"
  - How to read it: the mountain on the right side (near 0% and +100%) = healthy series that stay
  reasonable. The long tail going left past the red dashed line (-10%) = series with unexplained
  inventory gaps.
  - What we want to see: most mass on the right, small tail on the left. That's what we got — 85%
  clean, ~15% problematic.

  Graph 2 — "T-32206 across 3 DCs over time"
  - What's on it: three wiggly lines (SF, NJ, LA), each showing estimated inventory week-by-week from
  2023 to today.
  - How to read it: think of it like "if I could press rewind on the warehouse, how much stock was
  there each Monday?" The red dashed line at 0 is the physical floor — you can't have negative
  inventory in real life.
  - What's happening here: all three lines plunge deep below 0 in early 2023, then climb back up to
  today's stock. The dip = math running out of room when we try to subtract 3 years of sales without
  enough counterbalancing PO receipts on record. For this specific SKU, we probably don't have POs that
   far back (or they're under a different SKU code).

  Bottom line

  The rewind works for 85% of SKUs. For the remaining 15% — including our current showcase SKU — we'll
  rely on the confidence flag to skip them in F1 rather than pretend to know. Want me to hunt for a
  better showcase SKU (one with confidence='high' across all DCs AND ≥1000 sales lines AND TPR
  activity) before we move on?