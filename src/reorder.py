"""Per (SKU × DC) reorder-point math + alert table.

Drives F1. Given weekly clean demand, an inventory snapshot, and item-master
metadata, produce one row per (SKU × DC) with:

    reorder_point  = run_rate_wk × lead_time_wk + safety_stock
    safety_stock   = Z × std_wk × sqrt(lead_time_wk)            (95% service)
    suggested_qty  = max(0, reorder_point + forward_cover × run_rate − avail)
                     rounded up to case pack
    reorder_flag   = available_now < reorder_point

Why CV-based safety stock and not elasticity-based:
  The original feature_tree_v2 spec called for ``safety_weeks = base + k·|β|``.
  Since we discovered that a subset of customers (MRE800A, MWA662A) run
  off-invoice TPRs — the chargeback rebates the price but ``Unit_Price_adj``
  stays flat — the elasticity slope β under-estimates real promo
  responsiveness for those customers. Using weekly std directly avoids
  compounding that bias. See notes/status.md for the open question.

Public API:
    parse_lead_time_weeks(val) -> (float | None, bool)
    parse_case_pack(val) -> int
    compute_dc_stats(weekly) -> pd.DataFrame
    prepare_item_master(im) -> pd.DataFrame
    build_reorder_alerts(weekly, inv, im, **tunables) -> pd.DataFrame
"""

from __future__ import annotations

import math
import re

import numpy as np
import pandas as pd

SERVICE_LEVEL_Z = 1.65        # 95% service level under normal demand
FORWARD_COVER_WEEKS = 4       # weeks of post-arrival coverage to order up to
DEFAULT_LEAD_WEEKS = 13       # 3 months — matches modal Lead Time
MONTHS_TO_WEEKS = 4.33        # 365.25 / 12 / 7
MIN_WEEKS_FOR_HIGH = 8        # same low-data threshold as organic_run_rate

# Item-master Lead Time is freeform: "3 months", "3-4mths", "3~4wks", "2.5",
# "Half a year or more". Rules:
#   - ranges -> take the upper bound (conservative for reorder)
#   - bare numbers -> months (Tiger Balm / POP SKUs are ocean-freighted from
#     China / Singapore, so "2.5" means months, not weeks)
#   - explicit unit keyword wins over defaults
_HALF_YEAR_RE = re.compile(r'half\s+a?\s*year', re.I)
_RANGE_RE = re.compile(r'(\d+(?:\.\d+)?)\s*[-~]\s*(\d+(?:\.\d+)?)')
_SINGLE_RE = re.compile(r'(\d+(?:\.\d+)?)')
_UNIT_WK = re.compile(r'wk|week', re.I)
_UNIT_MO = re.compile(r'mth|month|mo\b', re.I)


def parse_lead_time_weeks(val) -> tuple[float | None, bool]:
    """Return (weeks, was_parsed).

    ``weeks`` is None when no number was extractable; callers should fall
    back to ``DEFAULT_LEAD_WEEKS``. ``was_parsed`` distinguishes "we
    couldn't read it" from "we read it and it said 0".
    """
    if pd.isna(val):
        return None, False
    s = str(val)
    if _HALF_YEAR_RE.search(s):
        return 26.0, True

    m = _RANGE_RE.search(s)
    if m:
        n = float(m.group(2))
    else:
        m = _SINGLE_RE.search(s)
        if not m:
            return None, False
        n = float(m.group(1))

    if _UNIT_WK.search(s):
        return n, True
    if _UNIT_MO.search(s):
        return n * MONTHS_TO_WEEKS, True
    return n * MONTHS_TO_WEEKS, True


def parse_case_pack(val) -> int:
    """``"BOX40"`` / ``"24"`` / ``"60"`` -> int. Default 1 when unparseable."""
    if pd.isna(val):
        return 1
    m = re.search(r'(\d+)', str(val))
    return int(m.group(1)) if m else 1


