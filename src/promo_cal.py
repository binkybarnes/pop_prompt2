"""Build (Customer x Brand x YearMonth) promo calendar from TPR chargebacks.

For rows where the Item Description embeds an MM/YY (e.g. "TPR 03/24"), parse it
as the promo month. For the rest, subtract the median billing lag from
Document Date as a fallback. Covers 100% of rows with a valid Document Date
in practice (regex alone ~98%).

Public API:
    extract_promo_ym(desc) -> pd.Period | None
    fit_median_lag(tpr) -> float
    impute_promo_ym(tpr, median_lag_days) -> pd.DataFrame
    build_promo_calendar(tpr) -> (promo_cal_df, median_lag_days)
"""

from __future__ import annotations

import re

import pandas as pd

# MM/YY with 20xx years only. Word-boundary so we don't chew into longer numbers.
_MMYY_RE = re.compile(r'\b(0[1-9]|1[0-2])/(2[0-9])\b')


def extract_promo_ym(desc) -> pd.Period | None:
    """Return pd.Period('YYYY-MM', 'M') if desc embeds an MM/YY, else None."""
    if pd.isna(desc):
        return None
    m = _MMYY_RE.search(str(desc))
    if not m:
        return None
    mm, yy = m.group(1), m.group(2)
    return pd.Period(f'20{yy}-{mm}', freq='M')


def _estimate_promo_ym_from_doc(doc_date, lag_days: float):
    if pd.isna(doc_date):
        return pd.NaT
    est = pd.to_datetime(doc_date) - pd.Timedelta(days=lag_days)
    return pd.Period(est, freq='M')


def fit_median_lag(tpr: pd.DataFrame) -> float:
    """Median (Document Date - promo_start) in days, fit on rows with a regex-extractable MM/YY.

    Requires columns: 'Item Description', 'Document Date'.
    """
    promo_ym_raw = tpr['Item Description'].apply(extract_promo_ym)
    mask = promo_ym_raw.notna()
    promo_start = promo_ym_raw[mask].apply(lambda p: p.to_timestamp())
    doc_dates = pd.to_datetime(tpr.loc[mask, 'Document Date'])
    lag_days = (doc_dates - promo_start).dt.days
    return float(lag_days.median())


def impute_promo_ym(tpr: pd.DataFrame, median_lag_days: float) -> pd.DataFrame:
    """Return a copy of tpr with promo_ym_raw, doc_ym, and promo_ym columns added.

    promo_ym = promo_ym_raw where present, else Document Date minus median_lag_days
    rounded down to the enclosing month.
    Requires columns: 'Item Description', 'Document Date'.
    """
    out = tpr.copy()
    out['promo_ym_raw'] = out['Item Description'].apply(extract_promo_ym)
    out['doc_ym'] = pd.to_datetime(out['Document Date']).dt.to_period('M')
    out['promo_ym'] = out['promo_ym_raw']
    need_fallback = out['promo_ym'].isna()
    out.loc[need_fallback, 'promo_ym'] = (
        out.loc[need_fallback, 'Document Date']
           .apply(lambda d: _estimate_promo_ym_from_doc(d, median_lag_days))
    )
    return out


def build_promo_calendar(tpr: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """Fit lag, impute promo_ym, and return unique (CUSTNMBR, brand, promo_ym) + lag.

    Requires columns: 'Item Description', 'Document Date', 'Customer Number', 'brand'.
    Output column `promo_ym` is pd.Period at monthly frequency; cast to str before parquet.
    """
    median_lag_days = fit_median_lag(tpr)
    tagged = impute_promo_ym(tpr, median_lag_days)
    promo_cal = (
        tagged.dropna(subset=['Customer Number', 'brand', 'promo_ym'])
              [['Customer Number', 'brand', 'promo_ym']]
              .drop_duplicates()
              .reset_index(drop=True)
    )
    promo_cal['Customer Number'] = promo_cal['Customer Number'].astype(str)
    promo_cal = promo_cal.rename(columns={'Customer Number': 'CUSTNMBR'})
    return promo_cal, median_lag_days
