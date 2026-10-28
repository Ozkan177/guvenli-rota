"""Check OpenCelliD cells: counts, sites after clustering, changeable share, radio mix.

Usage: python scripts/check_opencellid.py
Output: reports/checks/opencellid.csv, data/processed/<region>/sites.csv (sites from the buffered clip)
"""
import numpy as np
import pandas as pd

from guvenli_rota.common import PROCESSED, REPORTS, cluster_sites, in_utm_box, load_cells, load_regions

SITE_DIST_M = 300  # median spread of one LTE eNB's cells in Antalya is ~290 m

rows = []
for name, r in load_regions().items():
    cells = load_cells(name)
    sites = cluster_sites(cells, SITE_DIST_M)
    out = PROCESSED / name
    out.mkdir(parents=True, exist_ok=True)
    sites.to_csv(out / "sites.csv", index=False)

    inside = cells[in_utm_box(cells.x, cells.y, r)]
    lte = inside[inside.radio == "LTE"]
    cx, cy = np.mean(r["utm_bounds"][::2]), np.mean(r["utm_bounds"][1::2])
    row = {
        "region": name, "cells_buffered_5km": len(cells), "cells_in_box": len(inside),
        "sites_in_box": int(in_utm_box(sites.x, sites.y, r).sum()),
        "lte_enb_in_box": lte.groupby(["net", lte.cell // 256]).ngroups,
        "changeable_pct": round(float(inside.changeable.mean() * 100), 1) if len(inside) else None,
        "nearest_cell_to_center_km": round(float(np.hypot(cells.x - cx, cells.y - cy).min() / 1000), 1)
        if len(cells) else None,
    }
    row |= {f"radio_{k}": int((inside.radio == k).sum()) for k in ["GSM", "UMTS", "LTE", "NR"]}
    rows.append(row)

df = pd.DataFrame(rows)
(REPORTS / "checks").mkdir(parents=True, exist_ok=True)
df.to_csv(REPORTS / "checks" / "opencellid.csv", index=False)
print(df.T.to_string(header=False))
