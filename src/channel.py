"""Attach sales channel (MM / AM / HF) to each sales row via salesperson ID.

POP's sales data has a `Customer Type` field but it's free-text and inconsistent.
The source of truth is `SLPRSNID_SALESCHANNEL_KEY.xlsx`, a 46-row table that
maps each salesperson to one of three channels:

    MM : American Mainstream Market  (30 salespeople)
    AM : Asian Ethnic Market         (14 salespeople)
    HF : Health Food                 ( 2 salespeople)

Coverage is ~100%; only a handful of sales rows have a null SLPRSNID and those
are left as NA in SALESCHANNEL.

Public API:
    attach_channel(sales, slprsn_key) -> sales_with_channel
"""

from __future__ import annotations

import pandas as pd


def attach_channel(sales: pd.DataFrame, slprsn_key: pd.DataFrame) -> pd.DataFrame:
    """Left-merge SALESCHANNEL / SALESCHANNEL_DESC onto sales via SLPRSNID.

    Args:
        sales: must contain SLPRSNID.
        slprsn_key: columns ['SLPRSNID', 'SALESCHANNEL', 'SALESCHANNEL_DESC'].

    Returns:
        sales with two columns added. Row count preserved. Rows whose
        SLPRSNID is null or unmatched get NA in SALESCHANNEL.
    """
    return sales.merge(slprsn_key, on='SLPRSNID', how='left')
