# Reorder Alert UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a static Next.js prototype that presents F1 reorder alerts as a Linear-style list and a TradingView-style per-lane drilldown, driven entirely by pre-committed JSON artifacts produced by the existing pipeline notebooks.

**Architecture:** Two-tab Next.js app (App Router, TypeScript strict, static export). Data contract is JSON files in `ui/data/` written by new final cells in `pipeline/09_reorder_alerts.ipynb` and `pipeline/10_backtest.ipynb`. No server, no auth, no tests. Lane grain is `(SKU × DC)`; 107 lanes total, 3 showcase lanes (`T-32206-SF`, `T-32206-NJ`, `F-04111-NJ`) get authored counterfactual narratives.

**Tech Stack:** Next.js 15 App Router · React 19 · TypeScript strict · Tailwind CSS · Recharts · pandas / pyarrow (pipeline side). Python env is `mamba run -n 3.11mamba`.

**Source spec:** [`docs/superpowers/specs/2026-04-18-reorder-alert-ui-design.md`](../specs/2026-04-18-reorder-alert-ui-design.md)

**Validation model (not TDD):** The design spec puts tests out of scope. Each task uses runtime validation: running the pipeline notebook to verify JSON shape, then running `npm run dev` and loading a route in a browser to verify rendering. Commits happen after each task passes its runtime check.

---

## Phase A — Pipeline JSON emitters

Goal: add final cells to notebooks 09 and 10 that dump the exact JSON contract the UI consumes. Cells are idempotent (overwrite files) so re-running notebook 10 refreshes everything.

---

### Task 1: Create `ui/data/` directory + update gitignore

**Files:**
- Create: `ui/data/.gitkeep`
- Modify: `.gitignore` (already modified in brainstorm commit `df82bea` — verify only)

- [ ] **Step 1: Create directories**

```bash
mkdir -p ui/data/lane
touch ui/data/.gitkeep
```

- [ ] **Step 2: Verify .gitignore has UI build paths but NOT ui/data**

Run: `grep -n "^ui/" .gitignore`
Expected output (order may vary):
```
ui/node_modules/
ui/.next/
ui/out/
```

If `ui/data/` is in `.gitignore`, remove it — the data folder is deliberately committed.

- [ ] **Step 3: Commit**

```bash
git add ui/data/.gitkeep
git commit -m "chore: create ui/data scaffold for UI JSON artifacts"
```

---

### Task 2: Add final cell to `pipeline/09_reorder_alerts.ipynb` — dump `alerts_today.json`

**Files:**
- Modify: `pipeline/09_reorder_alerts.ipynb` (append a new markdown + code cell pair at the end)

The cell must produce a JSON array where each row matches one row of `reorder_alerts.parquet`, augmented with a 26-week `on_hand_sparkline` trailing window (most recent 26 weekly `on_hand_est` values from the inventory rewind).

- [ ] **Step 1: Read existing notebook structure to find the insertion point**

Use `NotebookEdit` in "insert" mode at the end of the notebook.

- [ ] **Step 2: Append a markdown cell**

Cell type: `markdown`, content:

```markdown
## 7. Export to UI

Dump this notebook's artifact as `ui/data/alerts_today.json` for the reorder-alert UI. Embeds a 26-week `on_hand_sparkline` per row so the List view can render inline sparklines without a separate fetch.
```

- [ ] **Step 3: Append a code cell**

Cell type: `code`, content:

```python
import json
from pathlib import Path
import pandas as pd

UI_DATA = Path('../ui/data')
UI_DATA.mkdir(parents=True, exist_ok=True)

inv_weekly = pd.read_parquet('artifacts/inv_weekly.parquet')

SPARK_WEEKS = 26
latest = inv_weekly['week_start'].max()
cutoff = latest - pd.Timedelta(weeks=SPARK_WEEKS - 1)
spark_src = (
    inv_weekly[inv_weekly['week_start'] >= cutoff]
    .sort_values(['ITEMNMBR', 'DC', 'week_start'])
    .groupby(['ITEMNMBR', 'DC'])['on_hand_est']
    .apply(lambda s: [None if pd.isna(v) else float(v) for v in s.tolist()])
    .rename('on_hand_sparkline')
    .reset_index()
)

out = reorder_alerts.merge(spark_src, on=['ITEMNMBR', 'DC'], how='left')
out['on_hand_sparkline'] = out['on_hand_sparkline'].apply(
    lambda v: v if isinstance(v, list) else []
)

payload = out.replace({pd.NA: None}).where(pd.notna(out), None).to_dict(orient='records')
for row in payload:
    for k, v in list(row.items()):
        if isinstance(v, float) and (v != v):
            row[k] = None

(UI_DATA / 'alerts_today.json').write_text(json.dumps(payload, default=str))
print(f"wrote {len(payload)} rows to {UI_DATA / 'alerts_today.json'}")
```

- [ ] **Step 4: Run the cell and verify**

Run the cell in the kernel. Expected output:
```
wrote 233 rows to ../ui/data/alerts_today.json
```

Then validate:
```bash
mamba run -n 3.11mamba python -c "
import json; d = json.load(open('ui/data/alerts_today.json'))
print(len(d), 'rows')
print('first row keys:', sorted(d[0].keys())[:10])
print('spark len:', len(d[0]['on_hand_sparkline']))
assert len(d) == 233
assert all('on_hand_sparkline' in r for r in d)
print('OK')
"
```
Expected: `233 rows`, `OK`.

- [ ] **Step 5: Commit**

```bash
git add pipeline/09_reorder_alerts.ipynb ui/data/alerts_today.json
git commit -m "feat(pipeline): dump alerts_today.json for UI from step 09"
```

---

### Task 3: Add final cell to `pipeline/10_backtest.ipynb` — dump `lanes_index.json` + `backtest_summary.json`

**Files:**
- Modify: `pipeline/10_backtest.ipynb` (append cells)

- [ ] **Step 1: Append markdown cell**

```markdown
## Export to UI

Dump lane summary index and aggregate backtest summary for the UI.
```

- [ ] **Step 2: Append code cell — `lanes_index.json`**

```python
import json
from pathlib import Path

UI_DATA = Path('../ui/data')
UI_DATA.mkdir(parents=True, exist_ok=True)

# Load the per-lane scoring from this notebook's outputs
per_lane = pd.read_parquet('artifacts/backtest_per_lane.parquet')

# Pull today-flag + description from step 09's output for the same lanes
reorder = pd.read_parquet('artifacts/reorder_alerts.parquet')

today_flag = reorder.set_index(['ITEMNMBR', 'DC'])[
    ['reorder_flag', 'confidence', 'inv_description']
].to_dict(orient='index')

# brand from the brand-tagged sales (for display)
sku_brand = pd.read_parquet('artifacts/sku_brand.parquet').set_index('ITEMNMBR')['brand'].to_dict()

rows = []
for _, r in per_lane.iterrows():
    key = (r['ITEMNMBR'], r['DC'])
    today = today_flag.get(key, {})
    rows.append({
        'sku': r['ITEMNMBR'],
        'dc': r['DC'],
        'sku_desc': today.get('inv_description') or '',
        'brand': sku_brand.get(r['ITEMNMBR']) or '',
        'fresh_rate': float(r['n_fresh']) / float(r['n_weeks']) if r['n_weeks'] else 0.0,
        'n_weeks': int(r['n_weeks']),
        'n_alerts': int(r['n_alerts']),
        'n_fresh': int(r['n_fresh']),
        'today_flag': bool(today.get('reorder_flag', False)),
        'today_confidence': today.get('confidence') or 'low',
    })

(UI_DATA / 'lanes_index.json').write_text(json.dumps(rows, default=str))
print(f"wrote {len(rows)} lanes to lanes_index.json")
```

- [ ] **Step 3: Append code cell — `backtest_summary.json`**

```python
# Aggregate summary: take from backtest_compare.parquet (mean vs p90 scoring)
cmp = pd.read_parquet('artifacts/backtest_compare.parquet')

summary = {
    'strategies': cmp.to_dict(orient='records'),
    'total_lanes': int(len(per_lane)),
    'total_alerts_today': int(reorder['reorder_flag'].sum()),
    'total_alerts_high_conf': int(
        (reorder['reorder_flag'] & (reorder['confidence'] == 'high')).sum()
    ),
    'total_alerts_med_conf': int(
        (reorder['reorder_flag'] & (reorder['confidence'] == 'medium')).sum()
    ),
    'total_alerts_low_conf': int(
        (reorder['reorder_flag'] & (reorder['confidence'] == 'low')).sum()
    ),
}
(UI_DATA / 'backtest_summary.json').write_text(json.dumps(summary, default=str))
print('wrote backtest_summary.json')
```

- [ ] **Step 4: Run both cells and verify**

Expected: `wrote 107 lanes to lanes_index.json` then `wrote backtest_summary.json`.

Validate:
```bash
mamba run -n 3.11mamba python -c "
import json
idx = json.load(open('ui/data/lanes_index.json'))
summ = json.load(open('ui/data/backtest_summary.json'))
assert len(idx) == 107, f'expected 107 lanes, got {len(idx)}'
assert 'strategies' in summ and len(summ['strategies']) == 2
print('OK — 107 lanes,', summ['total_alerts_today'], 'alerts today')
"
```

- [ ] **Step 5: Commit**

```bash
git add pipeline/10_backtest.ipynb ui/data/lanes_index.json ui/data/backtest_summary.json
git commit -m "feat(pipeline): dump lanes_index and backtest_summary JSON for UI"
```

---

### Task 4: Add cell to `pipeline/10_backtest.ipynb` — dump per-lane `lane/{slug}.json`

**Files:**
- Modify: `pipeline/10_backtest.ipynb` (append cell)

- [ ] **Step 1: Append code cell**

```python
# Per-lane time-series file. One file per (SKU, DC) lane.
alerts_wf = pd.read_parquet('artifacts/backtest_alerts.parquet')
inv_weekly = pd.read_parquet('artifacts/inv_weekly.parquet')
item_master = pd.read_parquet('artifacts/item_master.parquet')

LANE_DIR = UI_DATA / 'lane'
LANE_DIR.mkdir(exist_ok=True)

# Some backtest rows include both mean and p90 variants; pivot so each
# (sku, dc, as_of_week) has mean + p90 side-by-side.
key_cols = ['ITEMNMBR', 'DC', 'as_of_week']
value_cols = ['reorder_point', 'run_rate_wk', 'reorder_flag']

wf_mean = alerts_wf[alerts_wf['strategy'] == 'mean'].set_index(key_cols)[value_cols]
wf_p90  = alerts_wf[alerts_wf['strategy'] == 'p90' ].set_index(key_cols)[value_cols]
wf = wf_mean.join(wf_p90, lsuffix='_mean', rsuffix='_p90').reset_index()

# Merge inv + stockout ground truth
gt = alerts_wf[alerts_wf['strategy'] == 'mean'][
    key_cols + ['inv_at_asof', 'fresh_stockout', 'weeks_until_stockout']
]
wf = wf.merge(gt, on=key_cols, how='left')

im = item_master.set_index('Item Number')

# Lookup today's recommendation from step 09
reorder = pd.read_parquet('artifacts/reorder_alerts.parquet')
today_by_lane = reorder.set_index(['ITEMNMBR', 'DC']).to_dict(orient='index')

lanes_written = 0
for (sku, dc), group in wf.groupby(['ITEMNMBR', 'DC']):
    group = group.sort_values('as_of_week')
    today = today_by_lane.get((sku, dc), {})
    im_row = im.loc[sku] if sku in im.index else None

    series = []
    for _, r in group.iterrows():
        series.append({
            'week_start': r['as_of_week'].strftime('%Y-%m-%d'),
            'on_hand_est': None if pd.isna(r['inv_at_asof']) else float(r['inv_at_asof']),
            'reorder_point_mean': None if pd.isna(r['reorder_point_mean']) else float(r['reorder_point_mean']),
            'reorder_point_p90':  None if pd.isna(r['reorder_point_p90'])  else float(r['reorder_point_p90']),
            'run_rate_mean':      None if pd.isna(r['run_rate_wk_mean'])   else float(r['run_rate_wk_mean']),
            'run_rate_p90':       None if pd.isna(r['run_rate_wk_p90'])    else float(r['run_rate_wk_p90']),
            'alert_fired_mean':   bool(r['reorder_flag_mean']) if pd.notna(r['reorder_flag_mean']) else False,
            'alert_fired_p90':    bool(r['reorder_flag_p90'])  if pd.notna(r['reorder_flag_p90'])  else False,
            'fresh_stockout':     bool(r['fresh_stockout']) if pd.notna(r['fresh_stockout']) else False,
            'weeks_until_stockout': None if pd.isna(r['weeks_until_stockout']) else float(r['weeks_until_stockout']),
        })

    def _f(k, default=None):
        if not today:
            return default
        v = today.get(k)
        return None if (isinstance(v, float) and v != v) else v

    payload = {
        'sku': sku,
        'dc': dc,
        'series': series,
        'today': {
            'reorder_flag': bool(_f('reorder_flag', False) or False),
            'confidence': _f('confidence', 'low'),
            'on_hand': _f('on_hand_now'),
            'available': _f('available_now'),
            'reorder_point': _f('reorder_point'),
            'run_rate_wk': _f('run_rate_wk'),
            'lead_time_wk': _f('lead_time_wk'),
            'lead_time_source': _f('lead_time_source'),
            'suggested_qty': _f('suggested_qty'),
            'suggested_cases': _f('suggested_cases'),
            'weeks_of_cover': _f('weeks_of_cover'),
            'safety_stock': _f('safety_stock'),
            'std_wk': _f('std_wk'),
            'n_clean_weeks': _f('n_clean_weeks'),
        },
        'metadata': {
            'sku_desc': (im_row.get('Description') if im_row is not None else None) or _f('inv_description') or '',
            'case_pack': _f('case_pack'),
            'vendor': (im_row.get('Maufactuer/ CoPacker') if im_row is not None else None) or '',
            'country': (im_row.get('Country of Origin') if im_row is not None else None) or '',
        },
    }

    slug = f"{sku}-{dc}"
    (LANE_DIR / f'{slug}.json').write_text(json.dumps(payload, default=str))
    lanes_written += 1

print(f"wrote {lanes_written} per-lane JSON files to {LANE_DIR}")
```

