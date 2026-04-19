 No, I didn't make the test yet — I asked if you wanted me to, and you didn't say yes.

  How the model "predicts the future" (basic version):

  It's not ML. It's a statistical estimator on recent history. Three numbers drive
  everything:

1. run_rate_wk = average weekly demand. "Next week will probably look like the last 26
   weeks."
2. lead_time_wk = median time between past POs placed and received. "The vendor takes ~13
   weeks."
3. safety_stock = buffer sized from how noisy past demand and lead time have been. Z ×
   √(LT·σ_d² + d²·σ_LT²). Bigger noise → bigger buffer.

  Two decisions come out of those three numbers:

  When to order (the threshold you remembered):
  reorder_point = run_rate × lead_time + safety_stock
                  ↑ expected demand      ↑ cushion for
                    during lead time       surprises
  Fire an order when on_hand + inflight < reorder_point.

  How much to order (the part you're asking about):
  suggested_qty = max(0, reorder_point + forward_cover × run_rate − available_now)
                          ↑ get back above threshold    ↑ subtract what
                            plus 6 more weeks of buffer   you already have
  Then round up to case pack and cap by MOQ.

  Concrete example — Tiger Balm T-32206 at SF DC:

- run_rate = 8,413/wk, lead_time = 13 wk, SS = 51,273
- ROP = 8,413 × 13 + 51,273 ≈ 160,642
- If on_hand is 30,000 (below ROP), order: 160,642 + 6 × 8,413 − 30,000 ≈ 181,120 units →
  round up to nearest case pack.

  So "predicting the future" is just: assume the next lead-time window of demand will look
  statistically like the past year, then order enough to cover that window plus a safety
  cushion plus a forward buffer. The 10c trend-aware and empirical-p99 stuff changes how we
   estimate run_rate and SS — not the overall shape.

  Want me to build the forecast-accuracy test now? (I can add it as a new cell in
  10_backtest.ipynb that computes WMAPE + bias for run_rate_wk vs actual forward outflow
  across all 3,544 as-of rows.)

❯ those 3 numbers, are they calculated on all the past, or is it a window? in the
  simulation does it calculate on the past, produce a signal, then go to the next week
  repeat?

⏺ Let me check the actual window scope in the code to answer precisely.

⏺ Bash(conda run -n 3.11mamba python -c "
      import re…)
  ⎿  === compute_dc_stats (excerpt) ===
     def compute_dc_stats(
         weekly: pd.DataFrame,
     … +20 lines (ctrl+o to expand)

⏺ Bash(conda run -n 3.11mamba python -c "
      import json…)
  ⎿  === cell 22 (simulate_followed) ===
     # Build actual weekly outflow per (SKU, DC) from raw sales — signed (net of retur
     ns).
     … +29 lines (ctrl+o to expand)

⏺ Bash(conda run -n 3.11mamba python -c "
      import json…)
  ⎿  r_qty = po_schedule.pop(w, 0.0)
             on_hand += po_arr_qty
             out = float(outflow.get(w, 0.0))
     … +23 lines (ctrl+o to expand)

⏺ Bash(git -C /Users/johnpork/repos/pop_prompt2 show 5a67a11 --stat 2>&1 | head -10
      echo '---'…)
  ⎿  commit 5a67a117b3ba84119207431e5fd39762a3df0257
     Author: binkybarnes <cottonjohn2000@gmail.com>
     Date:   Sat Apr 18 14:15:56 2026 -0700
     … +29 lines (ctrl+o to expand)

⏺ Great question — the answer is nuanced. Two different timescales:

1. The 3 numbers use an EXPANDING window (all past data up to as-of date).

  Not a rolling window — not "last N weeks." At each as-of week, alerts_as_of filters
  weekly[week_start < as_of_week] then takes the mean/std over everything from
  start-of-history to that as-of. Same for lead time: median of all POs received before
  as-of.

  So on 2023-04-03 the window is ~3 months of history. By 2025-10-13 it's ~2.5 years. The
  window grows.

  (Exception: my 10c trend-aware policy switches to last 26 weeks for declining-regime
  lanes. Everywhere else = all past.)

2. The sim has TWO clocks running:

  ┌────────────┬─────────────────────────────────────────┬─────────────────────────────┐
  │   clock    │              what happens               │           cadence           │
  ├────────────┼─────────────────────────────────────────┼─────────────────────────────┤
  │ policy     │ recompute run_rate / SS / ROP / LT from │ every 4 weeks (the as-of    │
  │ refresh    │  expanded history                       │ walk-forward step)          │
  ├────────────┼─────────────────────────────────────────┼─────────────────────────────┤
  │ sim tick   │ subtract outflow, add arrivals, check   │ every 1 week                │
  │            │ inv_pos < ROP, fire order if so         │                             │
  └────────────┴─────────────────────────────────────────┴─────────────────────────────┘

  Between refreshes, the sim carries forward the most recent policy values. That's what
  commit 5a67a11 fixed — before, checks only fired on the 4-weekly as-of dates, and stock
  would drain silently in between.

  So the loop looks like:

  Week 0 (as_of): recompute rop/rr/ss/lt from all past data → policy A
  Week 1:   on_hand -= outflow; check inv_pos < policy_A.rop? fire if yes
  Week 2:   on_hand -= outflow; check inv_pos < policy_A.rop? fire if yes
  Week 3:   on_hand -= outflow; check inv_pos < policy_A.rop? fire if yes
  Week 4 (as_of): recompute from past (now 4 wks more data) → policy B
  Week 5:   on_hand -= outflow; check inv_pos < policy_B.rop? fire if yes
  ...

  When a PO fires at week w, it schedules po_schedule[w + lead_time_wk] += qty — arrivals
  land at that future week and get added to on_hand when the sim clock reaches it.

  Your mental model was right. At every as-of: compute-policy → check-signal → repeat 4
  weeks later with more data. The nuance is that inside the 4-week gap, the signal still
  gets checked weekly (using the most recent policy), so a lane can fire multiple POs
  between refreshes if demand surges.
