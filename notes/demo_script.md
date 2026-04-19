# Demo Script — POP Reorder Alert System

**Elevator pitch (one sentence):** We replaced a buyer reading 800 SKU rows in Excel with a dashboard that tells you exactly what to order, how much, and shows you the math behind every recommendation — including where it would have been wrong.

**Setup before you start:**

- Open the app to `/alerts`
- Have T-32206-SF (Tiger Balm Patch Small, SF DC) ready to click into
- Know your one real number: POP holds ~$2M in excess inventory across lanes the model says are fine to hold

---

## Scene 1 — The Triage Screen (`/alerts`)

**What you're showing:** 233 lanes, 197 flagged as needing attention today. Without this, a buyer scrolls through all 233 in GP.

**What to point at:**

- **Summary strip at the top** — "197 reorder alerts / 54 high-confidence / 17 medium." High-confidence means we had real PO history to calibrate lead time. Medium means we fell back to a pooled cross-DC estimate. Point out the split so they see you're not blending everything together.
- **Filter to DC = NJ or SF** — show that the view is slice-able. A buyer owns one DC; they don't care about the others.
- **Sparkline column** — the tiny on-hand trend per row. A sparkline draining to zero is why the flag fired. You can see the signal without clicking in.
- **Confidence badge** — say it out loud: "if you see 'low confidence', treat that as a flag for human review, not an order recommendation."

**Anticipated question:** *"How do I know this isn't just flagging everything?"*

> Point to the 36 lanes with no flag. The model saw high on-hand relative to reorder point and stayed quiet. If it flagged everything, that column wouldn't exist.

---

## Scene 2 — Lane Drill-Down: T-32206-SF (Tiger Balm Patch Small, SF)

**Why this lane:** 153 weeks of clean data, lead time from real PO receipts (not a default), two channels, and it had a real stockout in May 2023. This is your proof-of-concept lane.

**What to point at on the Operational Prediction Chart:**

- **The "Today" Line and Burn-Down Projection** — Show how the system takes actual physical inventory today and projects the downward burn rate into the future so you visually see when you will hit zero.
- **May 2023 dip (in the Diagnostics tab)** — Show the historical backtest where on-hand went negative (-1,495 units). The alert fired the week before (May 1). Say: "The model saw this coming a week early. That's the lead-of-warning metric — median 12 weeks across all backtested lanes."

**"Under the Hood" (The 3 Crucial Numbers):**
If a stakeholder asks exactly how the model works, point to `src/reorder.py` and explain the 3 exact numbers that drive the prediction:

1. **The Run Rate:** We use a dynamic **Trend-Aware Regime Detector**. We compute a `Ratio = (Recent 26-wk Mean) / (Full History Mean)`.
   - If `Ratio < 0.70` (declining) or `Ratio > 1.30` (growing), `Run Rate = Recent 26-wk Mean`.
   - Otherwise, `Run Rate = Full History Mean`.
   - *Why this matters:* It drops historical baggage instantly when trends shift, preventing over-ordering on dead stock or stockouts on new best-sellers.
2. **The Safety Stock:** We use a rigorous dual-variance formula: `SS = Z × √(LT·σ_d² + d²·σ_LT²)`.
   - It captures BOTH demand volatility (`σ_d`) and lead-time volatility (`σ_LT`). Single-source formulas fail when Chinese POs vary between 3 to 9 weeks in transit.
   - The `Z` score is tiered by ABC/XYZ classes. Best-sellers (AX) get `Z=1.96` (97.5% service level) to protect revenue, while slow unreliables (CZ) get squeezed down to `Z=1.04` to eliminate wasted working capital.
3. **The Reorder Point:** The final trigger is simply: `(Run Rate × Lead Time in weeks) + Safety Stock`. Once your active `on_hand` drops below this threshold, the red alert fires.

**Trust signal to name explicitly:**

> "The lead time in this lane — 2.9 weeks — came from 7 actual PO receipts in our history, not a category default. You can see the source: `po_history`. If it said `default`, I'd tell you to verify it yourself before placing an order."

**Anticipated question:** *"What if your on-hand numbers are wrong? GP data is messy."*

> "Fair. The model reads from the same GP export you use. It does not know about inventory adjustments made inside the warehouse that weren't entered into GP — that's a known gap. What it does know: if the sparkline shows a drain to zero and then a flat line, that's almost always a stockout, not a data entry error. We validated that by cross-checking against PO receipt dates."

---

## Scene 3 — The Counterfactual (Strategy Tab)

**What you're showing:** "What would have happened to T-32206-SF if you had followed this policy for the past 2 years?"

**What to point at:**

- **Blue line = simulated on-hand under policy.** It never goes below zero for T-32206-SF over 131 backtested weeks.
- **Grey line = what actually happened.** It hit zero in May 2023.
- **Delta card** — "Following this policy, ending inventory would be +X units higher and you would have avoided the May 2023 stockout."

