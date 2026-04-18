"""Fit price-quantity demand curves per SKU × channel and expose elasticity slopes.

The slope β from `log(qty) = α + β·log(price)` is the price elasticity that
F1 uses to size per-SKU safety stock (`safety_weeks = base + k·|β|`). F2
shows the scatter + fitted curve; this module provides the numeric slope.

Public API:

- ``filter_eligible(sales)`` — drop stockout weeks + non-positive price/qty
  + null channel rows before fitting.

- ``fit_elasticity(sales, *, min_obs=20, min_log_price_iqr=0.1)`` — full
  pipeline that returns one row per (SKU × channel). Low-data cells get
  ``is_low_data=True`` and null slope.

Low-data gating — we refuse to fit when either:
  - n_obs < min_obs (too few observations to trust a slope)
  - log-price IQR < min_log_price_iqr (prices barely vary, any slope would
    be driven by rounding noise, not real elasticity)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

DEFAULT_MIN_OBS = 20
DEFAULT_MIN_LOG_PRICE_IQR = 0.1


def filter_eligible(sales: pd.DataFrame) -> pd.DataFrame:
    """Return rows suitable for a log-log price/qty fit.

    Drops: confirmed stockout weeks, null SALESCHANNEL, non-positive
    Unit_Price_adj, non-positive QTY_BASE. ``is_stockout_week`` is a
    nullable boolean — NA means we never had inv coverage, so we keep
    those rows.
    """
    stockout_mask = sales['is_stockout_week'].fillna(False).astype(bool)
    return sales.loc[
        (~stockout_mask)
        & sales['SALESCHANNEL'].notna()
        & (sales['Unit_Price_adj'] > 0)
        & (sales['QTY_BASE'] > 0)
    ].copy()


def _fit_loglog(sub_df: pd.DataFrame, min_n: int, min_iqr: float) -> pd.Series:
    x = np.log(sub_df['Unit_Price_adj'].to_numpy())
    y = np.log(sub_df['QTY_BASE'].to_numpy())
    n = len(x)
    log_price_iqr = float(np.percentile(x, 75) - np.percentile(x, 25)) if n > 1 else 0.0
    median_price = float(np.exp(np.median(x))) if n else float('nan')

    if n < min_n or log_price_iqr < min_iqr:
        return pd.Series({
            'n_obs': n,
            'log_price_iqr': log_price_iqr,
            'median_price': median_price,
            'slope': float('nan'),
            'intercept': float('nan'),
            'r_squared': float('nan'),
            'is_low_data': True,
            'method': 'log-log',
        })

    slope, intercept = np.polyfit(x, y, 1)
    y_pred = slope * x + intercept
    ss_res = float(np.sum((y - y_pred) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2))
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else float('nan')

    return pd.Series({
        'n_obs': n,
        'log_price_iqr': log_price_iqr,
        'median_price': median_price,
        'slope': float(slope),
        'intercept': float(intercept),
        'r_squared': r_squared,
        'is_low_data': False,
        'method': 'log-log',
    })


def fit_elasticity(
    sales: pd.DataFrame,
    *,
    min_obs: int = DEFAULT_MIN_OBS,
    min_log_price_iqr: float = DEFAULT_MIN_LOG_PRICE_IQR,
) -> pd.DataFrame:
    """Fit per (SKU × channel) log-log elasticity.

    Returns a DataFrame with one row per (ITEMNMBR, SALESCHANNEL) and
    columns: n_obs, log_price_iqr, median_price, slope, intercept,
    r_squared, is_low_data, method, predicted_qty_at_median.
    """
    elig = filter_eligible(sales)
    out = (
        elig.groupby(['ITEMNMBR', 'SALESCHANNEL'])
            .apply(_fit_loglog, min_n=min_obs, min_iqr=min_log_price_iqr, include_groups=False)
            .reset_index()
    )
    out['predicted_qty_at_median'] = np.where(
        out['is_low_data'],
        np.nan,
        np.exp(out['intercept']) * out['median_price'] ** out['slope'],
    )
    return out
