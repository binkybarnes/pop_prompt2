"How do people normally decide how much to order?"

The manual process at POP today is basically:

1. Buyer opens an Excel export of recent sales
2. Eyeballs last few months — "we sold ~500 cases/month"
3. Checks current inventory — "we have 400 cases left"
4. Thinks: "lead time is 90 days from China, so I need ~1,500 cases in transit... I should order soon"
5. Places a PO manually

The problems with that:

- Step 2 includes promo months → inflates the baseline → they over-order
- Step 2 misses stockout months → deflates the baseline → they under-order
- Step 4 is done from memory/rules of thumb, not a formula
- There's no alert — the buyer has to remember to check 1,000 SKUs

What we're building replaces steps 2-4 with math:

clean weekly run rate  =  avg units/week (clean demand only, F1+F2)
reorder point trigger  =  run_rate × lead_time_weeks + safety_stock
"order now" alert      =  current available stock < reorder point
suggested qty          =  (run_rate × replenishment_cycle) - available + safety_stock

The buyer still makes the final call — but instead of doing mental math across 1,000 SKUs, they open one Excel file that
already says "Tiger Balm Patch: ORDER NOW, suggested 480 cases."




Linking tprs based on brand and customer id


⏺ How the brand link works in Cell 11/12 — and yes, it's approximate

  The flow:

1. Chargebacks: tpr rows have (Customer Number, brand, promo_ym) extracted → that's
   promo_cal (637 rows).
2. Sales: in tag_sales, every invoice row gets brand extracted from ITEMDESC and ym from
   DOCDATE.
3. Merge: left-join sales onto promo_cal on (CUSTNMBR, brand, ym). Match → is_promo=True.

  Where it can be wrong (you're right to ask):

- Sub-brand bleed (false positives): TPR was on Tiger Balm Patch, but Tiger Balm Ultra
  sold to the same customer that month also gets flagged. Fix would be to extract sub-brand
  (TBP/TBU/TBR) on both sides — possible but more work.
- Month is too coarse: A 1-week TPR ends up flagging the entire month's sales of that
  brand.
- Brand string ambiguity: "ginger chew" catches POP Ginger Chews + POP Ginger Chews Plus

+ Ginger Honey Crystals if they share the substring.

- No SKU on chargebacks: there's no way to be more precise without scraping SKU numbers
  from the description text (the T-22010 example in the unknown prefixes is exactly such a
  row).

  For the hackathon this is acceptable — bias is toward over-flagging promos, which is
  conservative (cleans more demand than necessary, slightly underestimates organic). Worth
  noting in the slide as a known limitation.
