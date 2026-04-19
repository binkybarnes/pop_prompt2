"""Regenerate per-lane UI backtest JSON using the trend-aware best policy.

Produces:
  ui/data/lane/{SKU}-{DC}.json — single-policy series with on_hand_actual,
      on_hand_sim (if we had followed the alerts), reorder_point, run_rate_wk,
      regime, alert_fired, po_ordered (placed), po_received (arrived),
      fresh_stockout + today snapshot + simulated_pos list.
  ui/data/lanes_index.json      — one row per lane for the list view.
  ui/data/backtest_summary.json — headline accuracy stats for the best policy.

Drops the mean/p90 dual-strategy schema. Reads pipeline artifacts from 01-09,
so run those first.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.reorder import (  # noqa: E402
    DEFAULT_LEAD_WEEKS,
    FORWARD_COVER_WEEKS,
    _round_up_case,
    build_reorder_alerts,
)

ART = ROOT / 'pipeline' / 'artifacts'
UI_DATA = ROOT / 'ui' / 'data'
LANE_DIR = UI_DATA / 'lane'
LANE_DIR.mkdir(parents=True, exist_ok=True)

DC_MAP = {'1': 'SF', '2': 'NJ', '3': 'LA'}
POLICY_KW = dict(
    use_trend_regime=True,
    use_empirical_p99_ss=True,
    ss_floor_frac=0.70,
)

START = pd.Timestamp('2023-04-03')
END   = pd.Timestamp('2025-10-13')
STEP  = pd.Timedelta(weeks=4)


# ── Load ────────────────────────────────────────────────────────────────
weekly        = pd.read_parquet(ART / 'clean_demand_weekly.parquet')
inv_weekly    = pd.read_parquet(ART / 'inv_weekly.parquet')
im            = pd.read_parquet(ART / 'item_master.parquet')
po            = pd.read_parquet(ART / 'po.parquet')
sales         = pd.read_parquet(ART / 'sales.parquet')
alerts_today  = pd.read_parquet(ART / 'reorder_alerts.parquet')

_lane_status_path = ART / 'lane_status.parquet'
if _lane_status_path.exists():
    lane_status = pd.read_parquet(_lane_status_path)
    status_by_lane = {
        (r['ITEMNMBR'], r['DC']): {
            'status':             str(r['status']),
            'snapshot_on_hand':   float(r['snapshot_on_hand']) if pd.notna(r['snapshot_on_hand']) else None,
            'hist_run_rate_wk':   float(r['hist_run_rate_wk']) if pd.notna(r['hist_run_rate_wk']) else None,
        }
        for _, r in lane_status.iterrows()
    }
else:
    status_by_lane = {}

sales['QTY_BASE']   = sales['QUANTITY_adj'].astype(float) * sales['QTYBSUOM'].fillna(1).astype(float)
sales['DC']         = sales['LOCNCODE'].astype(str).map(DC_MAP)
sales               = sales.dropna(subset=['DC'])
sales['week_start'] = pd.to_datetime(sales['DOCDATE']).dt.to_period('W-SUN').dt.start_time
outflow_wk = (sales.groupby(['ITEMNMBR', 'DC', 'week_start'], as_index=False)['QTY_BASE']
                   .sum()
                   .rename(columns={'QTY_BASE': 'outflow'}))


# ── Walk-forward ────────────────────────────────────────────────────────
def alerts_as_of(as_of_week: pd.Timestamp) -> pd.DataFrame:
    past = weekly[weekly['week_start'] < as_of_week]
    if past.empty:
        return pd.DataFrame()
    snap = inv_weekly[inv_weekly['week_start'] == as_of_week].copy()
    if snap.empty:
        return pd.DataFrame()
    snap = snap.rename(columns={'ITEMNMBR': 'Item Number', 'on_hand_est': 'On Hand'})
    snap['Available']   = snap['On Hand']
    snap['Description'] = None
    snap = snap[['Item Number', 'DC', 'Available', 'On Hand', 'Description']]
    past_po = po[po['Receipt Date'] < as_of_week]
    a = build_reorder_alerts(past, snap, im, po=past_po, dc_map=DC_MAP, **POLICY_KW)
    a.insert(0, 'as_of_week', as_of_week)
    return a


def attach_forward_truth(alerts: pd.DataFrame) -> pd.DataFrame:
    inv_idx   = inv_weekly.set_index(['ITEMNMBR', 'DC']).sort_index()
    inv_point = inv_weekly.set_index(['ITEMNMBR', 'DC', 'week_start'])['on_hand_est']

    out = alerts.copy()
    inv_asof, fs, mfo, wus = [], [], [], []
    for _, r in out.iterrows():
        key = (r['ITEMNMBR'], r['DC'])
        lead = r['lead_time_wk'] if pd.notna(r['lead_time_wk']) else DEFAULT_LEAD_WEEKS
        window_end = r['as_of_week'] + pd.Timedelta(weeks=int(np.ceil(lead)))
        inv_asof.append(inv_point.get((r['ITEMNMBR'], r['DC'], r['as_of_week']), np.nan))
        try:
            sub = inv_idx.loc[[key]]
        except KeyError:
            fs.append(False); mfo.append(np.nan); wus.append(np.nan); continue
        sub = sub[(sub['week_start'] > r['as_of_week']) & (sub['week_start'] <= window_end)]
        if sub.empty:
            fs.append(False); mfo.append(np.nan); wus.append(np.nan); continue
        dips = sub[sub['on_hand_est'] <= 0]
        fs.append(not dips.empty)
        mfo.append(sub['on_hand_est'].min())
        wus.append((dips['week_start'].min() - r['as_of_week']).days / 7.0 if not dips.empty else np.nan)

    out['inv_at_asof']          = inv_asof
    out['forward_stockout']     = fs
    out['min_forward_on_hand']  = mfo
    out['weeks_until_stockout'] = wus
    out['fresh_stockout']       = (out['inv_at_asof'] > 0) & out['forward_stockout']
    return out


as_of_weeks = pd.date_range(START, END, freq=STEP)
print(f'walk-forward: {len(as_of_weeks)} as-of weeks, policy={POLICY_KW}')
frames = []
for i, w in enumerate(as_of_weeks):
    a = alerts_as_of(w)
    if not a.empty:
        frames.append(a)
    if i % 8 == 0:
        print(f'  [{i + 1}/{len(as_of_weeks)}] {w.date()}')
alerts_wf = pd.concat(frames, ignore_index=True)
alerts_wf = attach_forward_truth(alerts_wf)
print(f'alerts_wf: {alerts_wf.shape}  flagged={int(alerts_wf["reorder_flag"].sum())}')


# ── Per-lane on_hand simulation ─────────────────────────────────────────
def simulate_followed(sku: str, dc: str) -> pd.DataFrame:
    """(Q,r) on_hand roll-forward using *this lane's* walk-forward alerts."""
    lane = alerts_wf[(alerts_wf.ITEMNMBR == sku) & (alerts_wf.DC == dc)].sort_values('as_of_week')
    if lane.empty:
        return pd.DataFrame()
    alerts_by_week = {r['as_of_week']: r for _, r in lane.iterrows()}
    start_week = lane['as_of_week'].min()

    inv_lane = inv_weekly[(inv_weekly.ITEMNMBR == sku) & (inv_weekly.DC == dc)].sort_values('week_start')
    seed = inv_lane[inv_lane['week_start'] == start_week]
    if seed.empty:
        return pd.DataFrame()
    on_hand = float(seed['on_hand_est'].iloc[0])

    of = (outflow_wk[(outflow_wk.ITEMNMBR == sku) & (outflow_wk.DC == dc)]
          .set_index('week_start')['outflow'])

    weeks = inv_lane[inv_lane['week_start'] >= start_week]['week_start'].tolist()
    po_schedule: dict[pd.Timestamp, float] = {}
    rows = []
    for w in weeks:
        po_arr_qty = po_schedule.pop(w, 0.0)
        on_hand   += po_arr_qty
        out_qty    = float(of.get(w, 0.0))
        on_hand   -= out_qty
        alert_fires = False
        po_qty      = 0.0
        arrival     = None
        if w in alerts_by_week:
            a    = alerts_by_week[w]
            rp   = float(a['reorder_point'])  if pd.notna(a['reorder_point'])  else float('nan')
            rr   = float(a['run_rate_wk'])    if pd.notna(a['run_rate_wk'])    else 0.0
            cp   = float(a['case_pack'])      if pd.notna(a['case_pack'])      else 1.0
            lead = float(a['lead_time_wk'])   if pd.notna(a['lead_time_wk'])   else 13.0
            inflight = sum(po_schedule.values())
            ip       = on_hand + inflight
            if pd.notna(rp) and ip < rp:
                raw   = max(0.0, rp + FORWARD_COVER_WEEKS * rr - ip)
                po_qty = _round_up_case(raw, cp)
                if po_qty > 0:
                    arrival = w + pd.Timedelta(weeks=int(round(lead)))
                    po_schedule[arrival] = po_schedule.get(arrival, 0.0) + po_qty
                    alert_fires = True
        rows.append({
            'week_start':     w,
            'on_hand_sim':    on_hand,
            'po_arrives':     po_arr_qty,
            'alert_fires':    alert_fires,
            'po_ordered':     po_qty,
            'po_arrival_week': arrival,
        })
    return pd.DataFrame(rows)


