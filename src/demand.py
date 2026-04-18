"""Aggregate clean transactions into organic run rate per SKU x channel x DC.

Two public entry points:

- ``aggregate_weekly(sales, *, channel_col='SALESCHANNEL', dc_col='DC')`` →
  weekly panel per (SKU, channel, DC, week_start). The granular artifact
  F2 uses for scatter / trend-stack curves.

- ``compute_organic_run_rate(weekly, *, low_data_weeks=8)`` → summary per
  (SKU, channel, DC) with ``mean_weekly_qty``, ``n_clean_weeks``, and the
  ``is_low_data`` flag F1 gates auto-alerts on.

``build_clean_demand(sales, ...)`` wraps both for callers that just want
the two artifacts in one shot.

Input sales DataFrame is expected to carry ``is_clean_demand`` (produced
by ``src.tagging.tag_transactions``) and ``SALESCHANNEL`` (produced by
``src.channel.attach_channel``), along with ``ITEMNMBR``, ``DC``,
``week_start``, ``QTY_BASE``, ``XTNDPRCE_adj``, ``Unit_Price_adj``.

Rows with null ``DC`` are dropped from both outputs. null DC corresponds
to Shopify (E1), Weee (W), Returns (ZD), and a handful of U/L codes —
none of which belong in F1's per-DC reorder math.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_LOW_DATA_WEEKS = 8


def _weighted_unit_price(g: pd.DataFrame) -> float:
    qty = g['QTY_BASE'].to_numpy()
    prc = g['Unit_Price_adj'].to_numpy()
    mask = (qty > 0) & np.isfinite(prc) & (prc > 0)
    if not mask.any():
        return float('nan')
    return float(np.average(prc[mask], weights=qty[mask]))


def aggregate_weekly(
    sales: pd.DataFrame,
    *,
    channel_col: str = 'SALESCHANNEL',
    dc_col: str = 'DC',
) -> pd.DataFrame:
    """Filter to clean + DC-assigned rows and aggregate to a weekly panel.

    Returns one row per (ITEMNMBR, channel, DC, week_start) with:
      qty_base, revenue, n_txn, unit_price_wt
    """
    mask = sales['is_clean_demand'] & sales[channel_col].notna() & sales[dc_col].notna()
    clean = sales.loc[mask].copy()

    keys = ['ITEMNMBR', channel_col, dc_col, 'week_start']
    grp = clean.groupby(keys, dropna=False)
    weekly = grp.agg(
        qty_base=('QTY_BASE', 'sum'),
        revenue=('XTNDPRCE_adj', 'sum'),
        n_txn=('QTY_BASE', 'size'),
    ).reset_index()

    wp = (grp.apply(_weighted_unit_price, include_groups=False)
             .rename('unit_price_wt').reset_index())
    weekly = weekly.merge(wp, on=keys, how='left')
    return weekly


def compute_organic_run_rate(
    weekly: pd.DataFrame,
    *,
    channel_col: str = 'SALESCHANNEL',
    dc_col: str = 'DC',
    low_data_weeks: int = DEFAULT_LOW_DATA_WEEKS,
) -> pd.DataFrame:
    """Collapse a weekly panel into one summary row per (SKU, channel, DC).

    ``mean_weekly_qty`` is computed over weeks that actually had clean
    sales — zero-weeks are NOT imputed. Treating a gap as zero demand
    vs. treating it as missing is a choice F1 should make per SKU.
    """
    keys = ['ITEMNMBR', channel_col, dc_col]
    summary = (
        weekly.groupby(keys)
              .agg(
                  n_clean_weeks=('week_start', 'nunique'),
                  mean_weekly_qty=('qty_base', 'mean'),
                  std_weekly_qty=('qty_base', 'std'),
                  total_qty=('qty_base', 'sum'),
                  first_week=('week_start', 'min'),
                  last_week=('week_start', 'max'),
              )
              .reset_index()
    )
    summary['cv_weekly'] = summary['std_weekly_qty'] / summary['mean_weekly_qty']
    summary['is_low_data'] = summary['n_clean_weeks'] < low_data_weeks
    return summary


def build_clean_demand(
    sales: pd.DataFrame,
    *,
    channel_col: str = 'SALESCHANNEL',
    dc_col: str = 'DC',
    low_data_weeks: int = DEFAULT_LOW_DATA_WEEKS,
) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """One-shot helper: returns (weekly, summary, meta)."""
    weekly = aggregate_weekly(sales, channel_col=channel_col, dc_col=dc_col)
    summary = compute_organic_run_rate(
        weekly,
        channel_col=channel_col,
        dc_col=dc_col,
        low_data_weeks=low_data_weeks,
    )
    meta = {
        'low_data_weeks': low_data_weeks,
        'n_weekly_rows': len(weekly),
        'n_summary_cells': len(summary),
        'n_low_data_cells': int(summary['is_low_data'].sum()),
    }
    return weekly, summary, meta