- [ ] **Step 2: Run cell and verify**

Expected: `wrote 107 per-lane JSON files to ../ui/data/lane`.

Validate:
```bash
mamba run -n 3.11mamba python -c "
import json, os
files = sorted(os.listdir('ui/data/lane'))
base = [f for f in files if not f.endswith('_demand.json') and not f.endswith('_counterfactual.json')]
assert len(base) == 107, f'expected 107, got {len(base)}'
d = json.load(open('ui/data/lane/T-32206-SF.json'))
assert len(d['series']) > 100, f'series too short: {len(d[\"series\"])}'
assert d['today']['reorder_point'] is not None
print('OK — first series row:', d['series'][0])
print('today:', d['today'])
"
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/10_backtest.ipynb ui/data/lane/
git commit -m "feat(pipeline): dump per-lane time-series JSON for UI lane view"
```

---

### Task 5: Add cell to `pipeline/10_backtest.ipynb` — dump `lane/{slug}_demand.json`

**Files:**
- Modify: `pipeline/10_backtest.ipynb` (append cell)

- [ ] **Step 1: Append code cell**

```python
# Per-lane demand breakdown by channel + top 5 customers.
clean = pd.read_parquet('artifacts/clean_demand_weekly.parquet')
tagged = pd.read_parquet('artifacts/sales_tagged_channel.parquet')

# Channel breakdown: weekly qty per (SKU, DC, SALESCHANNEL)
chan_weekly = (
    clean.groupby(['ITEMNMBR', 'DC', 'week_start', 'SALESCHANNEL'], as_index=False)['qty_base']
         .sum()
)

# Pivot so each row is (sku, dc, week) with MM/AM/HF columns
chan_wide = (
    chan_weekly.pivot_table(
        index=['ITEMNMBR', 'DC', 'week_start'],
        columns='SALESCHANNEL',
        values='qty_base',
        fill_value=0.0,
    )
    .reset_index()
)
for col in ['MM', 'AM', 'HF']:
    if col not in chan_wide.columns:
        chan_wide[col] = 0.0

# Top customers per lane from clean sales
cust_cols = ['ITEMNMBR', 'DC', 'CUSTNMBR', 'CUSTNAME']
have_cname = 'CUSTNAME' in tagged.columns
if not have_cname:
    tagged['CUSTNAME'] = ''
clean_cust = tagged[tagged.get('is_clean_demand', True) == True][cust_cols + ['QTY_BASE']].copy()
top_cust_by_lane = (
    clean_cust.groupby(['ITEMNMBR', 'DC', 'CUSTNMBR'], as_index=False)
              .agg(qty=('QTY_BASE', 'sum'),
                   name=('CUSTNAME', lambda s: s.dropna().iloc[0] if len(s.dropna()) else ''))
)

lanes_written = 0
for (sku, dc), lane_df in chan_wide.groupby(['ITEMNMBR', 'DC']):
    lane_df = lane_df.sort_values('week_start')
    weekly = [
        {
            'week_start': r['week_start'].strftime('%Y-%m-%d'),
            'MM': float(r['MM']),
            'AM': float(r['AM']),
            'HF': float(r['HF']),
        }
        for _, r in lane_df.iterrows()
    ]

    cust = top_cust_by_lane[
        (top_cust_by_lane['ITEMNMBR'] == sku) & (top_cust_by_lane['DC'] == dc)
    ].sort_values('qty', ascending=False).head(5)
    lane_total = cust['qty'].sum() or 1.0
    top_customers = [
        {
            'custnmbr': r['CUSTNMBR'],
            'name': r['name'] or r['CUSTNMBR'],
            'share_pct': float(r['qty'] / lane_total * 100.0),
            'qty': float(r['qty']),
        }
        for _, r in cust.iterrows()
    ]

    payload = {
        'sku': sku,
        'dc': dc,
        'weekly': weekly,
        'top_customers': top_customers,
    }
    slug = f"{sku}-{dc}"
    (LANE_DIR / f'{slug}_demand.json').write_text(json.dumps(payload, default=str))
    lanes_written += 1

print(f"wrote {lanes_written} demand-breakdown JSON files")
```

- [ ] **Step 2: Run cell and verify**

Expected: `wrote 107 demand-breakdown JSON files`.

Validate:
```bash
mamba run -n 3.11mamba python -c "
import json
d = json.load(open('ui/data/lane/T-32206-SF_demand.json'))
assert set(d['weekly'][0].keys()) == {'week_start', 'MM', 'AM', 'HF'}
assert len(d['top_customers']) <= 5
print('OK — top cust:', d['top_customers'][0] if d['top_customers'] else 'none')
"
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/10_backtest.ipynb ui/data/lane/
git commit -m "feat(pipeline): dump per-lane demand-breakdown JSON for UI"
```

---

### Task 6: Add cell to `pipeline/10_backtest.ipynb` — compute + dump counterfactual JSON

**Files:**
- Modify: `pipeline/10_backtest.ipynb` (append cell)

Counterfactual simulation: for each strategy (mean / p90), walk forward through the alert history. When an alert fires, schedule a simulated PO arrival `lead_time_wk` later, sized by `suggested_qty` at that moment. Apply all simulated arrivals as additive deltas to the actual `on_hand_est` trajectory.

- [ ] **Step 1: Append code cell — counterfactual simulator**

```python
# Counterfactual: "if POP had followed our alerts, what would inventory look like?"
# For each strategy, walk the alert history forward; when alert_fired True,
# schedule a simulated PO arrival lead_time_wk later for suggested_qty,
# then simulate the resulting on_hand trajectory by adding arrivals to actual.

def simulate_strategy(group, strategy_col, qty_col, lead_col):
    """Return dict {week_start_str: simulated_on_hand} and list of PO events."""
    group = group.sort_values('as_of_week').copy()
    pos = []
    arrivals = {}  # week_start (Timestamp) -> qty arriving
    for _, r in group.iterrows():
        if not r[strategy_col]:
            continue
        lead_wk = r[lead_col] if pd.notna(r[lead_col]) else 13.0
        arrival = r['as_of_week'] + pd.Timedelta(weeks=int(round(lead_wk)))
        qty = float(r[qty_col]) if pd.notna(r[qty_col]) else 0.0
        if qty <= 0:
            continue
        arrivals[arrival] = arrivals.get(arrival, 0.0) + qty
        pos.append({
            'order_week': r['as_of_week'].strftime('%Y-%m-%d'),
            'arrival_week': arrival.strftime('%Y-%m-%d'),
            'qty': qty,
        })

    # Build simulated trajectory: actual + cumulative arrivals
    trajectory = []
    cumulative_arrivals = 0.0
    for _, r in group.iterrows():
        wk = r['as_of_week']
        cumulative_arrivals += sum(v for k, v in arrivals.items() if k == wk)
        actual = r['inv_at_asof']
        sim = None if pd.isna(actual) else float(actual) + cumulative_arrivals
        trajectory.append((wk.strftime('%Y-%m-%d'), sim))
    return trajectory, pos

# Need suggested_qty at each as-of-week per strategy. Re-compute from
# reorder_point and run_rate (approximation: we re-derive it here).
FORWARD_COVER = 4
alerts_aug = alerts_wf.copy()
alerts_aug['suggested_qty_sim'] = (
    alerts_aug['reorder_point']
    + FORWARD_COVER * alerts_aug['run_rate_wk']
    - alerts_aug['inv_at_asof'].fillna(0)
).clip(lower=0)

lanes_written = 0
for (sku, dc), group_all in alerts_aug.groupby(['ITEMNMBR', 'DC']):
    group_mean = group_all[group_all['strategy'] == 'mean']
    group_p90  = group_all[group_all['strategy'] == 'p90']
    if len(group_mean) == 0:
        continue

    # "actual" is just inv_at_asof over time (taken from the mean rows,
    # since both strategies share ground truth)
    actual_traj = [
        (r['as_of_week'].strftime('%Y-%m-%d'),
         None if pd.isna(r['inv_at_asof']) else float(r['inv_at_asof']))
        for _, r in group_mean.sort_values('as_of_week').iterrows()
    ]

    mean_traj, mean_pos = simulate_strategy(
        group_mean, 'reorder_flag', 'suggested_qty_sim', 'lead_time_wk'
    ) if 'lead_time_wk' in group_mean.columns else ([], [])
    p90_traj, p90_pos = simulate_strategy(
        group_p90, 'reorder_flag', 'suggested_qty_sim', 'lead_time_wk'
    ) if 'lead_time_wk' in group_p90.columns else ([], [])

    # Pack into the time-series shape the UI expects
    by_week = {}
    for wk, v in actual_traj:
        by_week.setdefault(wk, {'week_start': wk, 'actual': None, 'mean_followed': None, 'p90_followed': None})
        by_week[wk]['actual'] = v
    for wk, v in mean_traj:
        by_week.setdefault(wk, {'week_start': wk, 'actual': None, 'mean_followed': None, 'p90_followed': None})
        by_week[wk]['mean_followed'] = v
    for wk, v in p90_traj:
        by_week.setdefault(wk, {'week_start': wk, 'actual': None, 'mean_followed': None, 'p90_followed': None})
        by_week[wk]['p90_followed'] = v
    series = sorted(by_week.values(), key=lambda r: r['week_start'])

    def _trough(values):
        vals = [v for v in values if v is not None]
        return float(min(vals)) if vals else None

    trough_delta = {
        'actual': _trough([r['actual'] for r in series]),
        'mean': _trough([r['mean_followed'] for r in series]),
        'p90': _trough([r['p90_followed'] for r in series]),
    }

    simulated_pos = (
        [dict(p, strategy='mean') for p in mean_pos]
        + [dict(p, strategy='p90') for p in p90_pos]
    )

    payload = {
        'sku': sku,
        'dc': dc,
        'series': series,
        'simulated_pos': simulated_pos,
        'trough_delta': trough_delta,
        'narrative': None,  # filled in Task 7 for showcase lanes
    }

    slug = f"{sku}-{dc}"
    (LANE_DIR / f'{slug}_counterfactual.json').write_text(json.dumps(payload, default=str))
    lanes_written += 1

print(f"wrote {lanes_written} counterfactual JSON files")
```

