"""Tag sales transactions with demand-quality flags.

Every sales row gets four boolean flags that tell the F1 forecaster which
rows reflect "clean" demand and which are polluted:

    is_promo            : customer × brand × month matches TPR chargeback calendar
    is_markdown         : Unit_Price_adj < factor × (SKU × channel) median price
                          — per-channel denominator avoids HF false positives
                          (their baseline is structurally below pooled median)
                          and MM false negatives (HF drags pooled median down
                          so real MM markdowns slip through).
    is_stockout_week    : on_hand_est <= 0 at week_start (strict, high-conf only)
    is_lost_demand_week : low_stock_week AND cust_below_normal
                          — detects the prompt's "ordered 1,000, shipped 500"
                          scenario where POP ran out and negotiated the order
                          down. Both halves are themselves kept as columns.

    is_clean_demand     : none of the above fire (what the forecaster ingests)

Flags with inventory dependencies (`is_stockout_week`, `is_lost_demand_week`,
`low_stock_week`) are nullable boolean — NA where `inv_weekly` has no row for
that (SKU, DC, week_start).

Public API:
    tag_transactions(sales, promo_cal, inv_weekly, ...) -> (sales_tagged, meta)
"""

from __future__ import annotations

import pandas as pd


# Sales LOCNCODE -> DC string (matches inv_weekly.DC from src.inventory).
DEFAULT_DC_MAP = {'1': 'SF', '2': 'NJ', '3': 'LA', 1: 'SF', 2: 'NJ', 3: 'LA'}


# ---- Per-flag taggers -------------------------------------------------------

def tag_promo(sales: pd.DataFrame, promo_cal: pd.DataFrame) -> pd.DataFrame:
    """Exact (CUSTNMBR, brand, sale_ym) match against promo_cal -> is_promo."""
    promo_keys = promo_cal.assign(is_promo=True)
    out = sales.merge(
        promo_keys,
        left_on=['CUSTNMBR', 'brand', 'sale_ym'],
        right_on=['CUSTNMBR', 'brand', 'promo_ym'],
        how='left',
    )
    # Left-merge turns bool into object; cast back so ~is_promo works as a mask.
    out['is_promo'] = out['is_promo'].fillna(False).astype(bool)
    return out.drop(columns=['promo_ym'])


def tag_markdown(
    sales: pd.DataFrame,
    factor: float,
    channel_col: str = 'SALESCHANNEL',
    min_n: int = 5,
) -> pd.DataFrame:
    """Unit_Price_adj < factor × (SKU × channel) median -> is_markdown.

    Medians are computed on non-promo, positive-price rows so a SKU that's
    frequently discounted doesn't anchor its own "normal" price low.

    Per-(SKU × channel) median, not pooled across channels: MM, AM, HF often
    price the same SKU at structurally different tiers (e.g., HF pays ~14%
    below pooled median as a rule; AM prices Tiger Balm above MM). A pooled
    median produces HF false positives and MM false negatives. Per-channel
    medians adapt to each channel's own baseline.

    Falls back to pooled SKU median when a (SKU × channel) cell has < min_n
    non-promo rows (too noisy to trust). Rows whose channel_col is NA (a few
    salespersons missing from the key) also fall back.

    Adds columns:
        sku_median_price   : pooled SKU median (kept for reference / diagnostics)
        markdown_denom     : the actual denominator used (per-channel or pooled)
        markdown_threshold : factor * markdown_denom
        is_markdown        : bool
    """
    base = sales[(~sales['is_promo']) & (sales['Unit_Price_adj'] > 0)]

    # Pooled SKU median — fallback denominator.
    sku_median = base.groupby('ITEMNMBR')['Unit_Price_adj'].median()

    # Per-(SKU × channel) median, gated by MIN_N.
    sc_stats = (
        base.groupby(['ITEMNMBR', channel_col])['Unit_Price_adj']
            .agg(sc_median='median', sc_n='size')
            .reset_index()
    )
    sc_stats = sc_stats[sc_stats['sc_n'] >= min_n][['ITEMNMBR', channel_col, 'sc_median']]

    out = sales.copy()
    out['sku_median_price'] = out['ITEMNMBR'].map(sku_median)
    out = out.merge(sc_stats, on=['ITEMNMBR', channel_col], how='left')
    out['markdown_denom']     = out['sc_median'].fillna(out['sku_median_price'])
    out['markdown_threshold'] = out['markdown_denom'] * factor
    out['is_markdown'] = (
        (out['Unit_Price_adj'] > 0)
        & (out['Unit_Price_adj'] < out['markdown_threshold'])
        & out['markdown_denom'].notna()
    )
    return out.drop(columns=['sc_median'])


