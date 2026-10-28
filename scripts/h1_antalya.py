"""H1 pre-test (Antalya): do cell site distance/density relate to Ookla measured speed?

Usage: python scripts/h1_antalya.py   (run check_opencellid.py first)
Output: reports/checks/h1.csv, reports/figures/h1_antalya.png

Main sample: 2026Q3 tiles with centre inside the region box. Sensitivity: tiles with >= 5 tests,
and all quarters pooled (test-weighted mean per tile). 95% CI from 1000 bootstrap resamples.
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import spearmanr

from guvenli_rota.common import PROCESSED, REPORTS, load_regions, to_utm

from check_ookla import load_tiles

REGION = "antalya_periurban"
RADIUS_M = 2000
rng = np.random.default_rng(0)


def boot_ci(a, b, n=1000):
    idx = rng.integers(0, len(a), (n, len(a)))
    rs = [spearmanr(a[i], b[i]).statistic for i in idx]
    return np.percentile(rs, [2.5, 97.5])


def features(t, sites):
    tree = cKDTree(sites[["x", "y"]].to_numpy())
    xy = np.column_stack(to_utm(t.tile_x.to_numpy(), t.tile_y.to_numpy()))
    t = t.copy()
    t["dist_nearest_site_m"] = tree.query(xy)[0]
    t["sites_within_2km"] = [len(i) for i in tree.query_ball_point(xy, RADIUS_M)]
    return t


def pooled(t):
    w = t.tests
    g = t.assign(wd=t.avg_d_kbps * w, wl=t.avg_lat_ms * w).groupby("quadkey")
    out = g[["wd", "wl", "tests"]].sum()
    return pd.DataFrame({"avg_d_kbps": out.wd / out.tests, "avg_lat_ms": out.wl / out.tests, "tests": out.tests,
                         "tile_x": g.tile_x.first(), "tile_y": g.tile_y.first()}).reset_index()


if __name__ == "__main__":
    r = load_regions()[REGION]
    sites = pd.read_csv(PROCESSED / REGION / "sites.csv")
    t = load_tiles(REGION)
    x1, y1, x2, y2 = r["bbox"]
    t = t[t.tile_x.between(x1, x2) & t.tile_y.between(y1, y2)]
    latest = t[(t.year == 2026) & (t.quarter == 3)]
    samples = {"2026Q3": latest, "2026Q3_tests>=5": latest[latest.tests >= 5], "pooled_2024Q1-2026Q3": pooled(t)}

    rows = []
    for label, s in samples.items():
        s = features(s, sites)
        for feat in ["dist_nearest_site_m", "sites_within_2km"]:
            for target in ["avg_d_kbps", "avg_lat_ms"]:
                a, b = s[feat].to_numpy(), s[target].to_numpy()
                res = spearmanr(a, b)
                lo, hi = boot_ci(a, b)
                rows.append({"sample": label, "n_tiles": len(s), "feature": feat, "target": target,
                             "spearman_rho": round(res.statistic, 3), "p_value": float(f"{res.pvalue:.2g}"),
                             "ci95_low": round(lo, 3), "ci95_high": round(hi, 3)})
        if label == "2026Q3":
            main = s

    df = pd.DataFrame(rows)
    df.to_csv(REPORTS / "checks" / "h1.csv", index=False)
    print(f"sites used: {len(sites)} (300 m clusters, region box + 5 km)")
    print(df.to_string(index=False))

    ink, mark = "#1f2328", "#2a6fb0"
    fig, axs = plt.subplots(1, 2, figsize=(11, 4.2), constrained_layout=True)
    for ax, feat, xlabel in [(axs[0], "dist_nearest_site_m", "distance to nearest site (m)"),
                             (axs[1], "sites_within_2km", "sites within 2 km")]:
        rho = df.query("sample == '2026Q3' and feature == @feat and target == 'avg_d_kbps'").iloc[0]
        ax.scatter(main[feat], main.avg_d_kbps / 1000, s=14, c=mark, alpha=0.6, ec="none")
        ax.set_yscale("log")
        ax.set_xlabel(xlabel)
        ax.set_ylabel("Ookla download (Mbps, log)")
        ax.set_title(f"Spearman ρ = {rho.spearman_rho:+.2f}  [{rho.ci95_low:+.2f}, {rho.ci95_high:+.2f}],  "
                     f"n = {rho.n_tiles}", fontsize=10, loc="left", color=ink)
        ax.grid(alpha=0.25)
    fig.suptitle("H1 pre-test, Antalya peri-urban, Ookla 2026Q3 tiles vs OpenCelliD sites", color=ink)
    fig.savefig(REPORTS / "figures" / "h1_antalya.png", dpi=110)