- [ ] **Step 2: Run cell and verify**

Expected: `wrote 107 counterfactual JSON files`.

Validate `T-32206-SF` has the expected trough improvement (actual much worse than p90):
```bash
mamba run -n 3.11mamba python -c "
import json
d = json.load(open('ui/data/lane/T-32206-SF_counterfactual.json'))
t = d['trough_delta']
print('actual:', t['actual'], ' mean:', t['mean'], ' p90:', t['p90'])
assert t['actual'] < 0, 'expected actual trough below zero'
assert t['p90'] > t['actual'], 'p90 should be less negative than actual'
print('num simulated POs:', len(d['simulated_pos']))
print('OK')
"
```
Expected output: `actual: -330...`, `p90: -212...` (approximately, from handoff doc).

- [ ] **Step 3: Commit**

```bash
git add pipeline/10_backtest.ipynb ui/data/lane/
git commit -m "feat(pipeline): simulate counterfactual trajectories for UI lane view"
```

---

### Task 7: Author narrative taglines for 3 showcase lanes

**Files:**
- Modify: `pipeline/10_backtest.ipynb` (append cell that overwrites narrative field for 3 showcase lanes)

- [ ] **Step 1: Append code cell**

```python
# Authored taglines for the 3 showcase lanes. Non-showcase lanes keep
# narrative=null and the UI falls back to computed numeric taglines.
SHOWCASE_NARRATIVE = {
    'T-32206-SF': {
        'actual_only': "T-32206 SF ran out of stock June 2023 — trough of −330k units.",
        'plus_mean':   "Mean-strategy would have flagged ~10 weeks earlier; trough reduced to −242k.",
        'plus_p90':    "P90 strategy would have prevented most of the dip. Trough reduced to −212k.",
    },
    'T-32206-NJ': {
        'actual_only': "T-32206 NJ is MM-dominant — 17.7k units/wk organic demand.",
        'plus_mean':   "Mean-strategy fires today at 18 wk cover; suggests 7,571 cases.",
        'plus_p90':    "P90 recommends the same order ~4 weeks earlier to absorb TPR spikes.",
    },
    'F-04111-NJ': {
        'actual_only': "F-04111 POP Ginger Chews Original — high elasticity (β = −4.26).",
        'plus_mean':   "Mean-strategy catches the post-promo rebound reliably.",
        'plus_p90':    "P90 widens safety stock for the elastic demand response.",
    },
}

for slug, narrative in SHOWCASE_NARRATIVE.items():
    path = LANE_DIR / f'{slug}_counterfactual.json'
    if not path.exists():
        print(f'MISSING: {path}')
        continue
    data = json.loads(path.read_text())
    data['narrative'] = narrative
    path.write_text(json.dumps(data, default=str))
    print(f'wrote narrative: {slug}')
```

- [ ] **Step 2: Run cell and verify**

Expected three `wrote narrative: <slug>` lines. Validate:
```bash
mamba run -n 3.11mamba python -c "
import json
d = json.load(open('ui/data/lane/T-32206-SF_counterfactual.json'))
assert d['narrative'] is not None
print('narrative keys:', list(d['narrative'].keys()))
print('plus_p90:', d['narrative']['plus_p90'])
"
```

- [ ] **Step 3: Commit**

```bash
git add pipeline/10_backtest.ipynb ui/data/lane/T-32206-SF_counterfactual.json ui/data/lane/T-32206-NJ_counterfactual.json ui/data/lane/F-04111-NJ_counterfactual.json
git commit -m "feat(pipeline): author narrative taglines for 3 showcase lanes"
```

---

## Phase B — UI scaffold

---

### Task 8: Initialize Next.js project in `ui/`

**Files:**
- Create: `ui/package.json`, `ui/tsconfig.json`, `ui/next.config.mjs`, `ui/tailwind.config.ts`, `ui/postcss.config.mjs`, `ui/app/globals.css`, `ui/app/layout.tsx`, `ui/app/page.tsx`, `ui/.gitignore`, `ui/README.md`

- [ ] **Step 1: Create package.json**

File: `ui/package.json`
```json
{
  "name": "pop-reorder-ui",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "lint": "next lint"
  },
  "dependencies": {
    "next": "15.0.3",
    "react": "19.0.0-rc-66855b96-20241106",
    "react-dom": "19.0.0-rc-66855b96-20241106",
    "recharts": "^2.13.3"
  },
  "devDependencies": {
    "@types/node": "^22.9.0",
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.15",
    "typescript": "^5.6.3"
  }
}
```

- [ ] **Step 2: Create tsconfig.json**

File: `ui/tsconfig.json`
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": false,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "paths": { "@/*": ["./*"] },
    "plugins": [{ "name": "next" }]
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}
```

- [ ] **Step 3: Create next.config.mjs (static export)**

File: `ui/next.config.mjs`
```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'export',
  images: { unoptimized: true },
  trailingSlash: true,
};

export default nextConfig;
```

- [ ] **Step 4: Create Tailwind config**

File: `ui/tailwind.config.ts`
```typescript
import type { Config } from 'tailwindcss';

const config: Config = {
  content: ['./app/**/*.{ts,tsx}', './components/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['ui-sans-serif', 'system-ui', '-apple-system', 'Segoe UI', 'sans-serif'],
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
      },
      colors: {
        bg: '#fafafa',
        surface: '#ffffff',
        border: '#e5e7eb',
        fg: '#111827',
        muted: '#6b7280',
        brand: '#1b2a4a',
        alert: '#dc2626',
        warn: '#f59e0b',
        ok: '#16a34a',
      },
    },
  },
  plugins: [],
};

export default config;
```

- [ ] **Step 5: Create postcss config**

File: `ui/postcss.config.mjs`
```javascript
export default {
  plugins: { tailwindcss: {}, autoprefixer: {} },
};
```

- [ ] **Step 6: Create globals.css**

File: `ui/app/globals.css`
```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body { background: #fafafa; color: #111827; }
body { font-feature-settings: 'tnum' 1, 'cv11' 1; }
```

- [ ] **Step 7: Create root layout**

File: `ui/app/layout.tsx`
```tsx
import type { Metadata } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'POP Reorder Intelligence',
  description: 'Hack the Coast 2026 — F1 reorder alert UI',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">{children}</body>
    </html>
  );
}
```

- [ ] **Step 8: Create root page (redirects to /alerts)**

File: `ui/app/page.tsx`
```tsx
import { redirect } from 'next/navigation';

export default function HomePage() {
  redirect('/alerts');
}
```

- [ ] **Step 9: Create ui-level .gitignore**

File: `ui/.gitignore`
```
node_modules/
.next/
out/
next-env.d.ts
*.tsbuildinfo
```

- [ ] **Step 10: Create ui/README.md**

File: `ui/README.md`
```markdown
# POP Reorder Intelligence UI

Static Next.js prototype on top of F1 reorder-alert data. See
`docs/superpowers/specs/2026-04-18-reorder-alert-ui-design.md` for the
design doc.

## Dev

```bash
cd ui
npm install
npm run dev
```

Open http://localhost:3000

## Build

```bash
npm run build
```

Outputs to `ui/out/` — deployable as static HTML.

## Data

All data lives in `ui/data/` as JSON, committed to the repo. It is produced
by `pipeline/09_reorder_alerts.ipynb` and `pipeline/10_backtest.ipynb`.
```

- [ ] **Step 11: Install deps**

```bash
cd ui && npm install 2>&1 | tail -5
```
Expected: installs without errors. `node_modules/` is created.

- [ ] **Step 12: Run dev server and smoke test**

```bash
cd ui && npm run dev &
```
Wait ~3 seconds, then:
```bash
curl -sS http://localhost:3000/ | grep -c "POP"
```
Expected: ≥1 (meta tag or redirect page contains "POP"). Kill the dev server: `kill %1`.

- [ ] **Step 13: Commit**

```bash
git add ui/package.json ui/package-lock.json ui/tsconfig.json ui/next.config.mjs ui/tailwind.config.ts ui/postcss.config.mjs ui/app/ ui/.gitignore ui/README.md
git commit -m "feat(ui): scaffold Next.js 15 + TS + Tailwind + Recharts project"
```

---

### Task 9: Build shell (TabBar + curves stub)

**Files:**
- Create: `ui/components/shell/TabBar.tsx`, `ui/app/alerts/layout.tsx`, `ui/app/curves/page.tsx`, `ui/app/alerts/page.tsx` (placeholder)

- [ ] **Step 1: Create TabBar component**

File: `ui/components/shell/TabBar.tsx`
```tsx
'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/alerts', label: 'Reorder Alerts' },
  { href: '/curves', label: 'Demand Curves' },
];