def tag_stockout_week(sales: pd.DataFrame, inv_weekly: pd.DataFrame) -> pd.DataFrame:
    """Join inv_weekly, flag on_hand_est <= 0 on high-confidence series.

    Adds columns: week_on_hand, inv_confidence, is_stockout_week (nullable bool).
    NA when the (SKU, DC, week_start) has no inv_weekly row (E1/W/ZD or SKUs
    missing from the snapshot).
    """
    out = sales.merge(
        inv_weekly.rename(columns={'on_hand_est': 'week_on_hand',
                                   'confidence':  'inv_confidence'}),
        on=['ITEMNMBR', 'DC', 'week_start'],
        how='left',
    )
    out['is_stockout_week'] = (
        (out['week_on_hand'] <= 0)
        & (out['inv_confidence'] == 'high')
    )
    out['is_stockout_week'] = out['is_stockout_week'].where(
        out['week_on_hand'].notna(), other=pd.NA,
    )
    return out


def tag_lost_demand_week(
    sales: pd.DataFrame,
    cover_k: float,
    order_f: float,
    min_n: int,
) -> pd.DataFrame:
    """Flag rows where POP likely shorted the customer because SF/NJ/LA ran out.

    Two conditions must both hold (AND):
        low_stock_week    : week_on_hand < cover_k × typical weekly base sales
                            for the (SKU, DC), on a high-confidence row.
                            Typical weekly = median of non-promo weekly base
                            sales (keeping stockout weeks in the sample is
                            fine because we use median, not mean).
        cust_below_normal : QTY_BASE < order_f × customer's median base order
                            qty for this SKU. Only trust the median on
                            >= min_n orders (else noisy).

    Adds: QTY_BASE (if not already present), typical_weekly_base, low_stock_week,
          cust_median_qty, cust_below_normal, is_lost_demand_week (nullable bool).
    """
    out = sales.copy()
    if 'QTY_BASE' not in out.columns:
        out['QTY_BASE'] = (
            out['QUANTITY_adj'].astype(float)
            * out['QTYBSUOM'].fillna(1).astype(float)
        )

    # (a) Typical weekly base sales per (SKU, DC) from non-promo rows
    weekly_sku_dc = (
        out.loc[~out['is_promo']]
           .groupby(['ITEMNMBR', 'DC', 'week_start'])['QTY_BASE']
           .sum().reset_index()
    )
    typical_weekly = (
        weekly_sku_dc.groupby(['ITEMNMBR', 'DC'])['QTY_BASE']
                     .median().rename('typical_weekly_base').reset_index()
    )
    out = out.merge(typical_weekly, on=['ITEMNMBR', 'DC'], how='left')

    low_stock = (
        out['week_on_hand'].notna()
        & out['typical_weekly_base'].notna()
        & (out['week_on_hand'] < cover_k * out['typical_weekly_base'])
        & (out['inv_confidence'] == 'high')
    )
    out['low_stock_week'] = low_stock.where(out['week_on_hand'].notna(), other=pd.NA)

    # (b) Customer median base order qty per (CUSTNMBR, ITEMNMBR), >= min_n orders
    cust_agg = (
        out.groupby(['CUSTNMBR', 'ITEMNMBR'])['QTY_BASE']
           .agg(cust_median_qty='median', cust_n='size')
           .reset_index()
    )
    cust_agg = cust_agg[cust_agg['cust_n'] >= min_n]
    out = out.merge(
        cust_agg[['CUSTNMBR', 'ITEMNMBR', 'cust_median_qty']],
        on=['CUSTNMBR', 'ITEMNMBR'], how='left',
    )

    out['cust_below_normal'] = (
        out['cust_median_qty'].notna()
        & (out['QTY_BASE'] < order_f * out['cust_median_qty'])
    )

    out['is_lost_demand_week'] = (
        (out['low_stock_week'] == True)
        & (out['cust_below_normal'] == True)
    )
    out['is_lost_demand_week'] = out['is_lost_demand_week'].where(
        out['low_stock_week'].notna() & out['cust_median_qty'].notna(),
        other=pd.NA,
    )
    return out


# ---- Top-level pipeline -----------------------------------------------------

