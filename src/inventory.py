"""Reconstruct historical per-SKU-per-DC inventory by rewinding the snapshot.

Anchors at today's `inv_snapshot.On Hand`, then walks backward week by week via
    inv[w] = today_on_hand
           + Sum(sales_signed in (w, today])        # add outflows back
           - Sum(po_in in (w, today])               # undo inflows
           - Sum(xfer_in in (w, today])
           + Sum(xfer_out in (w, today])

All movements are normalized to BASE UNITS before aggregation:
    sales.QTY_BASE     = QUANTITY_adj * QTYBSUOM (per-row, always populated by GP)
    po.QTY Shipped     = already base units (verified against sales totals)
    transfers.QTY_BASE = TRX QTY * pack_lookup(SKU, UOM)
                         fallback chain: (SKU, UOM) -> SKU median -> 1.0

Confidence per (SKU, DC): 'high' iff min(on_hand_est) >= -tolerance, where
    tolerance = max(tolerance_floor, tolerance_pct * |today_on_hand|).
Low-confidence series indicate missing transaction history (returns, unlogged
transfers, assembly/repack) and should be excluded from stockout detection.

Public API:
    build_inv_weekly(sales, po, transfers, inv_snap, dc_map, ...) -> (inv_weekly, meta)
"""

from __future__ import annotations

import numpy as np
import pandas as pd


# ---- UOM normalization ------------------------------------------------------