def compute_dc_stats(
    weekly: pd.DataFrame,
    *,
    run_rate_quantile: float | None = None,
) -> pd.DataFrame:
    """Aggregate clean weekly demand to per (SKU × DC) run-rate + std.

    Sums across channels first, so the run rate is what each DC actually
    ships in a week — not a per-channel slice. Requires columns:
    ``ITEMNMBR``, ``DC``, ``week_start``, ``qty_base``.

    ``run_rate_quantile`` (None by default) switches the "active" run
    rate column used downstream:

    - ``None`` → ``run_rate_wk = mean(weekly qty)`` (the default, matches
      what step 09 shipped). Best when weekly demand is roughly symmetric.
    - ``0.9`` / ``0.95`` → ``run_rate_wk = pN(weekly qty)``. Captures
      lumpy / burst demand where a handful of big customer orders
      dominate the peak weeks and the mean under-estimates real peak
      drawdown. Raises the reorder point so alerts fire earlier.

    Output always includes ``run_rate_wk_mean`` for reference and (when
    ``run_rate_quantile`` is set) an additional ``run_rate_wk_pN`` column
    so the caller can audit both. ``cv = std / mean`` uses the mean
    denominator regardless — it's a statistical property of the series,
    not a reorder input.
    """
    dc_weekly = (
        weekly.groupby(['ITEMNMBR', 'DC', 'week_start'], as_index=False)['qty_base']
              .sum()
    )
    g = dc_weekly.groupby(['ITEMNMBR', 'DC'])
    out = (
        g.agg(
            n_clean_weeks=('week_start', 'nunique'),
            run_rate_wk_mean=('qty_base', 'mean'),
            std_wk=('qty_base', 'std'),
            first_week=('week_start', 'min'),
            last_week=('week_start', 'max'),
        )
        .reset_index()
    )

    if run_rate_quantile is not None:
        pq_col = f'run_rate_wk_p{int(round(run_rate_quantile * 100))}'
        pq = (
            g['qty_base'].quantile(run_rate_quantile)
                         .rename(pq_col)
                         .reset_index()
        )
        out = out.merge(pq, on=['ITEMNMBR', 'DC'], how='left')
        out['run_rate_wk'] = out[pq_col]
    else:
        out['run_rate_wk'] = out['run_rate_wk_mean']

    out['cv'] = out['std_wk'] / out['run_rate_wk_mean']
    return out


def prepare_item_master(im: pd.DataFrame) -> pd.DataFrame:
    """Normalize item-master columns + parse Lead Time / Case Pack.

    Returns a DataFrame keyed on ``ITEMNMBR`` with: ``Description``,
    ``vendor``, ``country``, ``MOQ``, ``Lead Time`` (original string),
    ``Case Pack`` (original), ``lead_time_wk``, ``lead_parsed``,
    ``case_pack``.
    """
    out = im[['Item Number', 'Description', 'Case Pack', 'Lead Time',
              'Maufactuer/ CoPacker', 'Country of Origin', 'MOQ']].rename(columns={
        'Item Number': 'ITEMNMBR',
        'Maufactuer/ CoPacker': 'vendor',
        'Country of Origin': 'country',
    }).copy()
    parsed = out['Lead Time'].apply(parse_lead_time_weeks)
    out['lead_time_wk'] = parsed.apply(lambda t: t[0])
    out['lead_parsed'] = parsed.apply(lambda t: t[1])
    out['case_pack'] = out['Case Pack'].apply(parse_case_pack)
    return out


def _round_up_case(qty: float, case_pack: float) -> float:
    if pd.isna(qty) or qty <= 0:
        return qty
    cp = case_pack if pd.notna(case_pack) else 1
    if cp <= 1:
        return qty
    return math.ceil(qty / cp) * cp