export function TabBar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-[1400px] items-center gap-8 px-6 py-3">
        <div className="text-sm font-semibold tracking-tight text-brand">
          POP Reorder Intelligence
        </div>
        <nav className="flex gap-1">
          {TABS.map((t) => {
            const active = pathname.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={
                  'rounded-md px-3 py-1.5 text-sm ' +
                  (active
                    ? 'bg-brand text-white'
                    : 'text-muted hover:bg-gray-100')
                }
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
```

- [ ] **Step 2: Create alerts layout (wraps /alerts and /alerts/lane in the shell)**

File: `ui/app/alerts/layout.tsx`
```tsx
import { TabBar } from '@/components/shell/TabBar';

export default function AlertsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TabBar />
      <main className="mx-auto max-w-[1400px] px-6 py-6">{children}</main>
    </>
  );
}
```

- [ ] **Step 3: Create curves stub page**

File: `ui/app/curves/page.tsx`
```tsx
import { TabBar } from '@/components/shell/TabBar';

export default function CurvesPage() {
  return (
    <>
      <TabBar />
      <main className="mx-auto max-w-[1400px] px-6 py-16 text-center">
        <h1 className="text-2xl font-semibold text-brand">Demand Curves</h1>
        <p className="mt-3 text-muted">
          Coming soon — F2 per-SKU × channel elasticity curves, scatter, and
          price predictor.
        </p>
      </main>
    </>
  );
}
```

- [ ] **Step 4: Create placeholder /alerts page**

File: `ui/app/alerts/page.tsx`
```tsx
export default function AlertsPage() {
  return <div className="text-muted">Alerts list coming in Task 10.</div>;
}
```

- [ ] **Step 5: Smoke test in browser**

```bash
cd ui && npm run dev &
```
Manually load http://localhost:3000/alerts and http://localhost:3000/curves in a browser. Both should render the tab bar; clicking tabs should switch between them without errors. Kill: `kill %1`.

- [ ] **Step 6: Commit**

```bash
git add ui/components/shell/ ui/app/alerts/ ui/app/curves/
git commit -m "feat(ui): shell with TabBar and curves stub"
```

---

### Task 10: TypeScript types + JSON loaders

**Files:**
- Create: `ui/lib/types.ts`, `ui/lib/data.ts`, `ui/lib/format.ts`

- [ ] **Step 1: Create `lib/types.ts`**

File: `ui/lib/types.ts`
```typescript
export type DC = 'SF' | 'NJ' | 'LA';
export type Confidence = 'high' | 'medium' | 'low';
export type Channel = 'MM' | 'AM' | 'HF';
export type Strategy = 'mean' | 'p90';

export interface AlertRow {
  ITEMNMBR: string;
  DC: DC;
  inv_description: string | null;
  available_now: number | null;
  on_hand_now: number | null;
  run_rate_wk: number | null;
  std_wk: number | null;
  n_clean_weeks: number | null;
  case_pack: number | null;
  lead_time_wk: number | null;
  lead_time_source: 'po_history' | 'parsed' | 'default' | null;
  safety_stock: number | null;
  reorder_point: number | null;
  weeks_of_cover: number | null;
  reorder_flag: boolean;
  suggested_qty: number | null;
  suggested_cases: number | null;
  confidence: Confidence;
  on_hand_sparkline: (number | null)[];
  [key: string]: unknown;
}

export interface LaneIndexRow {
  sku: string;
  dc: DC;
  sku_desc: string;
  brand: string;
  fresh_rate: number;
  n_weeks: number;
  n_alerts: number;
  n_fresh: number;
  today_flag: boolean;
  today_confidence: Confidence;
}

export interface LaneSeriesRow {
  week_start: string;
  on_hand_est: number | null;
  reorder_point_mean: number | null;
  reorder_point_p90: number | null;
  run_rate_mean: number | null;
  run_rate_p90: number | null;
  alert_fired_mean: boolean;
  alert_fired_p90: boolean;
  fresh_stockout: boolean;
  weeks_until_stockout: number | null;
}

export interface LaneToday {
  reorder_flag: boolean;
  confidence: Confidence;
  on_hand: number | null;
  available: number | null;
  reorder_point: number | null;
  run_rate_wk: number | null;
  lead_time_wk: number | null;
  lead_time_source: string | null;
  suggested_qty: number | null;
  suggested_cases: number | null;
  weeks_of_cover: number | null;
  safety_stock: number | null;
  std_wk: number | null;
  n_clean_weeks: number | null;
}

export interface LaneMetadata {
  sku_desc: string;
  case_pack: number | null;
  vendor: string;
  country: string;
}

export interface LaneFile {
  sku: string;
  dc: DC;
  series: LaneSeriesRow[];
  today: LaneToday;
  metadata: LaneMetadata;
}

export interface DemandWeek {
  week_start: string;
  MM: number;
  AM: number;
  HF: number;
}

export interface DemandCustomer {
  custnmbr: string;
  name: string;
  share_pct: number;
  qty: number;
}

export interface LaneDemandFile {
  sku: string;
  dc: DC;
  weekly: DemandWeek[];
  top_customers: DemandCustomer[];
}

export interface CounterfactualWeek {
  week_start: string;
  actual: number | null;
  mean_followed: number | null;
  p90_followed: number | null;
}

export interface SimulatedPO {
  strategy: Strategy;
  order_week: string;
  arrival_week: string;
  qty: number;
}

export interface NarrativeTaglines {
  actual_only: string;
  plus_mean: string;
  plus_p90: string;
}

export interface LaneCounterfactualFile {
  sku: string;
  dc: DC;
  series: CounterfactualWeek[];
  simulated_pos: SimulatedPO[];
  trough_delta: { actual: number | null; mean: number | null; p90: number | null };
  narrative: NarrativeTaglines | null;
}

export interface BacktestSummary {
  strategies: Array<Record<string, unknown>>;
  total_lanes: number;
  total_alerts_today: number;
  total_alerts_high_conf: number;
  total_alerts_med_conf: number;
  total_alerts_low_conf: number;
}
```

- [ ] **Step 2: Create `lib/data.ts`**

File: `ui/lib/data.ts`
```typescript
import { promises as fs } from 'node:fs';
import path from 'node:path';
import type {
  AlertRow,
  BacktestSummary,
  LaneCounterfactualFile,
  LaneDemandFile,
  LaneFile,
  LaneIndexRow,
} from './types';

const DATA_DIR = path.join(process.cwd(), 'data');

async function readJson<T>(relativePath: string): Promise<T> {
  const full = path.join(DATA_DIR, relativePath);
  const raw = await fs.readFile(full, 'utf-8');
  return JSON.parse(raw) as T;
}

export async function loadAlertsToday(): Promise<AlertRow[]> {
  return readJson<AlertRow[]>('alerts_today.json');
}

export async function loadLanesIndex(): Promise<LaneIndexRow[]> {
  return readJson<LaneIndexRow[]>('lanes_index.json');
}

export async function loadBacktestSummary(): Promise<BacktestSummary> {
  return readJson<BacktestSummary>('backtest_summary.json');
}

export async function loadLane(slug: string): Promise<LaneFile> {
  return readJson<LaneFile>(`lane/${slug}.json`);
}

export async function loadLaneDemand(slug: string): Promise<LaneDemandFile> {
  return readJson<LaneDemandFile>(`lane/${slug}_demand.json`);
}

export async function loadLaneCounterfactual(
  slug: string
): Promise<LaneCounterfactualFile> {
  return readJson<LaneCounterfactualFile>(`lane/${slug}_counterfactual.json`);
}

export async function listLaneSlugs(): Promise<string[]> {
  const files = await fs.readdir(path.join(DATA_DIR, 'lane'));
  return files
    .filter((f) => f.endsWith('.json') && !f.endsWith('_demand.json') && !f.endsWith('_counterfactual.json'))
    .map((f) => f.replace(/\.json$/, ''));
}
```

- [ ] **Step 3: Create `lib/format.ts`**

File: `ui/lib/format.ts`
```typescript
export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return Math.round(n).toLocaleString('en-US');
}

export function fmtFloat(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function fmtPct(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })}%`;
}

export function fmtWeeks(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${n.toLocaleString('en-US', { maximumFractionDigits: 0 })} wk`;
}

export function fmtCases(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${Math.round(n).toLocaleString('en-US')} cs`;
}

export function slugOf(sku: string, dc: string): string {
  return `${sku}-${dc}`;
}

export function parseSlug(slug: string): { sku: string; dc: string } {
  const idx = slug.lastIndexOf('-');
  return { sku: slug.slice(0, idx), dc: slug.slice(idx + 1) };
}
```

- [ ] **Step 4: Typecheck**

```bash
cd ui && npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add ui/lib/
git commit -m "feat(ui): TS types for data contract + JSON loader helpers"
```

---

## Phase C — List view

---

### Task 11: Basic alert table at `/alerts`

**Files:**
- Create: `ui/components/list/AlertTable.tsx`
- Modify: `ui/app/alerts/page.tsx`

- [ ] **Step 1: Replace `/alerts` page to load data and render table**

File: `ui/app/alerts/page.tsx`
```tsx
import { loadAlertsToday, loadBacktestSummary } from '@/lib/data';
import { AlertTable } from '@/components/list/AlertTable';
import { FilterChips } from '@/components/list/FilterChips';
import { SummaryStats } from '@/components/list/SummaryStats';

export default async function AlertsPage({
  searchParams,
}: {
  searchParams: Promise<{ dc?: string; confidence?: string; status?: string }>;
}) {
  const params = await searchParams;
  const dc = params.dc ?? 'all';
  const confidence = params.confidence ?? 'all';
  const status = params.status ?? 'flagged';

  const [rows, summary] = await Promise.all([
    loadAlertsToday(),
    loadBacktestSummary(),
  ]);

  return (
    <div className="space-y-4">
      <FilterChips dc={dc} confidence={confidence} status={status} />
      <SummaryStats rows={rows} dc={dc} confidence={confidence} status={status} summary={summary} />
      <AlertTable rows={rows} dc={dc} confidence={confidence} status={status} />
    </div>
  );
}
```

- [ ] **Step 2: Create AlertTable component**

File: `ui/components/list/AlertTable.tsx`
```tsx
'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { AlertRow } from '@/lib/types';
import { fmtCases, fmtInt, fmtWeeks, slugOf } from '@/lib/format';
import { Sparkline } from './Sparkline';

type SortKey = 'confidence' | 'weeks_of_cover' | 'suggested_qty' | 'ITEMNMBR' | 'DC';

const CONF_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

function applyFilters(
  rows: AlertRow[],
  dc: string,
  confidence: string,
  status: string
): AlertRow[] {
  return rows.filter((r) => {
    if (dc !== 'all' && r.DC !== dc) return false;
    if (confidence !== 'all' && r.confidence !== confidence) return false;
    if (status === 'flagged' && !r.reorder_flag) return false;
    if (status === 'not_flagged' && r.reorder_flag) return false;
    return true;
  });
}

export function AlertTable({
  rows,
  dc,
  confidence,
  status,
}: {
  rows: AlertRow[];
  dc: string;
  confidence: string;
  status: string;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('confidence');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const filtered = useMemo(
    () => applyFilters(rows, dc, confidence, status),
    [rows, dc, confidence, status]
  );
  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      let va: number | string = 0;
      let vb: number | string = 0;
      if (sortKey === 'confidence') {
        va = CONF_RANK[a.confidence] ?? 0;
        vb = CONF_RANK[b.confidence] ?? 0;
      } else if (sortKey === 'weeks_of_cover') {
        va = a.weeks_of_cover ?? Number.POSITIVE_INFINITY;
        vb = b.weeks_of_cover ?? Number.POSITIVE_INFINITY;
      } else if (sortKey === 'suggested_qty') {
        va = a.suggested_qty ?? 0;
        vb = b.suggested_qty ?? 0;
      } else if (sortKey === 'ITEMNMBR') {
        va = a.ITEMNMBR;
        vb = b.ITEMNMBR;
      } else if (sortKey === 'DC') {
        va = a.DC;
        vb = b.DC;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    if (sortKey === 'confidence') {
      copy.sort((a, b) => {
        const cmp = (CONF_RANK[b.confidence] ?? 0) - (CONF_RANK[a.confidence] ?? 0);
        if (cmp !== 0) return cmp;
        const wa = a.weeks_of_cover ?? Number.POSITIVE_INFINITY;
        const wb = b.weeks_of_cover ?? Number.POSITIVE_INFINITY;
        return wa - wb;
      });
    }
    return copy;
  }, [filtered, sortKey, sortDir]);

  function onSort(k: SortKey) {
    if (k === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(k);
      setSortDir(k === 'confidence' ? 'desc' : 'asc');
    }
  }

  if (sorted.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-6 text-center text-sm text-muted">
        No alerts match these filters.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wider text-muted">
          <tr>
            <Th onClick={() => onSort('ITEMNMBR')}>SKU</Th>
            <th className="px-3 py-2">Product</th>
            <Th onClick={() => onSort('DC')}>DC</Th>
            <th className="px-3 py-2 text-right">On hand</th>
            <Th onClick={() => onSort('weeks_of_cover')} align="right">Cover</Th>
            <Th onClick={() => onSort('suggested_qty')} align="right">Suggest</Th>
            <Th onClick={() => onSort('confidence')}>Conf</Th>
            <th className="px-3 py-2">Trend</th>
            <th className="px-3 py-2 text-center">Alert</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const slug = slugOf(r.ITEMNMBR, r.DC);
            return (
              <tr key={slug} className="border-t border-border hover:bg-gray-50">
                <td className="px-3 py-1.5 font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{r.ITEMNMBR}</Link>
                </td>
                <td className="px-3 py-1.5 text-muted">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    {r.inv_description ?? ''}
                  </Link>
                </td>
                <td className="px-3 py-1.5 font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{r.DC}</Link>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{fmtInt(r.on_hand_now)}</Link>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{fmtWeeks(r.weeks_of_cover)}</Link>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{fmtCases(r.suggested_cases)}</Link>
                </td>
                <td className="px-3 py-1.5">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    <ConfidenceBadge c={r.confidence} />
                  </Link>
                </td>
                <td className="px-3 py-1.5">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    <Sparkline values={r.on_hand_sparkline} />
                  </Link>
                </td>
                <td className="px-3 py-1.5 text-center">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    {r.reorder_flag ? <span className="text-alert">●</span> : <span className="text-muted">○</span>}
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({
  children,
  onClick,
  align = 'left',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  align?: 'left' | 'right';
}) {
  return (
    <th
      className={
        'px-3 py-2 ' + (align === 'right' ? 'text-right ' : '') +
        (onClick ? 'cursor-pointer select-none hover:text-fg' : '')
      }
      onClick={onClick}
    >
      {children}
    </th>
  );
}

function ConfidenceBadge({ c }: { c: string }) {
  const color =
    c === 'high' ? 'bg-ok/10 text-ok' :
    c === 'medium' ? 'bg-warn/10 text-warn' :
    'bg-gray-200 text-muted';
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${color}`}>{c}</span>
  );
}
```

- [ ] **Step 3: Create placeholder stubs for FilterChips, SummaryStats, Sparkline so the page compiles**

File: `ui/components/list/FilterChips.tsx`
```tsx
export function FilterChips(_: { dc: string; confidence: string; status: string }) {
  return <div className="h-9" />;
}
```

File: `ui/components/list/SummaryStats.tsx`
```tsx
import type { AlertRow, BacktestSummary } from '@/lib/types';
export function SummaryStats(_: {
  rows: AlertRow[];
  dc: string;
  confidence: string;
  status: string;
  summary: BacktestSummary;
}) {
  return null;
}
```

File: `ui/components/list/Sparkline.tsx`
```tsx
export function Sparkline(_: { values: (number | null)[] }) {
  return <span className="inline-block h-4 w-20 bg-gray-100" />;
}
```

- [ ] **Step 4: Smoke test**

```bash
cd ui && npm run dev &
```
Open http://localhost:3000/alerts in a browser. Expect a table with flagged rows (default filter). Click a row — it should navigate to `/alerts/lane/T-32206-NJ` (or similar) and 404 (we haven't built that route yet — expected). Kill: `kill %1`.

- [ ] **Step 5: Commit**

```bash
git add ui/components/list/ ui/app/alerts/page.tsx
git commit -m "feat(ui): alert table with sortable columns + row→lane link"
```

---

### Task 12: FilterChips with URL state

**Files:**
- Modify: `ui/components/list/FilterChips.tsx`

- [ ] **Step 1: Replace FilterChips stub**

File: `ui/components/list/FilterChips.tsx`
```tsx
'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

