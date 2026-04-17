# POP Hackathon — Problem 3 (Inventory & Fulfillment Execution)

*Note: POP calls this Problem 3 internally; it was the 2nd prompt we studied.*

## The Core Pain
- Company-level inventory can look healthy (3 months of supply) while being badly imbalanced across the 3 DCs. One DC overstocked, others empty.
- Aggregate numbers lie. Planning must be **per DC**, not per company.

## The Cascading Penalty Scenario
Customer order hits an empty/short DC →
1. Order splits across 2 DCs → **2 picks, 2 shipments, double labor + freight.**
2. Partial shipment arrives first → **short-ship chargeback** (hundreds of $).
3. Second half arrives late → **late-delivery / missed-window chargeback.**
4. Net result: **~$300+ in penalties on a $100 product.**
- Even if POP ships on time, **third-party carrier** arriving early/late triggers penalties POP eats.
- Annual chargeback/deduction exposure: **~$700k total**; shipment/delivery penalties in the **low six figures**, concentrated in certain channels/accounts.

## OTIF (On Time, In Full)
- A **numeric score** retailers track per supplier.
- Low OTIF → less shelf space, smaller orders, potential delisting.
- A $500 penalty today can cost $50k in lost future orders.
- Why POP sometimes transfers even when freight wipes out margin: **avoiding OTIF damage > short-term freight cost.**

## The Transfer-vs-Wait Decision (Ops Manager's Dilemma)
When imbalance is spotted, choose between:
- **Transfer** from a stocked DC (costs freight)
- **Wait** for an inbound PO (risks stockout)

Factors weighed (manually today):
- Freight cost per route (inter-DC)
- Inbound shipment ETA + known delays
- FDA hold status on inbound containers
- Stockout risk at the needy DC
- OTIF / chargeback risk at the customer
- Shelf life of the product being transferred

**No existing tool combines these inputs.** Today = spreadsheets + gut feel.

## The Post-Audit Chargeback Trap
- Many chargebacks arrive as **post-audit adjustments 8–12 months later.**
- By then: no reconstruction of events, no paper trail, can't dispute → POP eats the loss.
- **Solution implication:** log every decision + inventory state as it happens so disputes have evidence.

## Reactive vs Proactive
- Today: **reactive exception reporting** — find out after the penalty.
- Goal: **proactive positioning** — alert before the problem ("DC-C stockouts in 6 days, transfer now vs. wait for PO arriving in 10 days").

## Key Vocabulary
- **Pallet:** wooden platform stacked with cases; standard unit for domestic truck/warehouse moves. **Freight is priced per pallet**, so units/pallet determines transfer efficiency.
- **Container:** 20/40ft steel ocean-shipping container. Priced per container → incentive to fill them fully.
- **Container optimization:** packing SKUs into containers to maximize fill + strategic mix.
- **Port allocation:** inbound containers land at different US ports (LA/LB, Oakland, NY/NJ). Each port is closer to a different DC. Deciding which port → which DC per container based on need.
- **Inter-DC transfer:** moving inventory between POP DCs (not supplier → DC).
- **FDA hold:** inbound goods held by FDA for inspection; delays arrival.
- **Chargeback / deduction:** retailer penalty fee, netted against POP's invoices.
- **MOQ:** supplier's Minimum Order Quantity (unrelated to pallets).

## Solution Pitch (Problem 3)
Ingest per-DC inventory, sales, open POs, transfer history, freight costs, and chargeback data. Produce a daily ops dashboard with:
1. **Early-warning stockout alerts** — per SKU per DC, N days ahead.
2. **Transfer-vs-wait recommendations** — compares freight cost, PO ETA, OTIF risk; outputs a recommended action with dollar tradeoff.
3. **Port-to-DC routing suggestions** — for inbound containers in transit, recommend destination DC based on projected need.
4. **Decision audit log** — every recommendation + action logged for chargeback dispute evidence 8–12 months later.

## Why Logging Recommendations Matters
- Feedback loop: prove ROI ("buyers who followed rec had X% fewer penalties").
- Dispute evidence for post-audit chargebacks.
- Tuning data for improving the model.

## Data Inputs Provided
- Current inventory snapshot (per SKU per DC; today only)
- Sales transaction history (Jan 2023–Dec 2025)
- Inter-DC transfer history (freight cost, reason)
- PO history + Open POs (port of entry, DC destination, delays/holds)
- Chargeback data (cause codes including TPRs)
- **Freight cost estimates (Excel):** per pallet, inter-DC routes + outbound to major regions
- Supplier master (country, port of origin, lead time, MOQ)
- SKU master (pack size, shelf life, units/case, **units/pallet**)

## Student Must Research
- OTIF benchmarks at major retailers
- CPG chargeback structures / penalty rates
- Ocean freight transit variability + port congestion patterns

## Problem 2 vs Problem 3 — Strategic Pick
- **Problem 2** recommended for hackathon:
  - More room for creative ML/analytics (lost-sales inference, markdown separation, channel-aware forecasting).
  - Problem 3 is constrained by ops logistics — harder to demo in 48 hours.
  - P2 outputs feed P3; nailing P2 lets you add a light P3 extension as a bonus.
- Doing both fully → both end up shallow. Commit to P2, gesture at P3.