def learn_uom_pack(sales: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """Learn (SKU, UOM) -> base-per-UOM conversion from sales.

    Returns (per_uom_table, per_sku_fallback).
        per_uom_table   : columns ['ITEMNMBR', 'UOFM_u', 'pack']
        per_sku_fallback: Series indexed by ITEMNMBR, median QTYBSUOM across all UOMs

    UOFM_u is uppercase + stripped so downstream merges are case-insensitive.
    """
    s = sales[['ITEMNMBR', 'UOFM', 'QTYBSUOM']].dropna(subset=['QTYBSUOM']).copy()
    s['UOFM_u'] = s['UOFM'].astype(str).str.upper().str.strip()
    per_uom = (
        s.groupby(['ITEMNMBR', 'UOFM_u'])['QTYBSUOM']
         .median().reset_index().rename(columns={'QTYBSUOM': 'pack'})
    )
    per_sku = sales.groupby('ITEMNMBR')['QTYBSUOM'].median()
    return per_uom, per_sku


def normalize_sales_to_base(sales_phys: pd.DataFrame) -> pd.DataFrame:
    """Add QTY_BASE column = QUANTITY_adj * QTYBSUOM (base units per row)."""
    out = sales_phys.copy()
    out['QTY_BASE'] = (
        out['QUANTITY_adj'].astype(float)
        * out['QTYBSUOM'].fillna(1).astype(float)
    )
    return out


def normalize_transfers_to_base(
    transfers_p: pd.DataFrame,
    per_uom: pd.DataFrame,
    per_sku: pd.Series,
) -> tuple[pd.DataFrame, dict]:
    """Add QTY_BASE column to transfers via (SKU, UOM) -> pack lookup.

    Fallback chain: exact (SKU, UOM) -> per-SKU median -> 1.0.
    Returns (transfers_with_base, coverage_stats).
    """
    out = transfers_p.copy()
    out['UOFM_u'] = out['U Of M'].astype(str).str.upper().str.strip()
    out = out.merge(
        per_uom.rename(columns={'ITEMNMBR': 'Item Number'}),
        on=['Item Number', 'UOFM_u'],
        how='left',
    )
    hit_exact = out['pack'].notna()
    out['pack'] = (
        out['pack']
        .fillna(out['Item Number'].map(per_sku))
        .fillna(1.0)
    )
    out['QTY_BASE'] = out['TRX QTY'].astype(float) * out['pack'].astype(float)

    fb_sku = (~hit_exact) & out['Item Number'].isin(per_sku.index)
    fb_one = (~hit_exact) & (~out['Item Number'].isin(per_sku.index))
    stats = {
        'exact_pct':    float(hit_exact.mean() * 100),
        'sku_fb_pct':   float(fb_sku.mean() * 100),
        'one_fb_pct':   float(fb_one.mean() * 100),
    }
    return out, stats


# ---- Weekly aggregation -----------------------------------------------------

def weekly_sum(
    df: pd.DataFrame,
    date_col: str,
    qty_col: str,
    sku_col: str,
    dc_col: str,
    out_col: str,
) -> pd.DataFrame:
    """Aggregate `qty_col` by (SKU, DC, week_start) using W-SUN weeks."""
    tmp = df[[sku_col, dc_col, date_col, qty_col]].copy()
    tmp.columns = ['SKU', 'DC', 'DATE', 'QTY']
    tmp['DATE'] = pd.to_datetime(tmp['DATE'])
    tmp = tmp.dropna(subset=['DATE'])
    tmp['week_start'] = tmp['DATE'].dt.to_period('W-SUN').dt.start_time
    out = tmp.groupby(['SKU', 'DC', 'week_start'], as_index=False)['QTY'].sum()
    return out.rename(columns={'QTY': out_col})


def _rev_cumsum(s: pd.Series) -> pd.Series:
    return s.iloc[::-1].cumsum().iloc[::-1]


# ---- Top-level pipeline -----------------------------------------------------

def build_inv_weekly(
    sales: pd.DataFrame,
    po: pd.DataFrame,
    transfers: pd.DataFrame,
    inv_snap: pd.DataFrame,
    dc_map: dict,
    tolerance_floor: float = 50.0,
    tolerance_pct: float = 0.10,
) -> tuple[pd.DataFrame, dict]:
    """Rewind today's inventory snapshot weekly back to min(sales.DOCDATE).

    Args:
        sales: sales history with LOCNCODE, DOCDATE, ITEMNMBR, QUANTITY_adj,
            UOFM, QTYBSUOM.
        po: purchase orders with Location Code, Receipt Date, Item Number,
            QTY Shipped (base units).
        transfers: posted internal transfers with TRX Location, Transfer To
            Location, Document Date, Item Number, TRX QTY, U Of M, Document
            Status.
        inv_snap: today's snapshot with Item Number, DC, On Hand.
        dc_map: LOCNCODE (int or str) -> DC string (e.g. {1: 'SF', ...}).
        tolerance_floor: min absolute tolerance for confidence tagging.
        tolerance_pct: fractional tolerance vs today_on_hand.

    Returns:
        (inv_weekly, meta). inv_weekly has columns
            ['ITEMNMBR', 'DC', 'week_start', 'on_hand_est', 'confidence'].
        meta is a dict with anchor/start dates, week count, UOM-coverage stats,
        and confidence counts — useful for audit logs.
    """
    # ---- Step A: normalize DC codes + keep physical DCs only ----------------
    sales = sales.copy()
    sales['DC'] = sales['LOCNCODE'].map(dc_map)
    sales_phys = sales.dropna(subset=['DC']).copy()

    po = po.copy()
    po['DC'] = po['Location Code'].map(dc_map)
    po_phys = po.dropna(subset=['DC']).copy()

    transfers_p = transfers[transfers['Document Status'] == 'Posted'].copy()
    transfers_p['DC_FROM'] = transfers_p['TRX Location'].map(dc_map)
    transfers_p['DC_TO'] = transfers_p['Transfer To Location'].map(dc_map)
    transfers_p = transfers_p.dropna(subset=['DC_FROM', 'DC_TO'])

    # ---- Step B: UOM normalization -> base units ----------------------------
    sales_phys = normalize_sales_to_base(sales_phys)
    per_uom, per_sku = learn_uom_pack(sales)
    transfers_p, uom_stats = normalize_transfers_to_base(transfers_p, per_uom, per_sku)

    # ---- Step C: weekly grid ------------------------------------------------
    # Grid extends one week past today so the final Monday has zero movement
    # ahead and on_hand_est == today_on_hand exactly (identity check).
    today = pd.to_datetime(sales_phys['DOCDATE']).max().normalize()
    start = pd.to_datetime(sales_phys['DOCDATE']).min().normalize()
    weeks = pd.date_range(
        start.to_period('W-SUN').start_time,
        today.to_period('W-SUN').start_time + pd.Timedelta(weeks=1),
        freq='W-MON',
    )

    # ---- Step D: weekly movement tables (all base units) --------------------
    sales_w = weekly_sum(sales_phys, 'DOCDATE', 'QTY_BASE', 'ITEMNMBR', 'DC', 'sales_out')
    po_w    = weekly_sum(po_phys, 'Receipt Date', 'QTY Shipped', 'Item Number', 'DC', 'po_in')
    tin_w   = weekly_sum(transfers_p, 'Document Date', 'QTY_BASE', 'Item Number', 'DC_TO',   'xfer_in')
    tout_w  = weekly_sum(transfers_p, 'Document Date', 'QTY_BASE', 'Item Number', 'DC_FROM', 'xfer_out')

    # ---- Step E: (SKU, DC, week) grid + merge movements ---------------------
    sku_dc = inv_snap[['Item Number', 'DC', 'On Hand']].rename(
        columns={'Item Number': 'SKU', 'On Hand': 'today_on_hand'}
    )
    grid = sku_dc.merge(pd.DataFrame({'week_start': weeks}), how='cross')
    for w in (sales_w, po_w, tin_w, tout_w):
        grid = grid.merge(w, on=['SKU', 'DC', 'week_start'], how='left')
    for c in ('sales_out', 'po_in', 'xfer_in', 'xfer_out'):
        grid[c] = grid[c].fillna(0.0)

    # ---- Step F: reverse cumsum -> rewind -----------------------------------
    grid = grid.sort_values(['SKU', 'DC', 'week_start']).reset_index(drop=True)
    for col in ('sales_out', 'po_in', 'xfer_in', 'xfer_out'):
        grid[f'cum_{col}'] = grid.groupby(['SKU', 'DC'])[col].transform(_rev_cumsum)

    grid['on_hand_est'] = (
        grid['today_on_hand']
        + grid['cum_sales_out']
        - grid['cum_po_in']
        - grid['cum_xfer_in']
        + grid['cum_xfer_out']
    )

    # ---- Step G: confidence tag per (SKU, DC) -------------------------------
    conf = grid.groupby(['SKU', 'DC']).agg(
        min_est=('on_hand_est', 'min'),
        today_on_hand=('today_on_hand', 'first'),
    ).reset_index()
    conf['tolerance'] = np.maximum(
        tolerance_floor, tolerance_pct * conf['today_on_hand'].abs()
    )
    conf['confidence'] = np.where(
        conf['min_est'] >= -conf['tolerance'], 'high', 'low'
    )
    grid = grid.merge(conf[['SKU', 'DC', 'confidence']], on=['SKU', 'DC'], how='left')

    inv_weekly = (
        grid[['SKU', 'DC', 'week_start', 'on_hand_est', 'confidence']]
        .rename(columns={'SKU': 'ITEMNMBR'})
        .reset_index(drop=True)
    )

    meta = {
        'anchor_today':    today,
        'rewind_start':    weeks.min(),
        'rewind_end':      weeks.max(),
        'week_count':      len(weeks),
        'tolerance_pct':   tolerance_pct,
        'tolerance_floor': tolerance_floor,
        'uom_coverage':    uom_stats,
        'confidence_counts': conf['confidence'].value_counts().to_dict(),
    }
    return inv_weekly, meta
