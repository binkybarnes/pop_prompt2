"""Brand extraction for POP sales + chargeback data.

Promoted from `pipeline/02_brand.ipynb` after verification:
 - sales coverage: 100.0% (236,818 rows)
 - tpr coverage:    87.6% (6,019 / 6,868 — remainder are admin cause codes with no brand)

High-level entry point:

    from src.load import load_cached
    from src.brand import tag_brands

    dfs = load_cached()
    out = tag_brands(dfs['sales'], dfs['tpr'])
    sales_with_brand = out['sales']   # +1 column 'brand'
    tpr_with_brand   = out['tpr']     # +1 column 'brand'
    sku_brand        = out['sku_brand']  # ITEMNMBR -> brand lookup
"""

from __future__ import annotations

import re

import pandas as pd

__all__ = [
    "BRANDS",
    "BRANDS_V2",
    "PREFIX_MAP_MANUAL",
    "SKU_PREFIX_MAP",
    "first_token",
    "extract_brand",
    "derive_prefix_map_auto",
    "make_extract_brand_v2",
    "apply_sku_prefix_override",
    "fill_brand_from_sku_majority",
    "tag_brands",
]

# Seed brand list — substring match (case-insensitive) against an Item Description.
BRANDS: list[str] = [
    "tiger balm", "ginger chew", "ferrero", "ricola", "kwan loong",
    "ginseng", "kjeldsens", "nutella", "totole", "bee & flower",
    "am gsg", "pop ginger",
]

# Manual prefix → brand map (first alphabetic token of *Item Description*).
# Do NOT put SKU-code prefixes (e.g. 'D-') here; those belong in SKU_PREFIX_MAP.
PREFIX_MAP_MANUAL: dict[str, str] = {
    "GHC": "ginger honey crystals",
    "BFS": "bee & flower",
    "CFX": "cofixrx",
    "AZX": "azzurx",
    "KGS": "ginseng",
    "TBR": "tiger balm",
    "TN":  "tiger balm",
    "TA":  "tiger balm",
    "T":   "tiger balm",
    "HAN": "hans honey",
}

# Extended brand list — used for the substring-fallback step of extract_brand_v2.
BRANDS_V2: list[str] = BRANDS + [
    "ginger honey crystals", "cofixrx", "azzurx", "hans honey", "mx eggrolls",
]

# SKU-code prefix → brand (keyed on ITEMNMBR, applied to sales only).
SKU_PREFIX_MAP: dict[str, str] = {
    "D-": "pop tea",  # all D-* SKUs are POP-branded teas (green/jasmine/oolong/…)
}

_PREFIX_TOKEN_RE = re.compile(r"([A-Za-z&]+)")


def first_token(s) -> str | None:
    """Leading alphabetic token (e.g. 'TBR' from 'TBR-1234 …'), uppercased."""
    if pd.isna(s):
        return None
    m = _PREFIX_TOKEN_RE.match(str(s))
    return m.group(1).upper() if m else None


def extract_brand(desc, brands: list[str] = BRANDS) -> str | None:
    """v1: substring-match a description against `brands`. Returns None if no hit."""
    if pd.isna(desc):
        return None
    d = str(desc).lower()
    for b in brands:
        if b in d:
            return b
    return None


def derive_prefix_map_auto(
    tpr: pd.DataFrame,
    desc_col: str = "Item Description",
    min_share: float = 0.9,
    min_support: int = 3,
) -> dict[str, str]:
    """Learn a prefix → brand map from the already-matched TPR rows.

    For each leading-token prefix, keep the dominant brand iff the prefix's
    dominant brand has >= `min_share` of occurrences AND >= `min_support` rows.
    Typical output on POP data: ~16 entries (AGS, GCP, GCZ, TBZ, TEA, …).
    """
    labeled = tpr.copy()
    labeled["_brand_v1"] = labeled[desc_col].apply(extract_brand)
    labeled = labeled[labeled["_brand_v1"].notna()]
    labeled["_prefix"] = labeled[desc_col].apply(first_token)

    counts = (
        labeled.groupby(["_prefix", "_brand_v1"])
               .size().rename("n").reset_index()
    )
    totals = counts.groupby("_prefix")["n"].sum().rename("total")
    counts = counts.merge(totals, on="_prefix")
    counts["share"] = counts["n"] / counts["total"]

    dom = counts.sort_values("n", ascending=False).drop_duplicates("_prefix")
    dom = dom[(dom["share"] >= min_share) & (dom["n"] >= min_support)]
    return dict(zip(dom["_prefix"], dom["_brand_v1"]))