def tag_transactions(
    sales: pd.DataFrame,
    promo_cal: pd.DataFrame,
    inv_weekly: pd.DataFrame,
    dc_map: dict | None = None,
    markdown_factor: float = 0.85,
    markdown_channel_col: str = 'SALESCHANNEL',
    markdown_min_n: int = 5,
    lost_demand_cover_k: float = 1.0,
    lost_demand_order_f: float = 0.70,
    lost_demand_min_n: int = 3,
) -> tuple[pd.DataFrame, dict]:
    """Add the four demand-quality flags + is_clean_demand to sales.

    Args:
        sales: sales_with_brand from step 02, with SALESCHANNEL already
            attached (see src.channel.attach_channel). Needs CUSTNMBR, brand,
            DOCDATE, LOCNCODE, ITEMNMBR, QUANTITY_adj, QTYBSUOM, Unit_Price_adj,
            SALESCHANNEL.
        promo_cal: promo calendar from step 03 (CUSTNMBR × brand × promo_ym).
            promo_ym should be Period[M]; caller handles string round-trip.
        inv_weekly: per-SKU-per-DC weekly on-hand from step 04 (ITEMNMBR, DC,
            week_start, on_hand_est, confidence).
        dc_map: LOCNCODE -> DC string mapping (defaults to SF/NJ/LA).
        markdown_factor: is_markdown cutoff as fraction of (SKU × channel)
            median price. Default 0.85 (15% off) is calibrated to where
            customer qty-per-order starts jumping above baseline (≥ 2.6×
            normal qty at 10–20% below median; see 05b experiment).
        markdown_channel_col: column name holding the channel code (MM/AM/HF).
        markdown_min_n: min rows per (SKU, channel) to trust the per-channel
            median. Below that the row falls back to the pooled SKU median.
        lost_demand_cover_k: low_stock_week fires if week_on_hand < K × typical
            weekly base sales. Lower = more conservative.
        lost_demand_order_f: cust_below_normal fires if order < F × cust median.
        lost_demand_min_n: minimum orders per (customer, SKU) to trust the
            median. Below this the row gets NA rather than a false negative.

    Returns:
        (sales_tagged, meta). Row count equals len(sales). meta is a dict of
        flag counts + NA counts useful for audit logs and notebook summaries.
    """
    dc_map = dc_map or DEFAULT_DC_MAP

    # ---- Normalize keys -----------------------------------------------------
    out = sales.copy()
    out['DOCDATE']    = pd.to_datetime(out['DOCDATE'])
    out['sale_ym']    = out['DOCDATE'].dt.to_period('M')
    out['DC']         = out['LOCNCODE'].map(dc_map)
    out['week_start'] = out['DOCDATE'].dt.to_period('W-SUN').dt.start_time
    out['QTY_BASE']   = (
        out['QUANTITY_adj'].astype(float) * out['QTYBSUOM'].fillna(1).astype(float)
    )

    # ---- Per-flag stages ----------------------------------------------------
    out = tag_promo(out, promo_cal)
    out = tag_markdown(
        out,
        factor=markdown_factor,
        channel_col=markdown_channel_col,
        min_n=markdown_min_n,
    )
    out = tag_stockout_week(out, inv_weekly)
    out = tag_lost_demand_week(
        out,
        cover_k=lost_demand_cover_k,
        order_f=lost_demand_order_f,
        min_n=lost_demand_min_n,
    )

    # ---- Clean-demand roll-up ----------------------------------------------
    # NA flags are treated as False for the roll-up: we keep the row as clean
    # unless we have positive evidence it's polluted.
    out['is_clean_demand'] = (
        (~out['is_promo'])
        & (~out['is_markdown'])
        & (out['is_stockout_week'].fillna(False) == False)
        & (out['is_lost_demand_week'].fillna(False) == False)
    )

    meta = {
        'n_rows': len(out),
        'is_promo_true':            int(out['is_promo'].sum()),
        'is_markdown_true':         int(out['is_markdown'].sum()),
        'is_stockout_week_true':    int((out['is_stockout_week'] == True).sum()),
        'is_stockout_week_na':      int(out['is_stockout_week'].isna().sum()),
        'is_lost_demand_week_true': int((out['is_lost_demand_week'] == True).sum()),
        'is_lost_demand_week_na':   int(out['is_lost_demand_week'].isna().sum()),
        'low_stock_week_true':      int((out['low_stock_week'] == True).sum()),
        'cust_below_normal_true':   int(out['cust_below_normal'].sum()),
        'is_clean_demand_true':     int(out['is_clean_demand'].sum()),
        'markdown_factor':          markdown_factor,
        'markdown_channel_col':     markdown_channel_col,
        'markdown_min_n':           markdown_min_n,
        'lost_demand_cover_k':      lost_demand_cover_k,
        'lost_demand_order_f':      lost_demand_order_f,
        'lost_demand_min_n':        lost_demand_min_n,
    }
    return out, meta
