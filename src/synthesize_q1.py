"""Forward-synthesize missing Q1 2026 sales rows using historical run-rate.

The raw sales export ends 2025-12-31 but the inventory snapshot and PO receipts
extend through ~2026-04-15. Without the missing sales, the weekly inventory
rewind sees a flat plateau from Jan through April. This module fills that gap:
for each lane with a healthy historical run-rate, we synthesize weekly rows
flagged `synthetic=True`. Lanes without a meaningful historical run-rate are
classified as discontinued/inactive and are NOT synthesized.

Public API:
    synthesize_q1_sales(sales, po, inv_snap, dc_map, ...)
        -> (sales_synth_df, lane_status_df)

    classify_lanes(...) runs internally; use `lane_status_df` for UI badges.
"""

from __future__ import annotations

import pandas as pd
import numpy as np


DEFAULT_AS_OF = pd.Timestamp('2025-12-31')
DEFAULT_GAP_END = pd.Timestamp('2026-04-15')
DEFAULT_LOOKBACK_WEEKS = 26


def compute_historical_run_rate(
    sales: pd.DataFrame,
    dc_map: dict,
    end_date: pd.Timestamp = DEFAULT_AS_OF,
    lookback_weeks: int = DEFAULT_LOOKBACK_WEEKS,
) -> pd.DataFrame:
    """Per-(ITEMNMBR, DC) mean weekly QTY_BASE over the lookback window.

    QTY_BASE = QUANTITY_adj * QTYBSUOM, summed by week, then averaged.
    Filters to physical DCs (SF/NJ/LA) via `dc_map`.
    """
    s = sales.copy()
    s['DOCDATE'] = pd.to_datetime(s['DOCDATE'], errors='coerce')
    s['DC'] = s['LOCNCODE'].map(dc_map)
    s = s.dropna(subset=['DC', 'DOCDATE'])
    start = end_date - pd.Timedelta(weeks=lookback_weeks)
    s = s[(s['DOCDATE'] > start) & (s['DOCDATE'] <= end_date)].copy()
    s['QTY_BASE'] = s['QUANTITY_adj'].astype(float) * s['QTYBSUOM'].fillna(1).astype(float)
    s['week'] = s['DOCDATE'].dt.to_period('W-SUN').dt.start_time

    weekly = s.groupby(['ITEMNMBR', 'DC', 'week'], as_index=False)['QTY_BASE'].sum()
    rr = (
        weekly.groupby(['ITEMNMBR', 'DC'])['QTY_BASE']
        .agg(['mean', 'count'])
        .rename(columns={'mean': 'hist_run_rate_wk', 'count': 'hist_n_weeks'})
        .reset_index()
    )
    return rr


def classify_lanes(
    run_rates: pd.DataFrame,
    inv_snap: pd.DataFrame,
    po_gap: pd.DataFrame,
    min_rr_active: float = 5.0,
    gap_end: pd.Timestamp = DEFAULT_GAP_END,
    as_of: pd.Timestamp = DEFAULT_AS_OF,
) -> pd.DataFrame:
    """Classify each (ITEMNMBR, DC) lane into one of: active, inactive,
    discontinued, stocked_out, anomaly.

    - active          : hist_run_rate_wk >= min_rr_active AND snapshot > 0
    - stocked_out     : hist_run_rate_wk >= min_rr_active AND snapshot == 0
    - inactive        : hist_run_rate_wk <  min_rr_active AND snapshot > 0
    - discontinued    : hist_run_rate_wk <  min_rr_active AND snapshot == 0
                        AND no PO receipts in the gap
    - anomaly         : snapshot < 0 or other weirdness
    """
    gap_weeks = int(round((gap_end - as_of).days / 7))
    snap = inv_snap.rename(columns={'Item Number': 'ITEMNMBR', 'On Hand': 'snapshot_on_hand'})
    snap = snap[['ITEMNMBR', 'DC', 'snapshot_on_hand']]

    po_sum = (
        po_gap.groupby(['ITEMNMBR', 'DC'], as_index=False)['QTY Shipped']
        .sum()
        .rename(columns={'QTY Shipped': 'po_in_gap'})
    )

    df = snap.merge(run_rates, on=['ITEMNMBR', 'DC'], how='left') \
             .merge(po_sum, on=['ITEMNMBR', 'DC'], how='left')
    df['hist_run_rate_wk'] = df['hist_run_rate_wk'].fillna(0.0)
    df['hist_n_weeks'] = df['hist_n_weeks'].fillna(0).astype(int)
    df['po_in_gap'] = df['po_in_gap'].fillna(0.0)
    df['gap_weeks'] = gap_weeks
    df['sales_gap_est'] = df['hist_run_rate_wk'] * gap_weeks

    conds = [
        df['snapshot_on_hand'] < 0,
        (df['hist_run_rate_wk'] >= min_rr_active) & (df['snapshot_on_hand'] > 0),
        (df['hist_run_rate_wk'] >= min_rr_active) & (df['snapshot_on_hand'] == 0),
        (df['hist_run_rate_wk'] < min_rr_active) & (df['snapshot_on_hand'] > 0),
        (df['hist_run_rate_wk'] < min_rr_active) & (df['snapshot_on_hand'] == 0),
    ]
    choices = ['anomaly', 'active', 'stocked_out', 'inactive', 'discontinued']
    df['status'] = np.select(conds, choices, default='anomaly')
    return df