def make_extract_brand_v2(prefix_map: dict[str, str], brands: list[str] = BRANDS_V2):
    """Return an extract-brand function that uses `prefix_map` first, then `brands` substring."""
    def extract_brand_v2(desc) -> str | None:
        if pd.isna(desc):
            return None
        s = str(desc)
        prefix = first_token(s)
        if prefix and prefix in prefix_map:
            return prefix_map[prefix]
        d = s.lower()
        for b in brands:
            if b in d:
                return b
        return None
    return extract_brand_v2


def apply_sku_prefix_override(
    df: pd.DataFrame,
    sku_col: str = "ITEMNMBR",
    brand_col: str = "brand",
    sku_prefix_map: dict[str, str] = SKU_PREFIX_MAP,
) -> pd.DataFrame:
    """Fill null brand rows by matching ITEMNMBR prefix (e.g. 'D-' → 'pop tea')."""
    if brand_col not in df.columns:
        df[brand_col] = pd.NA
    for sku_prefix, brand in sku_prefix_map.items():
        mask = df[brand_col].isna() & df[sku_col].astype(str).str.startswith(sku_prefix)
        df.loc[mask, brand_col] = brand
    return df


def fill_brand_from_sku_majority(
    df: pd.DataFrame,
    sku_col: str = "ITEMNMBR",
    brand_col: str = "brand",
) -> pd.DataFrame:
    """Last-resort: for null-brand rows, inherit brand from other rows with the same SKU.
    Handles edge cases like a single row with a null ITEMDESC whose SKU is otherwise labeled."""
    sku_to_brand = (
        df.dropna(subset=[brand_col])
          .groupby(sku_col)[brand_col]
          .agg(lambda s: s.mode().iloc[0] if len(s.mode()) else None)
    )
    mask = df[brand_col].isna()
    df.loc[mask, brand_col] = df.loc[mask, sku_col].map(sku_to_brand)
    return df


def tag_brands(
    sales: pd.DataFrame,
    tpr: pd.DataFrame,
    *,
    sales_desc_col: str = "ITEMDESC",
    tpr_desc_col: str = "Item Description",
    sales_sku_col: str = "ITEMNMBR",
) -> dict[str, pd.DataFrame]:
    """End-to-end brand tagging.

    Returns {'sales': sales + 'brand', 'tpr': tpr + 'brand', 'sku_brand': ITEMNMBR -> brand}.
    """
    prefix_map_auto = derive_prefix_map_auto(tpr, desc_col=tpr_desc_col)
    prefix_map = {**prefix_map_auto, **PREFIX_MAP_MANUAL}
    extract_brand_v2 = make_extract_brand_v2(prefix_map)

    sales = sales.copy()
    tpr = tpr.copy()

    tpr["brand"] = tpr[tpr_desc_col].apply(extract_brand_v2)
    sales["brand"] = sales[sales_desc_col].apply(extract_brand_v2)
    sales = apply_sku_prefix_override(sales, sku_col=sales_sku_col)
    sales = fill_brand_from_sku_majority(sales, sku_col=sales_sku_col)

    sku_brand = (
        sales.dropna(subset=["brand"])
             .drop_duplicates(sales_sku_col)[[sales_sku_col, "brand"]]
             .reset_index(drop=True)
    )

    return {"sales": sales, "tpr": tpr, "sku_brand": sku_brand}
