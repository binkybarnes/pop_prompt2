"""One-shot generator for the 9 pipeline notebooks. Run once, then delete.

Each notebook has the same skeleton:
 1. Title + purpose (markdown)
 2. Inputs / outputs contract (markdown)
 3. Imports (code)
 4. Load upstream artifact(s) (code stub)
 5. Do the work (code stub)
 6. Validate (code stub)
 7. Save downstream artifact (code stub)
 8. Notes on what to promote to src/ once verified (markdown)
"""
import json
import uuid
from pathlib import Path

PIPELINE = Path(__file__).parent
ARTIFACTS = PIPELINE / "artifacts"

# (filename, title, purpose, upstream, output, src_target)
STEPS = [
    (
        "01_load.ipynb",
        "01 — Load Tier 1 data",
        "Read raw CSV/XLSX files. Print shapes and dtypes. Cache typed copies as parquet so downstream notebooks do not pay Excel-parse cost.",
        "raw files in `data/`",
        "parquets in `pipeline/artifacts/` (sales, cb, tpr, inv_snapshot, item_master, vendor, po, slprsn_key)",
        "src/load.py",
    ),
    (
        "02_brand.ipynb",
        "02 — Brand extraction",
        "Extract brand from ITEMDESC on sales and chargebacks using prefix map (auto + manual) with a keyword fallback. Verify coverage is high enough to trust downstream promo joins.",
        "sales, cb, tpr parquets",
        "sales_with_brand.parquet, tpr_with_brand.parquet",
        "src/brand.py",
    ),
    (
        "03_promo_calendar.ipynb",
        "03 — Promo calendar + lag imputation",
        "Build (Customer × Brand × YearMonth) promo calendar from TPR chargebacks. For TPR rows with no MM/YY in the description, impute promo_ym by subtracting the median doc_date lag.",
        "tpr_with_brand.parquet",
        "promo_cal.parquet",
        "src/promo_cal.py",
    ),
    (
        "04_inventory_rewind.ipynb",
        "04 — Historical inventory reconstruction",
        "Rewind today's InventorySnapshot backward via (+POs received, −shipments) to get per-SKU-per-DC inventory at each week-end. Needed for stockout detection.",
        "inv_snapshot.parquet, sales.parquet, po.parquet",
        "inv_weekly.parquet",
        "src/inventory.py",
    ),
    (
        "05_tag_transactions.ipynb",
        "05 — Tag transactions",
        "Tag each sales row with is_promo (promo_cal match), is_markdown (price < threshold × SKU median), is_stockout_week (inv=0 that week OR shipped < customer typical weekly).",
        "sales_with_brand.parquet, promo_cal.parquet, inv_weekly.parquet",
        "sales_tagged.parquet",
        "src/tagging.py",
    ),
    (
        "06_channel.ipynb",
        "06 — Channel mapping",
        "Attach MM / AM / HF channel to each transaction via Salesperson ID → channel key. Replaces the unreliable Customer Type field.",
        "sales_tagged.parquet, slprsn_key.parquet",
        "sales_tagged_channel.parquet",
        "src/channel.py",
    ),
    (
        "07_clean_demand.ipynb",
        "07 — Clean demand aggregation",
        "Aggregate untagged (clean) rows into organic_run_rate per SKU × channel × DC. Flag low-data SKUs.",
        "sales_tagged_channel.parquet",
        "clean_demand.parquet",
        "src/demand.py",
    ),
    (
        "08_elasticity_curves.ipynb",
        "08 — F2 demand curves",
        "For showcase SKUs, build color-coded scatter (blue/orange/red/grey) per channel per 6-month window. Fit curves (log-log / isotonic / bucketed mean). Read off elasticity slope and organic baseline.",
        "sales_tagged_channel.parquet",
        "elasticity.parquet, figures in pipeline/artifacts/figures/",
        "src/elasticity.py",
    ),
    (
        "09_reorder_alerts.ipynb",
        "09 — F1 reorder alerts",
        "Compute reorder_point and suggested_qty per SKU × DC using organic run rate + lead time + elasticity-driven safety stock. Output alert list.",
        "clean_demand.parquet, elasticity.parquet, inv_snapshot.parquet, item_master.parquet",
        "reorder_alerts.parquet",
        "src/reorder.py",
    ),
]


def md(source):
    return {
        "cell_type": "markdown",
        "id": str(uuid.uuid4()),
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def code(source):
    return {
        "cell_type": "code",
        "id": str(uuid.uuid4()),
        "metadata": {},
        "execution_count": None,
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def make_notebook(title, purpose, upstream, output, src_target):
    cells = [
        md(f"# {title}\n\n{purpose}"),
        md(
            f"**Upstream:** {upstream}\n\n"
            f"**Output:** {output}\n\n"
            f"**Promotes to:** `{src_target}` once verified."
        ),
        md("## 1. Imports"),
        code(
            "import pandas as pd\n"
            "import numpy as np\n"
            "from pathlib import Path\n"
            "\n"
            "ROOT = Path.cwd().parent if Path.cwd().name == 'pipeline' else Path.cwd()\n"
            "DATA = ROOT / 'data'\n"
            "ART = ROOT / 'pipeline' / 'artifacts'\n"
            "ART.mkdir(parents=True, exist_ok=True)"
        ),
        md("## 2. Load upstream"),
        code("# TODO: load upstream parquet(s) from ART"),
        md("## 3. Do the work"),
        code("# TODO: implement the step"),
        md("## 4. Validate"),
        code("# TODO: shape checks, null checks, spot-check a few rows"),
        md("## 5. Save downstream artifact"),
        code("# TODO: write parquet to ART"),
        md(
            f"## 6. Promote\n\n"
            f"Once validation above looks right, extract the core logic into `{src_target}` "
            "and replace the inline code here with `from src.<module> import ...`. "
            "Downstream dev notebooks can then import the same function."
        ),
    ]
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.12"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


def main():
    for fname, title, purpose, upstream, output, src_target in STEPS:
        nb = make_notebook(title, purpose, upstream, output, src_target)
        path = PIPELINE / fname
        if path.exists():
            print(f"SKIP exists: {path.name}")
            continue
        path.write_text(json.dumps(nb, indent=1))
        print(f"WROTE {path.name}")


if __name__ == "__main__":
    main()