def synthesize_q1_sales(
    sales: pd.DataFrame,
    po: pd.DataFrame,
    inv_snap: pd.DataFrame,
    dc_map: dict,
    as_of: pd.Timestamp = DEFAULT_AS_OF,
    gap_end: pd.Timestamp = DEFAULT_GAP_END,
    lookback_weeks: int = DEFAULT_LOOKBACK_WEEKS,
    min_rr_active: float = 5.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build synthetic weekly sales rows for the (as_of, gap_end] window.

    Returns
    -------
    sales_synth : DataFrame with same columns as `sales` plus `synthetic=True`.
        One row per (ITEMNMBR, DC, week) for active lanes; QUANTITY_adj is the
        per-week run-rate estimate in base units (QTYBSUOM=1 so QTY_BASE matches).
    lane_status : DataFrame with per-lane classification and diagnostics.
    """
    sales = sales.copy()
    sales['DOCDATE'] = pd.to_datetime(sales['DOCDATE'], errors='coerce')

    po = po.copy()
    po['Receipt Date'] = pd.to_datetime(po['Receipt Date'], errors='coerce')
    po['DC'] = po['Location Code'].astype(str).map(dc_map)
    po_gap = po[(po['Receipt Date'] > as_of) & (po['Receipt Date'] <= gap_end)] \
        .dropna(subset=['DC']) \
        .rename(columns={'Item Number': 'ITEMNMBR'})

    run_rates = compute_historical_run_rate(sales, dc_map, as_of, lookback_weeks)
    lane_status = classify_lanes(run_rates, inv_snap, po_gap, min_rr_active, gap_end, as_of)

    active = lane_status[lane_status['status'].isin(['active', 'stocked_out'])].copy()
    weeks = pd.date_range(
        start=(as_of + pd.Timedelta(days=1)).to_period('W-SUN').start_time,
        end=gap_end.to_period('W-SUN').start_time,
        freq='W-SUN',
    )
    if len(weeks) == 0:
        raise ValueError('empty week range — check as_of/gap_end')

    dc_inv_map = {v: k for k, v in dc_map.items()}
    rows = []
    for _, lane in active.iterrows():
        sku = lane['ITEMNMBR']
        dc = lane['DC']
        rr = float(lane['hist_run_rate_wk'])
        locncode = dc_inv_map.get(dc)
        if locncode is None or rr <= 0:
            continue
        for w in weeks:
            docdate = w + pd.Timedelta(days=3)
            rows.append({
                'LOCNCODE': str(locncode),
                'SLPRSNID': 'SYNTH',
                'CUSTNMBR': 'SYNTH',
                'CITY': None, 'STATE': None, 'ZIPCODE': None,
                'SOP TYPE': 'SYNTH', 'SOPNUMBE': 'SYNTH',
                'DOCDATE': pd.Timestamp(docdate),
                'ITEMNMBR': sku,
                'ITEMDESC': None,
                'QUANTITY_adj': int(round(rr)),
                'UOFM': 'EACH',
                'QTYBSUOM': 1,
                'XTNDPRCE_adj': 0.0, 'EXTDCOST_adj': 0.0,
                'Customer Type': 'SYNTH', 'Product Type': 'SYNTH',
                'Source_File': 'SYNTH_Q1_2026',
                'Gross_Profit_adj': 0.0, 'Margin_Pct_adj': 0.0,
                'UOM_Price': 0.0, 'Unit_Price_adj': 0.0,
                'synthetic': True,
            })

    sales_synth = pd.DataFrame(rows)
    if 'synthetic' not in sales.columns:
        sales = sales.assign(synthetic=False)

    return sales_synth, lane_status
