"""Build (Customer x Brand x YearMonth) promo calendar from TPR chargebacks.

For rows where the Item Description embeds an MM/YY (e.g. "TPR 03/24"), parse it
as the promo month. For the rest, subtract the median billing lag from
Document Date as a fallback. Covers 100% of rows with a valid Document Date
in practice (regex alone ~98%).

The raw chargeback file is NOT pure TPR — cause code `CRED02` bundles real
scan-downs with publication / shelf-talker / catalog / trade-show / admin
fees that don't change the invoice price. ``filter_true_tpr`` keeps only
rows that describe a per-unit price cut so downstream ``is_promo`` tagging
fires on real promo windows, not marketing invoices.

Public API:
    classify_chargeback(desc, cause_code) -> str  # 'tpr' | 'fee' | 'other'
    filter_true_tpr(tpr) -> pd.DataFrame
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

# Per-unit price-cut signals in the Item Description. Any match qualifies a
# chargeback as a real TPR (unless FEE_ONLY also matches and overrides).
_PRICE_KW = re.compile(
    r'price[ -]?cut'
    r'|scan[ -]?down'
    r'|scan[ -]?back'
    r'|scan[ -]?bill(?:back)?'
    r'|\bscan\b'
    r'|bill[ -]?back'
    r'|\btpr\b'
    r'|\brebate\b'
    r'|\bin[ -]?ad\b'
    r'|\d+\s*%\s*(?:off|promo)'
    r'|\$\s*\d+(?:\.\d+)?\s*x\s*\d+\s*@'
    r'|\bppf\b'
    r'|price\s+adjust'
    r'|price\s+reduction',
    re.I,
)

# Fee-only signals — marketing / placement / admin chargebacks that do NOT
# change invoice price. A row matching FEE_ONLY but not PRICE_KW is dropped.
_FEE_ONLY_KW = re.compile(
    r'publication\s+fee'
    r'|shelf\s+talker'
    r'|consumer\s+catalog'
    r'|inventory\s+management\s+fee'
    r'|trade\s+show'
    r'|front\s+end\s+kit'
    r'|front\s+end\s+specials?'
    r'|fsa/hsa'
    r'|online\s+ad'
    r'|admin\s+fee'
    r'|insertion\s+fee'
    r'|end\s+cap'
    r'|\baccrual\b'
    r'|distributor\s+charges?'
    r'|ecomm\s+fee'
    r'|advertising\s+discount\s+quarterly'
    r'|circulars?'
    r'|thoughtspot'
    r'|ideashare'
    r'|hot\s+price\s+program'
    r'|full\s+page'
    r'|\bflyer\b'
    r'|search\s+boost'
    r'|natural\s+connections',
    re.I,
)

# CRED03 = retail TPR scan-down. Every CRED03 row is a real TPR even when the
# description is terse (e.g. "Target Initiated Circle") and the keyword scan
# misses it. Keep these unconditionally.
_TPR_ONLY_CAUSE_CODES = frozenset({'CRED03'})


def classify_chargeback(desc: object, cause_code: object) -> str:
    """Return 'tpr', 'fee', or 'other' for a chargeback row.

    Precedence: a row is 'fee' only if FEE_ONLY_KW fires AND PRICE_KW does
    not. CRED03 is always 'tpr' regardless of description. Otherwise we
    require a PRICE_KW match.
    """
    s = '' if pd.isna(desc) else str(desc)
    has_price = bool(_PRICE_KW.search(s))
    has_fee = bool(_FEE_ONLY_KW.search(s))
    if has_fee and not has_price:
        return 'fee'
    if cause_code in _TPR_ONLY_CAUSE_CODES:
        return 'tpr'
    if has_price:
        return 'tpr'
    return 'other'


def filter_true_tpr(tpr: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows that represent real per-unit price cuts.

    Drops fee-only rows (publication / shelf-talker / trade-show / admin)
    and rows whose cause code + description give no signal that a price
    cut actually happened.
    """
    kinds = [
        classify_chargeback(d, c)
        for d, c in zip(tpr['Item Description'], tpr['Cause Code'])
    ]
    mask = pd.Series(kinds, index=tpr.index) == 'tpr'
    return tpr.loc[mask].copy()


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

    Applies ``filter_true_tpr`` first so the calendar only contains real
    price-cut events, not marketing / placement fees.

    Requires columns: 'Item Description', 'Document Date', 'Customer Number',
    'brand', 'Cause Code'. Output column `promo_ym` is pd.Period at monthly
    frequency; cast to str before parquet.
    """
    real_tpr = filter_true_tpr(tpr)
    median_lag_days = fit_median_lag(real_tpr)
    tagged = impute_promo_ym(real_tpr, median_lag_days)
    promo_cal = (
        tagged.dropna(subset=['Customer Number', 'brand', 'promo_ym'])
              [['Customer Number', 'brand', 'promo_ym']]
              .drop_duplicates()
              .reset_index(drop=True)
    )
    promo_cal['Customer Number'] = promo_cal['Customer Number'].astype(str)
    promo_cal = promo_cal.rename(columns={'Customer Number': 'CUSTNMBR'})
    return promo_cal, median_lag_days