type ChipDef = { key: string; label: string; options: { value: string; label: string }[] };

const CHIPS: ChipDef[] = [
  {
    key: 'dc',
    label: 'DC',
    options: [
      { value: 'all', label: 'All' },
      { value: 'SF', label: 'SF' },
      { value: 'NJ', label: 'NJ' },
      { value: 'LA', label: 'LA' },
    ],
  },
  {
    key: 'confidence',
    label: 'Confidence',
    options: [
      { value: 'all', label: 'All' },
      { value: 'high', label: 'High' },
      { value: 'medium', label: 'Medium' },
      { value: 'low', label: 'Low' },
    ],
  },
  {
    key: 'status',
    label: 'Status',
    options: [
      { value: 'flagged', label: 'Flagged only' },
      { value: 'not_flagged', label: 'Not flagged' },
      { value: 'all', label: 'All' },
    ],
  },
];

export function FilterChips({
  dc,
  confidence,
  status,
}: {
  dc: string;
  confidence: string;
  status: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  const current: Record<string, string> = { dc, confidence, status };

  const update = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(sp.toString());
      const defaults: Record<string, string> = { dc: 'all', confidence: 'all', status: 'flagged' };
      if (value === defaults[key]) next.delete(key);
      else next.set(key, value);
      const qs = next.toString();
      router.push(qs ? `/alerts?${qs}` : '/alerts');
    },
    [router, sp]
  );

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {CHIPS.map((chip) => (
        <div key={chip.key} className="flex items-center gap-1">
          <span className="text-xs uppercase tracking-wider text-muted">{chip.label}</span>
          <div className="flex rounded-md border border-border bg-surface">
            {chip.options.map((opt) => {
              const active = current[chip.key] === opt.value;
              return (
                <button
                  key={opt.value}
                  onClick={() => update(chip.key, opt.value)}
                  className={
                    'px-2.5 py-1 text-xs first:rounded-l-md last:rounded-r-md ' +
                    (active ? 'bg-brand text-white' : 'hover:bg-gray-50')
                  }
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 2: Smoke test**

```bash
cd ui && npm run dev &
```
Open `/alerts`, click chips — URL updates to `?dc=NJ` etc., table re-renders. Default (no params) shows flagged only. Kill: `kill %1`.

- [ ] **Step 3: Commit**

```bash
git add ui/components/list/FilterChips.tsx
git commit -m "feat(ui): filter chips with URL query-param state"
```

---

### Task 13: SummaryStats row

**Files:**
- Modify: `ui/components/list/SummaryStats.tsx`

- [ ] **Step 1: Replace stub**

File: `ui/components/list/SummaryStats.tsx`
```tsx
import type { AlertRow, BacktestSummary } from '@/lib/types';

export function SummaryStats({
  rows,
  dc,
  confidence,
  status,
}: {
  rows: AlertRow[];
  dc: string;
  confidence: string;
  status: string;
  summary: BacktestSummary;
}) {
  const filtered = rows.filter((r) => {
    if (dc !== 'all' && r.DC !== dc) return false;
    if (confidence !== 'all' && r.confidence !== confidence) return false;
    if (status === 'flagged' && !r.reorder_flag) return false;
    if (status === 'not_flagged' && r.reorder_flag) return false;
    return true;
  });
  const flagged = filtered.filter((r) => r.reorder_flag).length;
  const high = filtered.filter((r) => r.reorder_flag && r.confidence === 'high').length;
  const med = filtered.filter((r) => r.reorder_flag && r.confidence === 'medium').length;
  const low = filtered.filter((r) => r.reorder_flag && r.confidence === 'low').length;

  return (
    <div className="flex items-baseline gap-6 rounded-md border border-border bg-surface px-4 py-2 text-sm">
      <span>
        <span className="font-semibold text-fg">{flagged}</span>
        <span className="ml-1 text-muted">alerts firing</span>
      </span>
      <span className="text-muted">·</span>
      <span>
        <span className="font-semibold text-ok">{high}</span>
        <span className="ml-1 text-muted">high</span>
      </span>
      <span>
        <span className="font-semibold text-warn">{med}</span>
        <span className="ml-1 text-muted">medium</span>
      </span>
      <span>
        <span className="font-semibold text-muted">{low}</span>
        <span className="ml-1 text-muted">low</span>
      </span>
      <span className="ml-auto text-xs text-muted">{filtered.length} rows shown</span>
    </div>
  );
}
```

- [ ] **Step 2: Smoke test**

Refresh `/alerts`. Expect a summary bar above the table. Change filter chips — counts update.

- [ ] **Step 3: Commit**

```bash
git add ui/components/list/SummaryStats.tsx
git commit -m "feat(ui): summary stats row with filter-aware counts"
```

---

### Task 14: Sparkline inline SVG

**Files:**
- Modify: `ui/components/list/Sparkline.tsx`

- [ ] **Step 1: Replace stub with inline SVG sparkline**

File: `ui/components/list/Sparkline.tsx`
```tsx
export function Sparkline({
  values,
  width = 80,
  height = 16,
}: {
  values: (number | null)[];
  width?: number;
  height?: number;
}) {
  const vals = values.filter((v): v is number => v !== null);
  if (vals.length < 2) {
    return <span className="inline-block h-4 w-20 text-muted">—</span>;
  }
  const min = Math.min(...vals);
  const max = Math.max(...vals);
  const span = max - min || 1;
  const stepX = width / (values.length - 1);
  const pts = values.map((v, i) => {
    const x = i * stepX;
    const y = v === null
      ? height / 2
      : height - ((v - min) / span) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const last = values[values.length - 1];
  const trending = vals.length > 1 ? vals[vals.length - 1] - vals[0] : 0;
  const color = trending < 0 ? '#dc2626' : '#16a34a';
  return (
    <svg width={width} height={height} className="align-middle">
      <polyline
        fill="none"
        stroke={color}
        strokeWidth="1.2"
        points={pts.join(' ')}
      />
      {last !== null && (
        <circle
          cx={width}
          cy={height - ((last - min) / span) * height}
          r="1.5"
          fill={color}
        />
      )}
    </svg>
  );
}
```

- [ ] **Step 2: Smoke test**

Refresh `/alerts`. Each row should render a tiny red/green sparkline showing on_hand trend.

- [ ] **Step 3: Commit**

```bash
git add ui/components/list/Sparkline.tsx
git commit -m "feat(ui): inline SVG sparkline for list-view trend column"
```

---

## Phase D — Lane view basics

---

### Task 15: Lane route scaffold + header

**Files:**
- Create: `ui/app/alerts/lane/[slug]/page.tsx`, `ui/components/lane/LaneHeader.tsx`

- [ ] **Step 1: Create dynamic route page**

File: `ui/app/alerts/lane/[slug]/page.tsx`
```tsx
import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  loadLane,
  loadLaneCounterfactual,
  loadLaneDemand,
  listLaneSlugs,
} from '@/lib/data';
import { LaneHeader } from '@/components/lane/LaneHeader';

export async function generateStaticParams() {
  const slugs = await listLaneSlugs();
  return slugs.map((slug) => ({ slug }));
}

export default async function LanePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;

  let lane, demand, cf;
  try {
    [lane, demand, cf] = await Promise.all([
      loadLane(slug),
      loadLaneDemand(slug),
      loadLaneCounterfactual(slug),
    ]);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-4">
      <Link href="/alerts" className="text-sm text-muted hover:text-fg">
        ← Back to alerts
      </Link>
      <LaneHeader lane={lane} />
      {/* Chart, tabs, side panel, demand breakdown land in subsequent tasks */}
      <pre className="text-xs text-muted">
        slug: {slug} · series len: {lane.series.length} · demand len: {demand.weekly.length} ·
        counterfactual: {cf.series.length}
      </pre>
    </div>
  );
}
```

- [ ] **Step 2: Create LaneHeader**

File: `ui/components/lane/LaneHeader.tsx`
```tsx
import type { LaneFile } from '@/lib/types';
import { fmtCases, fmtInt, fmtWeeks } from '@/lib/format';

export function LaneHeader({ lane }: { lane: LaneFile }) {
  const t = lane.today;
  const conf = t.confidence;
  const confColor =
    conf === 'high' ? 'bg-ok/10 text-ok' :
    conf === 'medium' ? 'bg-warn/10 text-warn' :
    'bg-gray-200 text-muted';

  const recommendation = t.reorder_flag
    ? `Alert firing · suggest ${fmtCases(t.suggested_cases)} · lead time ${fmtWeeks(t.lead_time_wk)} · run rate ${fmtInt(t.run_rate_wk)}/wk`
    : `No alert · ${fmtWeeks(t.weeks_of_cover)} cover · run rate ${fmtInt(t.run_rate_wk)}/wk`;

  return (
    <div className="rounded-md border border-border bg-surface px-5 py-3">
      <div className="flex items-center gap-3">
        <h1 className="font-mono text-lg font-semibold text-fg">{lane.sku}</h1>
        <span className="text-sm text-muted">·</span>
        <span className="text-sm text-fg">{lane.metadata.sku_desc}</span>
        <span className="text-sm text-muted">·</span>
        <span className="font-mono text-sm text-fg">{lane.dc}</span>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium ${confColor}`}>
          {conf}
        </span>
      </div>
      <p className={`mt-2 text-sm ${t.reorder_flag ? 'text-alert' : 'text-muted'}`}>
        {recommendation}
      </p>
    </div>
  );
}
```

- [ ] **Step 3: Smoke test**

```bash
cd ui && npm run dev &
```
Open `/alerts/lane/T-32206-SF`. Expect header with SKU, description, DC, confidence badge, and one-line recommendation. Kill: `kill %1`.

- [ ] **Step 4: Commit**

```bash
git add ui/app/alerts/lane/ ui/components/lane/LaneHeader.tsx
git commit -m "feat(ui): lane route scaffold + LaneHeader"
```

---

### Task 16: MainChart — on_hand + reorder_point lines

**Files:**
- Create: `ui/components/lane/MainChart.tsx`
- Modify: `ui/app/alerts/lane/[slug]/page.tsx`

- [ ] **Step 1: Create MainChart client component**

File: `ui/components/lane/MainChart.tsx`
```tsx
'use client';

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';
import { useMemo } from 'react';

type Strategy = 'mean' | 'p90';

export function MainChart({
  lane,
  strategy,
  overlay,
  counterfactual,
}: {
  lane: LaneFile;
  strategy: Strategy;
  overlay: 'none' | 'mean' | 'p90';
  counterfactual: LaneCounterfactualFile;
}) {
  const data = useMemo(() => {
    const cfByWeek = new Map(counterfactual.series.map((r) => [r.week_start, r]));
    return lane.series.map((r) => {
      const cf = cfByWeek.get(r.week_start);
      return {
        week_start: r.week_start,
        on_hand: r.on_hand_est,
        reorder_point: strategy === 'mean' ? r.reorder_point_mean : r.reorder_point_p90,
        alert_fired: strategy === 'mean' ? r.alert_fired_mean : r.alert_fired_p90,
        fresh_stockout: r.fresh_stockout,
        mean_followed: cf?.mean_followed ?? null,
        p90_followed: cf?.p90_followed ?? null,
      };
    });
  }, [lane, strategy, counterfactual]);

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
          <CartesianGrid stroke="#e5e7eb" strokeDasharray="2 4" />
          <XAxis
            dataKey="week_start"
            tick={{ fontSize: 11, fill: '#6b7280' }}
            minTickGap={32}
          />
          <YAxis
            tick={{ fontSize: 11, fill: '#6b7280' }}
            tickFormatter={(v) => fmtInt(v as number)}
            width={72}
          />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(v: number | null) => (v === null ? '—' : fmtInt(v))}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line
            type="monotone"
            dataKey="on_hand"
            name="on_hand (actual)"
            stroke="#1b2a4a"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="reorder_point"
            name={`reorder_point (${strategy})`}
            stroke="#f59e0b"
            strokeDasharray="5 4"
            strokeWidth={1.5}
            dot={false}
            connectNulls
          />
          {overlay !== 'none' && (
            <Line
              type="monotone"
              dataKey={overlay === 'mean' ? 'mean_followed' : 'p90_followed'}
              name={overlay === 'mean' ? 'mean-followed' : 'p90-followed'}
              stroke={overlay === 'mean' ? '#16a34a' : '#0891b2'}
              strokeWidth={1.5}
              strokeDasharray="2 2"
              dot={false}
              connectNulls
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Wire into lane page**

File: `ui/app/alerts/lane/[slug]/page.tsx`

Replace the `<pre>` debug block with the chart + toggle component (to be built next task). For now, just render the chart with defaults:

```tsx
import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  loadLane,
  loadLaneCounterfactual,
  loadLaneDemand,
  listLaneSlugs,
} from '@/lib/data';
import { LaneHeader } from '@/components/lane/LaneHeader';
import { LaneChartPanel } from '@/components/lane/LaneChartPanel';

export async function generateStaticParams() {
  const slugs = await listLaneSlugs();
  return slugs.map((slug) => ({ slug }));
}

export default async function LanePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let lane, demand, cf;
  try {
    [lane, demand, cf] = await Promise.all([
      loadLane(slug),
      loadLaneDemand(slug),
      loadLaneCounterfactual(slug),
    ]);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-4">
      <Link href="/alerts" className="text-sm text-muted hover:text-fg">
        ← Back to alerts
      </Link>
      <LaneHeader lane={lane} />
      <LaneChartPanel lane={lane} counterfactual={cf} />
      <pre className="text-xs text-muted">demand weeks: {demand.weekly.length}</pre>
    </div>
  );
}
```

- [ ] **Step 3: Create LaneChartPanel client wrapper (stateful toggle host)**

File: `ui/components/lane/LaneChartPanel.tsx`
```tsx
'use client';

import { useState } from 'react';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { MainChart } from './MainChart';

type Strategy = 'mean' | 'p90';
type Overlay = 'none' | 'mean' | 'p90';

export function LaneChartPanel({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const [strategy, _setStrategy] = useState<Strategy>('mean');
  const [overlay, setOverlay] = useState<Overlay>('none');

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted">Overlay:</span>
        {(['none', 'mean', 'p90'] as Overlay[]).map((opt) => (
          <button
            key={opt}
            onClick={() => setOverlay(opt)}
            className={
              'rounded border px-2 py-1 ' +
              (overlay === opt
                ? 'border-brand bg-brand text-white'
                : 'border-border bg-surface hover:bg-gray-50')
            }
          >
            {opt === 'none' ? 'Actual only' : opt === 'mean' ? '+ Mean' : '+ P90'}
          </button>
        ))}
      </div>
      <MainChart
        lane={lane}
        strategy={strategy}
        overlay={overlay}
        counterfactual={counterfactual}
      />
    </div>
  );
}
```

- [ ] **Step 4: Smoke test**

Open `/alerts/lane/T-32206-SF`. Expect a chart with blue `on_hand` line and dashed amber `reorder_point` line. Toggle `+ Mean` and `+ P90` — extra overlay lines appear.

- [ ] **Step 5: Commit**

```bash
git add ui/components/lane/MainChart.tsx ui/components/lane/LaneChartPanel.tsx ui/app/alerts/lane/
git commit -m "feat(ui): main chart with on_hand + reorder_point + counterfactual overlay"
```

---

### Task 17: Alert markers + stockout markers on the chart

**Files:**
- Modify: `ui/components/lane/MainChart.tsx`

- [ ] **Step 1: Add ReferenceDot and custom Scatter for alerts / stockouts**

Edit `MainChart.tsx` to import `Scatter` and `ReferenceDot`, then render alert / stockout markers:

Replace the entire file content:

File: `ui/components/lane/MainChart.tsx`
```tsx
'use client';

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';
import { useMemo } from 'react';

type Strategy = 'mean' | 'p90';
type Overlay = 'none' | 'mean' | 'p90';

export function MainChart({
  lane,
  strategy,
  overlay,
  counterfactual,
}: {
  lane: LaneFile;
  strategy: Strategy;
  overlay: Overlay;
  counterfactual: LaneCounterfactualFile;
}) {
  const data = useMemo(() => {
    const cfByWeek = new Map(counterfactual.series.map((r) => [r.week_start, r]));
    const posByWeek = new Map<string, { strategy: string; qty: number }>();
    for (const po of counterfactual.simulated_pos) {
      if (overlay !== 'none' && po.strategy === overlay) {
        const existing = posByWeek.get(po.arrival_week);
        posByWeek.set(po.arrival_week, {
          strategy: po.strategy,
          qty: (existing?.qty ?? 0) + po.qty,
        });
      }
    }
    return lane.series.map((r) => {
      const cf = cfByWeek.get(r.week_start);
      const alertFired = strategy === 'mean' ? r.alert_fired_mean : r.alert_fired_p90;
      const reorderPoint = strategy === 'mean' ? r.reorder_point_mean : r.reorder_point_p90;
      const po = posByWeek.get(r.week_start);
      return {
        week_start: r.week_start,
        on_hand: r.on_hand_est,
        reorder_point: reorderPoint,
        alert_marker: alertFired ? reorderPoint : null,
        alert_true_positive: alertFired && r.weeks_until_stockout !== null && r.weeks_until_stockout <= 12,
        stockout_marker: r.fresh_stockout && r.on_hand_est !== null ? 0 : null,
        mean_followed: cf?.mean_followed ?? null,
        p90_followed: cf?.p90_followed ?? null,
        po_marker: po ? (overlay === 'mean' ? cf?.mean_followed : cf?.p90_followed) ?? null : null,
        po_qty: po?.qty ?? null,
      };
    });
  }, [lane, strategy, overlay, counterfactual]);

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
          <CartesianGrid stroke="#e5e7eb" strokeDasharray="2 4" />
          <XAxis dataKey="week_start" tick={{ fontSize: 11, fill: '#6b7280' }} minTickGap={32} />
          <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={(v) => fmtInt(v as number)} width={72} />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(v: number | null, name: string) => {
              if (v === null || v === undefined) return ['—', name];
              return [fmtInt(v), name];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          <Line type="monotone" dataKey="on_hand" name="on_hand (actual)" stroke="#1b2a4a" strokeWidth={2} dot={false} connectNulls />
          <Line
            type="monotone"
            dataKey="reorder_point"
            name={`reorder_point (${strategy})`}
            stroke="#f59e0b"
            strokeDasharray="5 4"
            strokeWidth={1.5}
            dot={false}
            connectNulls
          />
          {overlay !== 'none' && (
            <Line
              type="monotone"
              dataKey={overlay === 'mean' ? 'mean_followed' : 'p90_followed'}
              name={overlay === 'mean' ? 'mean-followed' : 'p90-followed'}
              stroke={overlay === 'mean' ? '#16a34a' : '#0891b2'}
              strokeWidth={1.5}
              strokeDasharray="2 2"
              dot={false}
              connectNulls
            />
          )}
          <Scatter
            name="alert fired"
            dataKey="alert_marker"
            fill="#dc2626"
            shape="triangle"
          />
          <Scatter
            name="stockout"
            dataKey="stockout_marker"
            fill="#dc2626"
            shape="cross"
          />
          {overlay !== 'none' && (
            <Scatter
              name={`simulated PO (${overlay})`}
              dataKey="po_marker"
              fill={overlay === 'mean' ? '#16a34a' : '#0891b2'}
              shape="circle"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
```

- [ ] **Step 2: Smoke test**

Refresh `/alerts/lane/T-32206-SF`. Expect red triangle markers where alerts fired, red X markers where stockouts occurred. Toggle `+ Mean` / `+ P90` — green/teal circles appear along the overlay line.

- [ ] **Step 3: Commit**

```bash
git add ui/components/lane/MainChart.tsx
git commit -m "feat(ui): alert, stockout, and simulated-PO markers on main chart"
```

---

### Task 18: DeltaCard for counterfactual trough improvement

**Files:**
- Create: `ui/components/lane/DeltaCard.tsx`
- Modify: `ui/components/lane/LaneChartPanel.tsx`

- [ ] **Step 1: Create DeltaCard**

File: `ui/components/lane/DeltaCard.tsx`
```tsx
import type { LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';

export function DeltaCard({
  counterfactual,
  overlay,
}: {
  counterfactual: LaneCounterfactualFile;
  overlay: 'none' | 'mean' | 'p90';
}) {
  if (overlay === 'none') return null;
  const t = counterfactual.trough_delta;
  const chosen = overlay === 'mean' ? t.mean : t.p90;
  if (t.actual === null || chosen === null) return null;
  const improvement = chosen - t.actual;

  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3 text-sm">
      <div className="flex flex-wrap items-baseline gap-4">
        <span>
          <span className="text-muted">Actual trough:</span>{' '}
          <span className="font-mono font-semibold text-alert">{fmtInt(t.actual)}</span>
        </span>
        <span>
          <span className="text-muted">Mean-followed:</span>{' '}
          <span className={'font-mono font-semibold ' + (overlay === 'mean' ? 'text-ok' : 'text-muted')}>
            {fmtInt(t.mean)}
          </span>
        </span>
        <span>
          <span className="text-muted">P90-followed:</span>{' '}
          <span className={'font-mono font-semibold ' + (overlay === 'p90' ? 'text-ok' : 'text-muted')}>
            {fmtInt(t.p90)}
          </span>
        </span>
        <span className="ml-auto">
          <span className="text-muted">Improvement:</span>{' '}
          <span className="font-mono font-semibold text-ok">+{fmtInt(improvement)}</span>
          <span className="ml-1 text-muted">units</span>
        </span>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire DeltaCard into LaneChartPanel**

File: `ui/components/lane/LaneChartPanel.tsx`

Replace with:

```tsx
'use client';

import { useState } from 'react';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { MainChart } from './MainChart';
import { DeltaCard } from './DeltaCard';
import { NarrativeBanner } from './NarrativeBanner';

type Strategy = 'mean' | 'p90';
type Overlay = 'none' | 'mean' | 'p90';

export function LaneChartPanel({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const [strategy, _setStrategy] = useState<Strategy>('mean');
  const [overlay, setOverlay] = useState<Overlay>('none');

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted">Overlay:</span>
        {(['none', 'mean', 'p90'] as Overlay[]).map((opt) => (
          <button
            key={opt}
            onClick={() => setOverlay(opt)}
            className={
              'rounded border px-2 py-1 ' +
              (overlay === opt
                ? 'border-brand bg-brand text-white'
                : 'border-border bg-surface hover:bg-gray-50')
            }
          >
            {opt === 'none' ? 'Actual only' : opt === 'mean' ? '+ Mean' : '+ P90'}
          </button>
        ))}
      </div>
      <NarrativeBanner counterfactual={counterfactual} overlay={overlay} />
      <MainChart lane={lane} strategy={strategy} overlay={overlay} counterfactual={counterfactual} />
      <DeltaCard counterfactual={counterfactual} overlay={overlay} />
    </div>
  );
}
```

- [ ] **Step 3: Create NarrativeBanner stub (we flesh it out in Task 25)**

File: `ui/components/lane/NarrativeBanner.tsx`
```tsx
import type { LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';

export function NarrativeBanner({
  counterfactual,
  overlay,
}: {
  counterfactual: LaneCounterfactualFile;
  overlay: 'none' | 'mean' | 'p90';
}) {
  const n = counterfactual.narrative;
  const t = counterfactual.trough_delta;
  let text: string;
  if (n) {
    text =
      overlay === 'none' ? n.actual_only :
      overlay === 'mean' ? n.plus_mean :
      n.plus_p90;
  } else {
    if (overlay === 'none') {
      text = t.actual !== null
        ? `Actual trough: ${fmtInt(t.actual)} units.`
        : 'No inventory trough recorded for this lane.';
    } else {
      const chosen = overlay === 'mean' ? t.mean : t.p90;
      const improvement = (chosen !== null && t.actual !== null) ? chosen - t.actual : null;
      text = improvement !== null
        ? `Following the ${overlay} strategy would improve the trough by ${fmtInt(improvement)} units.`
        : `${overlay} strategy trajectory shown above.`;
    }
  }
  return (
    <div className="rounded-md border border-border bg-gray-50 px-4 py-2 text-sm italic text-fg">
      {text}
    </div>
  );
}
```

- [ ] **Step 4: Smoke test**

Refresh `/alerts/lane/T-32206-SF`. Expect (a) italic narrative banner above chart (showcase lane has authored text; others have computed fallback), (b) delta card below chart that appears only when an overlay is active.

- [ ] **Step 5: Commit**

```bash
git add ui/components/lane/DeltaCard.tsx ui/components/lane/NarrativeBanner.tsx ui/components/lane/LaneChartPanel.tsx
git commit -m "feat(ui): counterfactual delta card + narrative banner"
```

---

## Phase E — Lane view panels and tabs

---

### Task 19: SidePanel (Why firing, metadata, lane stats)

**Files:**
- Create: `ui/components/lane/SidePanel.tsx`
- Modify: `ui/app/alerts/lane/[slug]/page.tsx`

- [ ] **Step 1: Create SidePanel**

File: `ui/components/lane/SidePanel.tsx`
```tsx
import type { LaneFile, LaneIndexRow } from '@/lib/types';
import { fmtCases, fmtFloat, fmtInt, fmtPct, fmtWeeks } from '@/lib/format';

export function SidePanel({
  lane,
  laneSummary,
}: {
  lane: LaneFile;
  laneSummary: LaneIndexRow | undefined;
}) {
  const t = lane.today;
  const m = lane.metadata;

  return (
    <aside className="w-[280px] shrink-0 space-y-4">
      {t.reorder_flag && (
        <Card title="Why firing?">
          <Row label="Available" value={fmtInt(t.available)} />
          <Row label="Reorder point" value={fmtInt(t.reorder_point)} />
          <Row
            label="Gap"
            value={
              t.available !== null && t.reorder_point !== null
                ? fmtInt(t.reorder_point - t.available)
                : '—'
            }
          />
          <Row label="Suggest" value={`${fmtInt(t.suggested_qty)} u · ${fmtCases(t.suggested_cases)}`} />
          <p className="mt-2 text-xs leading-snug text-muted">
            {t.lead_time_wk !== null && t.run_rate_wk !== null
              ? `${fmtWeeks(t.lead_time_wk)} × ${fmtInt(t.run_rate_wk)}/wk = ${fmtInt(t.lead_time_wk * t.run_rate_wk)} needed, + ${fmtInt(t.safety_stock)} safety = ${fmtInt(t.reorder_point)} reorder point.`
              : 'Insufficient data for derivation.'}
          </p>
        </Card>
      )}

      <Card title="SKU metadata">
        <Row label="Brand" value={laneSummary?.brand || '—'} />
        <Row label="Case pack" value={m.case_pack !== null ? String(m.case_pack) : '—'} />
        <Row label="Vendor" value={m.vendor || '—'} />
        <Row label="Country" value={m.country || '—'} />
        <Row
          label="Lead time"
          value={`${fmtWeeks(t.lead_time_wk)}${t.lead_time_source ? ` (${t.lead_time_source})` : ''}`}
        />
      </Card>

      <Card title="Lane stats">
        <Row label="Fresh rate" value={laneSummary ? fmtPct(laneSummary.fresh_rate * 100, 1) : '—'} />
        <Row label="Run rate" value={`${fmtInt(t.run_rate_wk)}/wk`} />
        <Row label="CV (weekly)" value={
          t.std_wk !== null && t.run_rate_wk !== null && t.run_rate_wk > 0
            ? fmtFloat(t.std_wk / t.run_rate_wk, 2)
            : '—'
        } />
        <Row label="Clean weeks" value={fmtInt(t.n_clean_weeks)} />
      </Card>
    </aside>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3">
      <h3 className="mb-2 text-xs uppercase tracking-wider text-muted">{title}</h3>
      <div className="space-y-1 text-sm">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-[13px] text-fg">{value}</span>
    </div>
  );
}
```

- [ ] **Step 2: Modify lane page to flex chart + side panel side-by-side**

File: `ui/app/alerts/lane/[slug]/page.tsx`

```tsx
import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  loadLane,
  loadLaneCounterfactual,
  loadLaneDemand,
  loadLanesIndex,
  listLaneSlugs,
} from '@/lib/data';
import { LaneHeader } from '@/components/lane/LaneHeader';
import { LaneChartPanel } from '@/components/lane/LaneChartPanel';
import { SidePanel } from '@/components/lane/SidePanel';

export async function generateStaticParams() {
  const slugs = await listLaneSlugs();
  return slugs.map((slug) => ({ slug }));
}

export default async function LanePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let lane, demand, cf, lanesIdx;
  try {
    [lane, demand, cf, lanesIdx] = await Promise.all([
      loadLane(slug),
      loadLaneDemand(slug),
      loadLaneCounterfactual(slug),
      loadLanesIndex(),
    ]);
  } catch {
    notFound();
  }

  const laneSummary = lanesIdx.find((l) => l.sku === lane.sku && l.dc === lane.dc);

  return (
    <div className="space-y-4">
      <Link href="/alerts" className="text-sm text-muted hover:text-fg">
        ← Back to alerts
      </Link>
      <LaneHeader lane={lane} />
      <div className="flex gap-4">
        <div className="flex-1">
          <LaneChartPanel lane={lane} counterfactual={cf} />
        </div>
        <SidePanel lane={lane} laneSummary={laneSummary} />
      </div>
      <pre className="text-xs text-muted">demand weeks: {demand.weekly.length}</pre>
    </div>
  );
}
```

- [ ] **Step 3: Smoke test**

Refresh `/alerts/lane/T-32206-SF`. Expect side panel on the right with "Why firing?", SKU metadata, and Lane stats cards.

- [ ] **Step 4: Commit**

```bash
git add ui/components/lane/SidePanel.tsx ui/app/alerts/lane/[slug]/page.tsx
git commit -m "feat(ui): lane view side panel with why-firing, metadata, stats"
```

---

### Task 20: Tab infrastructure + Chart/Backtest/Strategy tab shells

**Files:**
- Create: `ui/components/lane/LaneTabs.tsx`, `ui/components/lane/ChartTab.tsx`, `ui/components/lane/BacktestTab.tsx`, `ui/components/lane/StrategyTab.tsx`
- Modify: `ui/app/alerts/lane/[slug]/page.tsx`

- [ ] **Step 1: Create LaneTabs wrapper**

File: `ui/components/lane/LaneTabs.tsx`
```tsx
'use client';

import { useState } from 'react';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { ChartTab } from './ChartTab';
import { BacktestTab } from './BacktestTab';
import { StrategyTab } from './StrategyTab';

type TabKey = 'chart' | 'backtest' | 'strategy';

export function LaneTabs({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const [active, setActive] = useState<TabKey>('chart');
  return (
    <div className="space-y-3">
      <div className="flex gap-1 border-b border-border">
        {(['chart', 'backtest', 'strategy'] as TabKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setActive(k)}
            className={
              'px-3 py-1.5 text-sm capitalize ' +
              (active === k
                ? 'border-b-2 border-brand font-semibold text-brand'
                : 'text-muted hover:text-fg')
            }
          >
            {k}
          </button>
        ))}
      </div>
      {active === 'chart' && <ChartTab lane={lane} counterfactual={counterfactual} />}
      {active === 'backtest' && <BacktestTab lane={lane} />}
      {active === 'strategy' && <StrategyTab lane={lane} counterfactual={counterfactual} />}
    </div>
  );
}
```

- [ ] **Step 2: Create ChartTab — wraps existing LaneChartPanel**

File: `ui/components/lane/ChartTab.tsx`
```tsx
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { LaneChartPanel } from './LaneChartPanel';

export function ChartTab({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  return <LaneChartPanel lane={lane} counterfactual={counterfactual} />;
}
```

- [ ] **Step 3: Create BacktestTab**

File: `ui/components/lane/BacktestTab.tsx`
```tsx
import type { LaneFile } from '@/lib/types';
import { fmtInt, fmtWeeks } from '@/lib/format';

export function BacktestTab({ lane }: { lane: LaneFile }) {
  const alertRows = lane.series.filter((r) => r.alert_fired_mean || r.alert_fired_p90);
  const tpCount = alertRows.filter(
    (r) => r.weeks_until_stockout !== null && r.weeks_until_stockout <= 12
  ).length;
  const stockoutCount = lane.series.filter((r) => r.fresh_stockout).length;
  const totalAlerts = alertRows.length;

  const precision = totalAlerts > 0 ? (tpCount / totalAlerts) * 100 : 0;
  const recall = stockoutCount > 0 ? (tpCount / stockoutCount) * 100 : 0;
  const warningWeeks = alertRows
    .map((r) => r.weeks_until_stockout)
    .filter((w): w is number => w !== null)
    .sort((a, b) => a - b);
  const median = warningWeeks.length > 0
    ? warningWeeks[Math.floor(warningWeeks.length / 2)]
    : null;

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border bg-surface px-4 py-3 text-sm">
        <div className="flex flex-wrap gap-6">
          <Stat label="Precision" value={`${precision.toFixed(0)}%`} />
          <Stat label="Recall" value={`${recall.toFixed(0)}%`} />
          <Stat label="Median warning" value={median !== null ? fmtWeeks(median) : '—'} />
          <Stat label="Alerts fired" value={fmtInt(totalAlerts)} />
          <Stat label="Real stockouts" value={fmtInt(stockoutCount)} />
        </div>
      </div>
      <div className="overflow-hidden rounded-md border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-3 py-2">Week</th>
              <th className="px-3 py-2 text-right">Reorder pt (mean)</th>
              <th className="px-3 py-2 text-right">Reorder pt (p90)</th>
              <th className="px-3 py-2 text-right">On hand</th>
              <th className="px-3 py-2 text-center">Mean alert</th>
              <th className="px-3 py-2 text-center">P90 alert</th>
              <th className="px-3 py-2 text-right">Wks to stockout</th>
            </tr>
          </thead>
          <tbody>
            {alertRows.slice(-40).reverse().map((r) => (
              <tr key={r.week_start} className="border-t border-border hover:bg-gray-50">
                <td className="px-3 py-1.5 font-mono text-[13px]">{r.week_start}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.reorder_point_mean)}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.reorder_point_p90)}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.on_hand_est)}</td>
                <td className="px-3 py-1.5 text-center">{r.alert_fired_mean ? '●' : ''}</td>
                <td className="px-3 py-1.5 text-center">{r.alert_fired_p90 ? '●' : ''}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  {r.weeks_until_stockout !== null ? fmtWeeks(r.weeks_until_stockout) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className="font-mono text-lg font-semibold text-fg">{value}</div>
    </div>
  );
}
```

- [ ] **Step 4: Create StrategyTab**

File: `ui/components/lane/StrategyTab.tsx`
```tsx
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';

export function StrategyTab({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const meanAlerts = lane.series.filter((r) => r.alert_fired_mean).length;
  const p90Alerts = lane.series.filter((r) => r.alert_fired_p90).length;
  const stockouts = lane.series.filter((r) => r.fresh_stockout).length;
  const meanTP = lane.series.filter(
    (r) => r.alert_fired_mean && r.weeks_until_stockout !== null && r.weeks_until_stockout <= 12
  ).length;
  const p90TP = lane.series.filter(
    (r) => r.alert_fired_p90 && r.weeks_until_stockout !== null && r.weeks_until_stockout <= 12
  ).length;

  const meanOrders = counterfactual.simulated_pos
    .filter((p) => p.strategy === 'mean')
    .reduce((acc, p) => acc + p.qty, 0);
  const p90Orders = counterfactual.simulated_pos
    .filter((p) => p.strategy === 'p90')
    .reduce((acc, p) => acc + p.qty, 0);

  return (
    <div className="grid grid-cols-2 gap-4">
      <StratCard
        title="Mean"
        alerts={meanAlerts}
        tp={meanTP}
        stockouts={stockouts}
        totalOrdered={meanOrders}
        accent="text-ok"
      />
      <StratCard
        title="P90"
        alerts={p90Alerts}
        tp={p90TP}
        stockouts={stockouts}
        totalOrdered={p90Orders}
        accent="text-cyan-700"
      />
      <p className="col-span-2 text-xs italic text-muted">
        Mean uses the average weekly clean-demand run rate. P90 uses the 90th-percentile
        weekly run rate, widening the safety buffer — fires more alerts but catches more
        real stockouts.
      </p>
    </div>
  );
}

function StratCard({
  title,
  alerts,
  tp,
  stockouts,
  totalOrdered,
  accent,
}: {
  title: string;
  alerts: number;
  tp: number;
  stockouts: number;
  totalOrdered: number;
  accent: string;
}) {
  const fp = alerts - tp;
  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3">
      <h3 className={`text-sm font-semibold ${accent}`}>{title}</h3>
      <dl className="mt-2 space-y-1 text-sm">
        <StatRow label="Alerts fired" value={fmtInt(alerts)} />
        <StatRow label="True positives" value={fmtInt(tp)} />
        <StatRow label="False positives" value={fmtInt(fp)} />
        <StatRow label="Real stockouts" value={fmtInt(stockouts)} />
        <StatRow label="Simulated units ordered" value={fmtInt(totalOrdered)} />
      </dl>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-[13px] text-fg">{value}</span>
    </div>
  );
}
```

- [ ] **Step 5: Modify lane page to use LaneTabs**

Edit `ui/app/alerts/lane/[slug]/page.tsx` — replace the `<LaneChartPanel ... />` line with `<LaneTabs lane={lane} counterfactual={cf} />`. The final page:

```tsx
import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  loadLane,
  loadLaneCounterfactual,
  loadLaneDemand,
  loadLanesIndex,
  listLaneSlugs,
} from '@/lib/data';
import { LaneHeader } from '@/components/lane/LaneHeader';
import { LaneTabs } from '@/components/lane/LaneTabs';
import { SidePanel } from '@/components/lane/SidePanel';
import { DemandBreakdown } from '@/components/lane/DemandBreakdown';

export async function generateStaticParams() {
  const slugs = await listLaneSlugs();
  return slugs.map((slug) => ({ slug }));
}

export default async function LanePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let lane, demand, cf, lanesIdx;
  try {
    [lane, demand, cf, lanesIdx] = await Promise.all([
      loadLane(slug),
      loadLaneDemand(slug),
      loadLaneCounterfactual(slug),
      loadLanesIndex(),
    ]);
  } catch {
    notFound();
  }

  const laneSummary = lanesIdx.find((l) => l.sku === lane.sku && l.dc === lane.dc);

  return (
    <div className="space-y-4">
      <Link href="/alerts" className="text-sm text-muted hover:text-fg">
        ← Back to alerts
      </Link>
      <LaneHeader lane={lane} />
      <div className="flex gap-4">
        <div className="flex-1 min-w-0">
          <LaneTabs lane={lane} counterfactual={cf} />
        </div>
        <SidePanel lane={lane} laneSummary={laneSummary} />
      </div>
      <DemandBreakdown demand={demand} />
    </div>
  );
}
```

- [ ] **Step 6: Create DemandBreakdown placeholder so the build doesn't break**

File: `ui/components/lane/DemandBreakdown.tsx`
```tsx
import type { LaneDemandFile } from '@/lib/types';
export function DemandBreakdown(_: { demand: LaneDemandFile }) {
  return null;
}
```

- [ ] **Step 7: Smoke test**

Refresh `/alerts/lane/T-32206-SF`. Expect a tab bar with `chart / backtest / strategy`. Click Backtest — see precision/recall summary + table. Click Strategy — see side-by-side mean vs p90 cards.

- [ ] **Step 8: Commit**

```bash
git add ui/components/lane/
git commit -m "feat(ui): lane tabs — Chart / Backtest / Strategy content"
```

---

### Task 21: DemandBreakdown — stacked-by-channel chart + top customers

**Files:**
- Modify: `ui/components/lane/DemandBreakdown.tsx`

- [ ] **Step 1: Replace stub**

File: `ui/components/lane/DemandBreakdown.tsx`
```tsx
'use client';

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { LaneDemandFile } from '@/lib/types';
import { fmtInt, fmtPct } from '@/lib/format';