# ── Per-lane JSON export ────────────────────────────────────────────────
alerts_today_idx = alerts_today.set_index(['ITEMNMBR', 'DC'])


def _f(v):
    if v is None or (isinstance(v, float) and np.isnan(v)) or pd.isna(v):
        return None
    return float(v)


def _s(v):
    if v is None or pd.isna(v):
        return None
    return str(v)


lanes_written = 0
lanes_index   = []

for (sku, dc), group in alerts_wf.groupby(['ITEMNMBR', 'DC']):
    inv_lane      = inv_weekly[(inv_weekly.ITEMNMBR == sku) & (inv_weekly.DC == dc)].sort_values('week_start')
    sim           = simulate_followed(sku, dc)
    inv_by_wk     = inv_lane.set_index('week_start')['on_hand_est'].to_dict()
    alerts_by_wk  = {r['as_of_week']: r for _, r in group.sort_values('as_of_week').iterrows()}
    sim_by_wk     = {r['week_start']: r for _, r in sim.iterrows()} if not sim.empty else {}

    all_weeks = sorted(set(inv_by_wk) | set(alerts_by_wk) | set(sim_by_wk))

    series = []
    for w in all_weeks:
        a = alerts_by_wk.get(w)
        s = sim_by_wk.get(w)
        series.append({
            'week_start':           str(pd.Timestamp(w).date()),
            'on_hand_est':          _f(inv_by_wk.get(w)),
            'on_hand_sim':          _f(s['on_hand_sim']) if s is not None else None,
            'reorder_point':        _f(a['reorder_point']) if a is not None else None,
            'run_rate_wk':          _f(a['run_rate_wk'])   if a is not None else None,
            'regime':               _s(a['regime']) if (a is not None and 'regime' in a.index) else None,
            'alert_fired':          bool(s['alert_fires']) if s is not None else False,
            'po_ordered':           _f(s['po_ordered']) if (s is not None and s['po_ordered'] > 0) else None,
            'po_received':          _f(s['po_arrives']) if (s is not None and s['po_arrives'] > 0) else None,
            'fresh_stockout':       bool(a['fresh_stockout']) if a is not None else False,
            'weeks_until_stockout': _f(a['weeks_until_stockout']) if a is not None else None,
        })

    simulated_pos = []
    if not sim.empty:
        for _, r in sim[sim['alert_fires']].iterrows():
            if r['po_ordered'] > 0:
                simulated_pos.append({
                    'order_week':   str(pd.Timestamp(r['week_start']).date()),
                    'arrival_week': str(pd.Timestamp(r['po_arrival_week']).date()) if pd.notna(r['po_arrival_week']) else None,
                    'qty':          float(r['po_ordered']),
                })

    try:
        t = alerts_today_idx.loc[(sku, dc)]
        today = {
            'reorder_flag':     bool(t['reorder_flag']),
            'confidence':       str(t['confidence']),
            'on_hand':          _f(t['on_hand_now']),
            'available':        _f(t['available_now']),
            'reorder_point':    _f(t['reorder_point']),
            'run_rate_wk':      _f(t['run_rate_wk']),
            'lead_time_wk':     _f(t['lead_time_wk']),
            'lead_time_source': _s(t['lead_time_source']),
            'suggested_qty':    _f(t['suggested_qty']),
            'suggested_cases':  _f(t['suggested_cases']),
            'weeks_of_cover':   _f(t['weeks_of_cover']),
            'safety_stock':     _f(t['safety_stock']),
            'std_wk':           _f(t['std_wk']),
            'n_clean_weeks':    int(t['n_clean_weeks']) if pd.notna(t['n_clean_weeks']) else None,
            'regime':           _s(t.get('regime')),
            'trend_ratio':      _f(t.get('trend_ratio')),
        }
        metadata = {
            'sku_desc':  _s(t.get('Description')) or '',
            'case_pack': _f(t.get('case_pack')),
            'vendor':    _s(t.get('vendor')) or '',
            'country':   _s(t.get('country')) or '',
        }
    except KeyError:
        today    = None
        metadata = {'sku_desc': '', 'case_pack': None, 'vendor': '', 'country': ''}

    lane_st = status_by_lane.get((sku, dc), {})
    status  = lane_st.get('status', 'active')

    payload = {
        'sku': sku, 'dc': dc,
        'status': status,
        'snapshot_on_hand': lane_st.get('snapshot_on_hand'),
        'hist_run_rate_wk': lane_st.get('hist_run_rate_wk'),
        'series': series,
        'simulated_pos': simulated_pos,
        'today': today,
        'metadata': metadata,
    }
    (LANE_DIR / f'{sku}-{dc}.json').write_text(json.dumps(payload, default=str))
    lanes_written += 1

    n_alerts = int(group['reorder_flag'].sum())
    n_fresh  = int(group['fresh_stockout'].sum())
    n_weeks  = len(group)
    lanes_index.append({
        'sku':              sku,
        'dc':               dc,
        'sku_desc':         metadata['sku_desc'],
        'brand':            '',
        'fresh_rate':       round(n_fresh / n_weeks, 3) if n_weeks else 0.0,
        'n_weeks':          n_weeks,
        'n_alerts':         n_alerts,
        'n_fresh':          n_fresh,
        'today_flag':       today['reorder_flag'] if today else False,
        'today_confidence': today['confidence']   if today else 'low',
        'status':           status,
    })

