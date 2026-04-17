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