const CHANNEL_COLORS = {
  MM: '#1b2a4a',
  AM: '#0891b2',
  HF: '#a855f7',
};

export function DemandBreakdown({ demand }: { demand: LaneDemandFile }) {
  if (demand.weekly.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
        Demand breakdown
      </h2>
      <div className="rounded-md border border-border bg-surface p-3">
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={demand.weekly} margin={{ top: 8, right: 12, left: 12, bottom: 8 }}>
            <CartesianGrid stroke="#e5e7eb" strokeDasharray="2 4" />
            <XAxis dataKey="week_start" tick={{ fontSize: 11, fill: '#6b7280' }} minTickGap={32} />
            <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={(v) => fmtInt(v as number)} width={72} />
            <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v: number) => fmtInt(v)} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="MM" stackId="1" fill={CHANNEL_COLORS.MM} stroke={CHANNEL_COLORS.MM} name="MM" />
            <Area type="monotone" dataKey="AM" stackId="1" fill={CHANNEL_COLORS.AM} stroke={CHANNEL_COLORS.AM} name="AM" />
            <Area type="monotone" dataKey="HF" stackId="1" fill={CHANNEL_COLORS.HF} stroke={CHANNEL_COLORS.HF} name="HF" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {demand.top_customers.length > 0 && (
        <div className="rounded-md border border-border bg-surface px-4 py-3">
          <h3 className="text-xs uppercase tracking-wider text-muted">Top customers</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {demand.top_customers.map((c) => (
              <li key={c.custnmbr} className="flex items-center gap-2">
                <span className="font-mono text-[13px] text-muted w-20">{c.custnmbr}</span>
                <span className="flex-1 truncate text-fg">{c.name}</span>
                <span className="w-14 text-right font-mono text-[13px] text-fg">
                  {fmtPct(c.share_pct, 1)}
                </span>
                <div className="w-32 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-brand" style={{ width: `${Math.min(100, c.share_pct)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
```

- [ ] **Step 2: Smoke test**

Refresh `/alerts/lane/T-32206-SF`. Expect stacked-area chart showing MM/AM/HF demand over time below the main content, plus a top-5 customers block.

- [ ] **Step 3: Commit**

```bash
git add ui/components/lane/DemandBreakdown.tsx
git commit -m "feat(ui): demand breakdown stacked-area chart + top customers"
```

---

## Phase F — Polish & ship

---

### Task 22: Final static build + end-to-end demo walkthrough

**Files:**
- None (verification only)

- [ ] **Step 1: Static export build**

```bash
cd ui && npm run build 2>&1 | tail -30
```
Expected: build succeeds; `ui/out/` is populated. Look for the line `Route (app)` showing `/alerts/lane/[slug]` with `107` pages generated.

- [ ] **Step 2: Serve the static export locally**

```bash
cd ui && npx -y http-server out -p 4000 &
```
Wait 2s. Then:
```bash
curl -sS http://localhost:4000/alerts/ | grep -c "alerts firing"
```
Expected: ≥1.

```bash
curl -sS http://localhost:4000/alerts/lane/T-32206-SF/ | grep -c "Tiger Balm"
```
Expected: ≥1.

Kill: `kill %1`.

- [ ] **Step 3: Manual demo walkthrough**

Start `npm run dev` and run through the demo script:

1. Open `http://localhost:3000/alerts` → List view with flagged alerts default, sparklines visible, summary count.
2. Click DC chip "NJ" → URL becomes `?dc=NJ`, table filters.
3. Click a row for `T-32206 NJ` → Lane view loads.
4. On Lane view: header shows recommendation. Chart shows on_hand + reorder_point dashed line + red triangles for alerts + red X for stockouts.
5. Click `+ Mean` toggle → green overlay line appears + green PO circles + delta card + narrative banner.
6. Click `+ P90` toggle → teal overlay line swaps in + p90 banner text.
7. Click `Backtest` tab → precision/recall stats + alert history table.
8. Click `Strategy` tab → side-by-side mean vs p90 comparison.
9. Back link returns to list preserving filter state (if implemented; acceptable if filters reset — this is a prototype).
10. Open `/curves` → "coming soon" stub.

Document any smoke-test failures for follow-up.

- [ ] **Step 4: Commit any final adjustments**

```bash
git add -A ui/
git commit -m "chore(ui): final static-build verification" --allow-empty
```

- [ ] **Step 5: Update `notes/status.md`**

Add a bullet under "Recently completed":

```markdown
- **UI prototype (F1 reorder alerts)** — static Next.js + Recharts app at `ui/`.
  Two-tab shell (Reorder Alerts + Demand Curves stub). List view at `/alerts`
  with filter chips (URL-state), sortable table, per-row on_hand sparklines,
  summary stats. Lane view at `/alerts/lane/[slug]` with TradingView-style
  main chart (on_hand + reorder_point + alert/stockout/simulated-PO markers),
  counterfactual overlay (Actual / +Mean / +P90 toggle), authored narrative
  banners for 3 showcase lanes (T-32206-SF, T-32206-NJ, F-04111-NJ), delta
  readout card, side panel (why-firing + metadata + lane stats), tabs for
  Backtest + Strategy, and demand breakdown stacked-area chart + top customers.
  Pipeline notebooks 09 + 10 dump JSON artifacts to `ui/data/` (committed).
  `npm run build` produces `ui/out/` for static deploy.
```

Then commit:
```bash
git add notes/status.md
git commit -m "docs: status update — UI prototype complete"
```

---

## Spec coverage check

| Spec requirement | Implementing task(s) |
|---|---|
| §2 Two-tab shell (Alerts + Curves stub) | 9 |
| §2 Routes `/alerts`, `/alerts/lane/[slug]`, `/curves` | 9, 11, 15 |
| §2 Static export | 8 |
| §2 URL-as-state | 11, 12 |
| §3 Data contract — alerts_today.json + embedded sparkline | 2 |
| §3 lanes_index.json + backtest_summary.json | 3 |
| §3 per-lane JSON | 4 |
| §3 demand breakdown JSON | 5 |
| §3 counterfactual JSON + narrative | 6, 7 |
| §3 `ui/data/` committed | 1 |
| §4 Filter chips + summary + sortable table + sparkline + empty state | 11, 12, 13, 14 |
| §4 Default `status=flagged` | 11 |
| §5 Lane header + today recommendation | 15 |
| §5 Main chart with on_hand + reorder_point + markers | 16, 17 |
| §5 Counterfactual toggle + overlay lines | 16, 18 |
| §5 Simulated PO arrival markers | 17 |
| §5 Delta readout card | 18 |
| §5 Narrative banner (showcase taglines + fallback) | 18 |
| §5 Side panel (why firing + metadata + stats) | 19 |
| §5 Tabs (Chart / Backtest / Strategy) | 20 |
| §5 Demand breakdown stacked area + top customers | 21 |
| §7 File layout (`ui/app`, `components`, `lib`, `data`) | 8, 9, 10, 11+ |
| §7 Pipeline integration (final cells in 09 + 10) | 2–7 |
| §11 Done criteria — build + 8-step walkthrough | 22 |

All spec sections have at least one implementing task. Out-of-scope items (auth, tests, F2 content, dark mode, mobile polish, accessibility audit) have no tasks, as intended.