def build_reorder_alerts(
    weekly: pd.DataFrame,
    inv: pd.DataFrame,
    im: pd.DataFrame,
    *,
    service_level_z: float = SERVICE_LEVEL_Z,
    forward_cover_weeks: int = FORWARD_COVER_WEEKS,
    default_lead_weeks: float = DEFAULT_LEAD_WEEKS,
    min_weeks_for_high: int = MIN_WEEKS_FOR_HIGH,
    run_rate_quantile: float | None = None,
) -> pd.DataFrame:
    """Return a (SKU × DC) reorder alert table sorted by urgency.

    One row per (ITEMNMBR, DC). Sorted by (reorder_flag DESC,
    weeks_of_cover ASC) so the most urgent reorder candidates sit at the
    top. Confidence is ``high`` when ≥ ``min_weeks_for_high`` clean weeks
    AND lead time parsed AND inventory ``available_now`` not null;
    ``medium`` for two of three; ``low`` otherwise.

    Required inputs:
        weekly : ITEMNMBR, DC, week_start, qty_base (clean_demand_weekly).
        inv    : Item Number, DC, Available, On Hand, Description.
        im     : item_master with Item Number, Description, Case Pack,
                 Lead Time, Maufactuer/ CoPacker, Country of Origin, MOQ.
    """
    dc_stats = compute_dc_stats(weekly, run_rate_quantile=run_rate_quantile)

    inv_p = inv.rename(columns={
        'Item Number': 'ITEMNMBR',
        'Description': 'inv_description',
        'Available': 'available_now',
        'On Hand': 'on_hand_now',
    })[['ITEMNMBR', 'DC', 'available_now', 'on_hand_now', 'inv_description']]

    im_p = prepare_item_master(im)

    rec = dc_stats.merge(inv_p, on=['ITEMNMBR', 'DC'], how='left')
    rec = rec.merge(im_p, on='ITEMNMBR', how='left')

    rec['lead_time_source'] = np.where(
        rec['lead_parsed'].fillna(False), 'parsed', 'default',
    )
    rec['lead_time_wk'] = rec['lead_time_wk'].fillna(default_lead_weeks)

    rec['safety_stock'] = (
        service_level_z * rec['std_wk'].fillna(0) * np.sqrt(rec['lead_time_wk'])
    )
    rec['reorder_point'] = (
        rec['run_rate_wk'] * rec['lead_time_wk'] + rec['safety_stock']
    )
    rec['weeks_of_cover'] = np.where(
        rec['run_rate_wk'] > 0,
        rec['available_now'] / rec['run_rate_wk'],
        np.nan,
    )
    rec['reorder_flag'] = rec['available_now'].fillna(0) < rec['reorder_point']

    raw_qty = (
        rec['reorder_point']
        + forward_cover_weeks * rec['run_rate_wk']
        - rec['available_now'].fillna(0)
    ).clip(lower=0)
    rec['suggested_qty_raw'] = raw_qty
    rec['suggested_qty'] = [
        _round_up_case(q, cp)
        for q, cp in zip(rec['suggested_qty_raw'], rec['case_pack'])
    ]
    rec['suggested_cases'] = np.where(
        rec['case_pack'].fillna(0) > 1,
        (rec['suggested_qty'] / rec['case_pack']).round(1),
        np.nan,
    )

    checks = (
        (rec['n_clean_weeks'] >= min_weeks_for_high).astype(int)
        + rec['lead_parsed'].fillna(False).astype(int)
        + rec['available_now'].notna().astype(int)
    )
    rec['confidence'] = np.select(
        [checks == 3, checks == 2],
        ['high', 'medium'],
        default='low',
    )

    ordered_cols = [
        'ITEMNMBR', 'Description', 'DC', 'vendor', 'country',
        'run_rate_wk', 'std_wk', 'cv', 'n_clean_weeks',
        'lead_time_wk', 'lead_time_source', 'Lead Time',
        'available_now', 'on_hand_now',
        'weeks_of_cover', 'reorder_point', 'safety_stock',
        'reorder_flag', 'suggested_qty', 'suggested_cases',
        'case_pack', 'MOQ',
        'first_week', 'last_week',
        'confidence',
    ]
    return (
        rec[ordered_cols]
        .sort_values(['reorder_flag', 'weeks_of_cover'], ascending=[False, True])
        .reset_index(drop=True)
    )
