"""Load Tier 1 POP data files into typed dataframes.

Promoted from `pipeline/01_load.ipynb` after end-to-end verification.
Downstream notebooks/modules read parquet artifacts via `load_cached()`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

__all__ = [
    "load_all",
    "load_cached",
    "write_cache",
    "TPR_CAUSE_REGEX",
]

TPR_CAUSE_REGEX = r"TPR|promo|price reduction"


def _resolve_root(root: Path | str | None) -> Path:
    if root is not None:
        return Path(root)
    cwd = Path.cwd()
    return cwd.parent if cwd.name == "pipeline" else cwd


def load_all(root: Path | str | None = None) -> dict[str, pd.DataFrame]:
    """Read the 7 raw Tier-1 files and derive `tpr`. Returns a dict of dataframes.

    Keys: sales, cb, tpr, inv_snapshot, item_master, vendor_master, po, slprsn_key.
    """
    root = _resolve_root(root)
    data = root / "data"

    sales = pd.read_csv(
        data / "POP_SalesTransactionHistory.csv",
        parse_dates=["DOCDATE"],
        low_memory=False,
    )

    inv = pd.concat(
        [
            pd.read_excel(data / "POP_InventorySnapshot.xlsx", sheet_name="Site 1 - SF").assign(DC="SF"),
            pd.read_excel(data / "POP_InventorySnapshot.xlsx", sheet_name="Site 2 - NJ").assign(DC="NJ"),
            pd.read_excel(data / "POP_InventorySnapshot.xlsx", sheet_name="Site 3 - LA").assign(DC="LA"),
        ],
        ignore_index=True,
    )

    items = pd.read_excel(data / "POP_ItemSpecMaster.xlsx", sheet_name="Item Spec Master")
    vendors = pd.read_excel(data / "POP_VendorMaster.xlsx", sheet_name="Supplier Master")
    pos = pd.read_excel(data / "POP_PurchaseOrderHistory.XLSX", sheet_name="PO Order History 2023-2025")
    cb = pd.read_excel(
        data / "POP_ChargeBack_Deductions_Penalties_Freight.xlsx",
        sheet_name="Data - Deductions & Cause Code",
    )
    slprsn = pd.read_excel(data / "SLPRSNID_SALESCHANNEL_KEY.xlsx")

    tpr_mask = cb["Cause Code Desc"].str.contains(TPR_CAUSE_REGEX, case=False, na=False)
    tpr = cb[tpr_mask].copy()

    return {
        "sales": sales,
        "cb": cb,
        "tpr": tpr,
        "inv_snapshot": inv,
        "item_master": items,
        "vendor_master": vendors,
        "po": pos,
        "slprsn_key": slprsn,
    }


def _dedup_columns(cols) -> tuple[list[str], list[tuple[str, str]]]:
    seen: dict[str, int] = {}
    out: list[str] = []
    renamed: list[tuple[str, str]] = []
    for c in cols:
        key = str(c)
        if key in seen:
            seen[key] += 1
            new = f"{key}__{seen[key]}"
            renamed.append((key, new))
            out.append(new)
        else:
            seen[key] = 0
            out.append(key)
    return out, renamed


def _coerce_mixed_object_cols(df: pd.DataFrame) -> list[tuple[str, list[str]]]:
    """Cast object-dtype columns with heterogeneous Python types to string in-place.

    Pyarrow rejects mixed-type columns (e.g. `Case Pack` = int+str, `Zip` = int+str,
    `Lead Time` = float+str). NaN is preserved. `exclude='str'` skips pandas 3
    native-string columns to silence Pandas4Warning.
    """
    renamed: list[tuple[str, list[str]]] = []
    for col in df.select_dtypes(include="object", exclude="str").columns:
        sample = df[col].dropna().head(200)
        types = {type(v).__name__ for v in sample}
        if len(types) > 1:
            df[col] = df[col].where(df[col].isna(), df[col].astype(str))
            renamed.append((col, sorted(types)))
    return renamed


def write_cache(
    dfs: dict[str, pd.DataFrame],
    art_dir: Path | str,
    *,
    verbose: bool = True,
) -> dict[str, Path]:
    """Write each dataframe to `<art_dir>/<name>.parquet`, coercing mixed-type object cols.

    Returns a map of name -> written path. On parquet failure, falls back to pickle.
    """
    art = Path(art_dir)
    art.mkdir(parents=True, exist_ok=True)
    written: dict[str, Path] = {}

    for name, df in dfs.items():
        df_out = df.copy()

        new_cols, dup_renamed = _dedup_columns(df_out.columns)
        df_out.columns = new_cols
        if verbose and dup_renamed:
            print(f"{name:14s} deduped cols: {dup_renamed}")

        mixed = _coerce_mixed_object_cols(df_out)
        if verbose and mixed:
            print(f"{name:14s} cast mixed-type cols to str: {mixed}")

        path = art / f"{name}.parquet"
        try:
            df_out.to_parquet(path)
            written[name] = path
            if verbose:
                print(f"{name:14s} {df_out.shape} -> {path.name}")
        except Exception as e:
            alt = art / f"{name}.pkl"
            df_out.to_pickle(alt)
            written[name] = alt
            if verbose:
                print(f"{name:14s} parquet FAILED ({type(e).__name__}): {e}")
                print(f"               saved pickle -> {alt.name}")

    return written


def load_cached(
    art_dir: Path | str | None = None,
    names: list[str] | None = None,
) -> dict[str, pd.DataFrame]:
    """Read cached parquet (or pickle fallback) artifacts produced by `write_cache()`.

    Defaults to the standard `pipeline/artifacts/` under the repo root.
    """
    if art_dir is None:
        art_dir = _resolve_root(None) / "pipeline" / "artifacts"
    art = Path(art_dir)
    if names is None:
        names = [
            "sales",
            "cb",
            "tpr",
            "inv_snapshot",
            "item_master",
            "vendor_master",
            "po",
            "slprsn_key",
        ]
    out: dict[str, pd.DataFrame] = {}
    for name in names:
        pq = art / f"{name}.parquet"
        pk = art / f"{name}.pkl"
        if pq.exists():
            out[name] = pd.read_parquet(pq)
        elif pk.exists():
            out[name] = pd.read_pickle(pk)
        else:
            raise FileNotFoundError(f"No cached artifact for '{name}' in {art}")
    return out