print(f'wrote {lanes_written} lane JSON files')
(UI_DATA / 'lanes_index.json').write_text(json.dumps(lanes_index, default=str))
print(f'wrote {len(lanes_index)} rows to lanes_index.json')


# ── Backtest summary ────────────────────────────────────────────────────
eval_ = alerts_wf[alerts_wf['confidence'] == 'high'].copy()
eval_['horizon_ok'] = eval_['weeks_until_stockout'] <= 12
tp_fresh = int(((eval_['reorder_flag']) & (eval_['fresh_stockout']) & (eval_['horizon_ok'])).sum())
fp_fresh = int(((eval_['reorder_flag']) & (~eval_['fresh_stockout'])).sum())
fn_fresh = int(((~eval_['reorder_flag']) & (eval_['fresh_stockout'])).sum())
tn_fresh = int(((~eval_['reorder_flag']) & (~eval_['fresh_stockout'])).sum())
prec = tp_fresh / (tp_fresh + fp_fresh) if (tp_fresh + fp_fresh) else 0.0
rec  = tp_fresh / (tp_fresh + fn_fresh) if (tp_fresh + fn_fresh) else 0.0
wus_series = eval_.loc[eval_['reorder_flag'], 'weeks_until_stockout'].dropna()
med  = float(wus_series.median()) if not wus_series.empty else None

