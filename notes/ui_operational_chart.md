# Feature Spec: Operational UI Chart (Forward-Looking)

**To: Claude (Frontend Implementation)**

**Context:**
Currently, our `LaneChartPanel` and `MainChart` render a 34-week historical backtest of inventory levels and reorder points. This causes a mental model mismatch, as users interpret the "Lane Detail" page as an operational tool to predict *when* they will run out of stock in the future, rather than an evaluation of historical policy performance.

We need to build a new `OperationalChart` component that acts as the primary "Today" view for a given lane.

## Data & Visualization Requirements

The Operation Chart must bridge current state and future projection. It should render:

1. **The "Today" Line (Vertical Axis Marker)**
   - A distinct vertical line or shaded zone separating the past (actuals) from the future (predictions).
   - "Today" is defined by the `as_of_week` of the latest inventory snapshot.

2. **Current Inventory Point**
   - The verified `on_hand` count as of the snapshot date.

3. **The "Burn Down" Projection (Dotted Line)**
   - A descending slope originating from Current Inventory and projecting into the future.
   - The negative slope of this line is determined by the model's `run_rate_wk` (the forecasted demand rate).
   - The line shows visually when inventory is projected to cross the Reorder Point and ultimately hit zero (Stockout Date).

4. **Strategic Thresholds (Horizontal Lines)**
   - **Reorder Point (ROP):** Drawn as a relatively firm horizontal warning threshold.
   - **Safety Stock (SS):** Drawn as the absolute bottom limit horizontal floor, representing emergency buffer.

5. **Action Overlays (Suggested POs)**
   - If the current inventory is below the Reorder Point (meaning `reorder_flag` acts as True), immediately overlay an incoming PO arrival.
   - This should visually "bump" the inventory line back up by the `suggested_qty` at `Today + lead_time_wk` (the expected delivery week).

## User Experience Note
The goal is for a planner to glance at the chart and instantly see:
> "If I don't order today, my inventory line hits zero in 3 weeks. If I order today, the PO arrives in 2 weeks and I avoid dropping into my safety stock."

The existing `MainChart` / `BacktestTab` should be preserved but clearly sequestered to a "Diagnostics" or "Policy Evaluation" context, not the primary Operational entry point.