**Key framing:** This is not a promise about the future. It's a proof that the policy would have worked on data the model never saw during calibration — because the walk-forward backtest rolls forward week by week, using only what a buyer would have known at that moment.

**Anticipated question:** *"You tuned the model to look good on this lane. Of course it works on T-32206."*

> "The backtest ran on 116 lanes simultaneously. 103 of 116 stayed above zero under the policy. 13 dipped. We know which 13 and why — mostly lumpy, bursty demand lanes where a single-week spike (17× the run rate in one case) outpaced any reasonable safety stock. We didn't hide those; they're in the risk report."

---

## Scene 4 — Showing an Honest Failure (F-04001-NJ)

**Why include this:** Every model that only shows wins is a lie. Showing a known failure and explaining it builds more trust than hiding it.

**Navigate to F-04001-NJ (POP Ginger, NJ DC).**

**What to say:**

> "This is one of our 13 regression lanes. The sim dips to −22k at one point even though actual stock was fine. The reason: F-04001 NJ has burst weeks where demand is 17× the weekly run rate — a single Costco-style order. Our safety stock formula handles variance, but not individual spikes that large. The fix we'd implement next is an empirical percentile buffer instead of the analytic formula for lanes flagged as bursty. We know the problem; we're not pretending it doesn't exist."

**What this shows the judge/customer:** You understand your model's failure modes. That's what distinguishes a real tool from a demo.

---

## Scene 5 — Confidence Tiers (Back to the List)

**Filter to `confidence = low`.** Walk through what low confidence means:

- Fewer than ~13 weeks of clean demand history, OR
- Lead time came from `default` (13 weeks — a category fallback, not a real measurement), OR
- No PO receipt history to validate against

**What to say:**

> "Low confidence rows are still shown because a buyer should know they exist — but the suggested order quantity has wide error bars. Think of it as: 'we see something concerning, please verify before acting.' Medium and high confidence are the ones you can act on directly."

**Anticipated question:** *"Can the model be gamed? What if someone enters bad data into GP?"*

> "Yes, garbage in, garbage out — same as your current Excel process. The difference is: bad data is visible here. If a lane shows 'default' lead time and a suspiciously high suggested quantity, you know to check the PO history. In the current process, a bad formula cell is invisible."

---

## Scene 6 — The Ask / So What

**What this replaces:**

- Buyer manually scanning 233 rows in GP every week: ~3–4 hours
- Zero lead-of-warning (buyer sees stockout when it happens, not 12 weeks before)
- No audit trail for why an order was placed or skipped

**What this adds:**

- 12-week median lead-of-warning (time to actually call the vendor and negotiate)
- Per-lane confidence so buyers know when to trust vs. verify
- Counterfactual "what would have happened" — a built-in check against buyer intuition
- Capital efficiency: C-tier items (CZ tier) carry lower safety stock because demand is low and variable — no reason to hold 6 weeks of cover for a $200/week SKU

---

## Q&A Playbook

| Question                                                            | Answer                                                                                                                                                                                           |
| ------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| "How do you know your demand numbers aren't inflated by promos?"    | "We stripped promo-inflated weeks before calibrating. A TPR (Temporary Price Reduction) sale does not count toward the baseline run rate. Clean demand is a separate column from total outflow." |
| "What if we have a new SKU with no history?"                        | "Low or no confidence. The model says so. You order based on your vendor MOQ and buyer experience — same as today."                                                                             |
| "Does this account for seasonality?"                                | "Run rate recalculates on a rolling trailing window, so it does pick up seasonal patterns implicitly. Explicit lunar/seasonal overlay is planned but not in this build."                         |
| "What if inventory gets counted wrong in a cycle count?"            | "The model reads the GP snapshot. A recount that gets entered into GP will update the next week's on-hand number automatically. One bad snapshot = one bad alert week."                          |
| "Why is suggested quantity so high for lane X?"                     | "Check the lead time source. If it says 'default' (13 weeks), the formula is sizing for a longer lead time than may be real. Confirm actual lead time with the vendor and re-run."               |
| "Can we trust the backtest? You could have picked favorable lanes." | "The backtest ran on all 116 high-confidence lanes. We can show the full 116-row risk table. 103 stayed above zero, 13 dipped. The 13 are documented with root cause."                           |

---

## Timing Guide

| Segment                        | Time  |
| ------------------------------ | ----- |
| Elevator pitch + list view     | 2 min |
| T-32206-SF chart + trust story | 3 min |
| Counterfactual / Strategy tab  | 2 min |
| Honest failure (F-04001-NJ)    | 1 min |
| Confidence tiers               | 1 min |
| The ask                        | 1 min |
| Q&A                            | open  |

**Total demo time: ~10 minutes before Q&A.**