flagged_today = alerts_today[alerts_today['reorder_flag']]
summary = {
    'strategies': [{
        'method':               'trend_aware_p99_hybrid',
        'n_rows':               int(len(eval_)),
        'n_healthy':            int(len(eval_[eval_['inv_at_asof'] > 0])),
        'n_flagged':            int(eval_['reorder_flag'].sum()),
        'tp_fresh':             tp_fresh,
        'fp_fresh':             fp_fresh,
        'fn_fresh':             fn_fresh,
        'tn_fresh':             tn_fresh,
        'precision_fresh':      round(prec, 3),
        'recall_fresh':         round(rec, 3),
        'med_warn_wk':          med,
    }],
    'total_lanes':              int(eval_[['ITEMNMBR', 'DC']].drop_duplicates().shape[0]),
    'total_alerts_today':       int(alerts_today['reorder_flag'].sum()),
    'total_alerts_high_conf':   int((flagged_today['confidence'] == 'high').sum()),
    'total_alerts_med_conf':    int((flagged_today['confidence'] == 'medium').sum()),
    'total_alerts_low_conf':    int((flagged_today['confidence'] == 'low').sum()),
}
(UI_DATA / 'backtest_summary.json').write_text(json.dumps(summary, default=str))
print(f'wrote backtest_summary.json: {summary["strategies"][0]}')


# ── Patch alerts_today.json with lane status ────────────────────────────
# Adds `status` per row; suppresses reorder_flag for discontinued lanes so
# they stop showing up as alerts. The lane stays visible in the UI with
# its badge.
alerts_path = UI_DATA / 'alerts_today.json'
if alerts_path.exists() and status_by_lane:
    rows = json.loads(alerts_path.read_text())
    n_suppressed = 0
    for row in rows:
        key = (row.get('ITEMNMBR'), row.get('DC'))
        st  = status_by_lane.get(key, {}).get('status', 'active')
        row['status'] = st
        if st == 'discontinued' and row.get('reorder_flag'):
            row['reorder_flag'] = False
            n_suppressed += 1
    alerts_path.write_text(json.dumps(rows, default=str))
    print(f'patched alerts_today.json: added status to {len(rows)} rows, suppressed {n_suppressed} discontinued alerts')

print('done')
