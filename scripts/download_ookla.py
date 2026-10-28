"""Read Ookla mobile performance tiles for each region from S3 (remote, filtered) and save them.

Usage: python scripts/download_ookla.py
Output: data/raw/<region>/ookla_mobile_2024q1_2026q3.parquet (one row per tile per quarter)

Only the row groups that overlap the region boxes are fetched, not the ~190 MB quarterly files.
Missing tiles mean "no measurements", not "no coverage".
"""
import duckdb

from guvenli_rota.common import buffered_bbox, load_regions, log_download, region_dir

SRC = "s3://ookla-open-data/parquet/performance/type=mobile/year=*/quarter=*/*.parquet"
FIRST_YEAR = 2024
VERSION = "2024Q1-2026Q3"
BUFFER_DEG = 0.01  # tiles just outside the box still matter for edge cells


def in_box(b):
    return f"tile_x BETWEEN {b[0]} AND {b[2]} AND tile_y BETWEEN {b[1]} AND {b[3]}"


def fetch(regions):
    """Save one parquet per region and return {region: DataFrame}."""
    boxes = {n: buffered_bbox(r["bbox"], BUFFER_DEG) for n, r in regions.items()}
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs; SET s3_region='us-west-2';")
    con.execute(f"""
        CREATE TABLE t AS SELECT * FROM read_parquet('{SRC}', hive_partitioning=true, union_by_name=true)
        WHERE year >= {FIRST_YEAR} AND ({" OR ".join(f"({in_box(b)})" for b in boxes.values())})
    """)
    frames = {}
    for n, b in boxes.items():
        out = region_dir(n) / "ookla_mobile_2024q1_2026q3.parquet"
        con.execute(f"COPY (SELECT * FROM t WHERE {in_box(b)} ORDER BY year, quarter, quadkey) "
                    f"TO '{out.as_posix()}' (FORMAT parquet)")
        log_download("Ookla Speedtest open data (mobile)", VERSION, SRC, out)
        frames[n] = con.execute(f"SELECT * FROM '{out.as_posix()}'").df()
    return frames


def summary(regions, frames):
    """Tiles with centroid inside the (unbuffered) region box, per quarter and cumulative."""
    for n, df in frames.items():
        x1, y1, x2, y2 = regions[n]["bbox"]
        d = df[df.tile_x.between(x1, x2) & df.tile_y.between(y1, y2)]
        per_q = d.groupby(["year", "quarter"]).quadkey.nunique()
        print(f"\n{n}: unique tiles over all quarters = {d.quadkey.nunique()}, "
              f"best single quarter = {per_q.max()}, latest = {per_q.iloc[-1]}")
        print("  " + "  ".join(f"{y}Q{q}:{c}" for (y, q), c in per_q.items()))


if __name__ == "__main__":
    regions = load_regions()
    summary(regions, fetch(regions))
