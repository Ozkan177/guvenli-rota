"""One quick-look figure per region from the raw clips (lon/lat axes).

Usage: python scripts/plot_quicklook.py   ->  reports/figures/quicklook_<region>.png
Run check_opencellid.py first (it writes the site table).
"""
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import osmnx as ox
import pandas as pd
import rasterio
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.patches import Patch, Rectangle
from pyproj import Transformer

from guvenli_rota.common import GRID_CRS, PROCESSED, RAW, REPORTS, load_regions

from check_ookla import load_tiles
from check_osm import load_graph

# official WorldCover legend colours
WC = {10: ("tree", "#006400"), 20: ("shrub", "#ffbb22"), 30: ("grass", "#ffff4c"), 40: ("crop", "#f096ff"),
      50: ("built", "#fa0000"), 60: ("bare", "#b4b4b4"), 70: ("snow", "#f0f0f0"), 80: ("water", "#0064c8"),
      90: ("wetland", "#0096a0"), 95: ("mangrove", "#00cf75"), 100: ("moss", "#fae6a0")}
MAJOR = {"motorway", "trunk", "primary", "secondary", "tertiary"}
INK, MUTED = "#1f2328", "#8c959f"
BLUES = ListedColormap(plt.cm.Blues(np.linspace(0.2, 1, 256)))  # lowest speeds stay visible on white


def raster(ax, path, **kw):
    with rasterio.open(path) as s:
        a, b = s.read(1), s.bounds
    return ax.imshow(a, extent=(b.left, b.right, b.bottom, b.top), interpolation="nearest", **kw), a


def frame(ax, r, title):
    x1, y1, x2, y2 = r["bbox"]
    ax.add_patch(Rectangle((x1, y1), x2 - x1, y2 - y1, fill=False, ec=INK, lw=1.5, ls="--"))
    pad = 0.012
    ax.set_xlim(x1 - pad, x2 + pad)
    ax.set_ylim(y1 - pad, y2 + pad)
    ax.set_aspect(1 / np.cos(np.radians((y1 + y2) / 2)))
    ax.set_title(title, fontsize=10, loc="left", color=INK)
    ax.tick_params(labelsize=7, colors=MUTED)


def tiles(ax, fig, t, title, r):
    if len(t):
        im = t.plot(ax=ax, column=t.avg_d_kbps / 1000, cmap=BLUES, vmin=0, vmax=200, edgecolor="white", lw=0.3)
        fig.colorbar(im.collections[0], ax=ax, shrink=0.7, label="download Mbps")
    frame(ax, r, f"{title}: {len(t)} tiles")


for name, r in load_regions().items():
    fig, axs = plt.subplots(2, 3, figsize=(15, 10), constrained_layout=True)
    fig.suptitle(f"{r['label']}  ({name}, dashed = 10 km region box)", fontsize=12, color=INK)

    im, z = raster(axs[0, 0], RAW / name / "dem_glo30.tif", cmap="Greys_r")
    fig.colorbar(im, ax=axs[0, 0], shrink=0.7, label="elevation m (DSM)")
    frame(axs[0, 0], r, f"Copernicus DEM GLO-30: {z.min():.0f}-{z.max():.0f} m")

    codes = sorted(WC)
    cmap = ListedColormap([WC[c][1] for c in codes])
    _, lc = raster(axs[0, 1], RAW / name / "worldcover_2021_v200.tif",
                   cmap=cmap, norm=BoundaryNorm([c - 0.5 for c in codes] + [codes[-1] + 0.5], len(codes)))
    present = [c for c in codes if (lc == c).mean() > 0.005]
    axs[0, 1].legend(handles=[Patch(color=WC[c][1], label=WC[c][0]) for c in present], fontsize=7, loc="lower left")
    frame(axs[0, 1], r, "ESA WorldCover 2021 v200")

    edges = ox.graph_to_gdfs(ox.convert.to_undirected(load_graph(name, r)), nodes=False)
    major = edges.highway.map(lambda h: (h[0] if isinstance(h, list) else h) in MAJOR)
    edges[~major].plot(ax=axs[0, 2], color=MUTED, lw=0.4)
    edges[major].plot(ax=axs[0, 2], color=INK, lw=1.4)
    axs[0, 2].legend(handles=[Patch(color=INK, label="tertiary and above"), Patch(color=MUTED, label="minor, track, path")],
                     fontsize=7, loc="lower left")
    frame(axs[0, 2], r, f"OSM roads: {len(edges)} edges")

    t = load_tiles(name)
    tiles(axs[1, 0], fig, t[(t.year == 2026) & (t.quarter == 3)], "Ookla mobile 2026Q3", r)
    pooled = t.sort_values(["year", "quarter"]).drop_duplicates("quadkey", keep="last")
    tiles(axs[1, 1], fig, pooled, "Ookla pooled 2024Q1-2026Q3 (latest value)", r)

    ax = axs[1, 2]
    cells = pd.read_csv(RAW / name / "opencellid_cells.csv")
    sites = pd.read_csv(PROCESSED / name / "sites.csv")
    ax.scatter(cells.lon, cells.lat, s=6, c=MUTED, label=f"cells ({len(cells)})")
    if len(sites):
        lon, lat = Transformer.from_crs(GRID_CRS, "EPSG:4326", always_xy=True).transform(sites.x, sites.y)
        ax.scatter(lon, lat, s=22, facecolors="none", ec=INK, lw=1.2, label=f"sites, 300 m clusters ({len(sites)})")
    ax.legend(fontsize=7, loc="lower left")
    frame(ax, r, "OpenCelliD (box + 5 km buffer)")
    if not len(cells):
        ax.text(0.5, 0.5, "no cells within 5 km", transform=ax.transAxes, ha="center", color=INK)
    ax.set_xlim(r["bbox"][0] - 0.05, r["bbox"][2] + 0.05)
    ax.set_ylim(r["bbox"][1] - 0.05, r["bbox"][3] + 0.05)

    out = REPORTS / "figures" / f"quicklook_{name}.png"
    fig.savefig(out, dpi=110)
    plt.close(fig)
    print(out)
