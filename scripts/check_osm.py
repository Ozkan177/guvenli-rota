"""Check the clipped OSM road network: graph size and road type mix inside each region box.

Usage: python scripts/check_osm.py   ->  reports/checks/osm.csv, reports/checks/osm_highway.csv
"""
import osmnx as ox
import pandas as pd

from guvenli_rota.common import RAW, REPORTS, load_regions


def load_graph(name, region):
    G = ox.graph_from_xml(RAW / name / "osm_roads.osm", retain_all=True)
    return ox.truncate.truncate_graph_bbox(G, region["bbox"], truncate_by_edge=True)


if __name__ == "__main__":
    rows, types = [], []
    for name, r in load_regions().items():
        G = load_graph(name, r)
        edges = ox.graph_to_gdfs(ox.convert.to_undirected(G), nodes=False)
        hw = edges.highway.map(lambda h: h[0] if isinstance(h, list) else h)
        km = edges["length"].groupby(hw).sum() / 1000  # OSMnx edge length in metres
        rows.append({"region": name, "nodes": G.number_of_nodes(), "edges_directed": G.number_of_edges(),
                     "edges_undirected": len(edges), "road_km": round(km.sum(), 1)})
        types += [{"region": name, "highway": k, "km": round(v, 2), "pct_km": round(v / km.sum() * 100, 1)}
                  for k, v in km.sort_values(ascending=False).items()]

    (REPORTS / "checks").mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(REPORTS / "checks" / "osm.csv", index=False)
    t = pd.DataFrame(types)
    t.to_csv(REPORTS / "checks" / "osm_highway.csv", index=False)
    print(pd.DataFrame(rows).to_string(index=False))
    print(t.groupby("region").head(8).to_string(index=False))
