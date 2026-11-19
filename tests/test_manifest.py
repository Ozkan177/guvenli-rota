import csv
import hashlib

import pytest

from guvenli_rota import common


@pytest.fixture
def manifest(tmp_path, monkeypatch):
    path = tmp_path / "data" / "data_manifest.csv"
    monkeypatch.setattr(common, "ROOT", tmp_path)
    monkeypatch.setattr(common, "MANIFEST", path)
    return path


def read_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write_file(tmp_path, rel, content):
    p = tmp_path / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(content)
    return p


def test_creates_manifest_with_header(tmp_path, manifest):
    f = write_file(tmp_path, "data/raw/a.tif", b"aaa")
    common.log_download("DEM", "v1", "src-a", f)
    rows = read_rows(manifest)
    assert len(rows) == 1
    assert rows[0]["file"] == "data/raw/a.tif"
    assert rows[0]["size_bytes"] == "3"
    assert rows[0]["sha256"] == hashlib.sha256(b"aaa").hexdigest()


def test_same_file_updates_row_in_place(tmp_path, manifest):
    a = write_file(tmp_path, "data/raw/a.tif", b"aaa")
    b = write_file(tmp_path, "data/raw/b.tif", b"bbb")
    common.log_download("DEM", "v1", "src-a", a)
    common.log_download("DEM", "v1", "src-b", b)

    a.write_bytes(b"changed")
    common.log_download("DEM", "v2", "src-a2", a)

    rows = read_rows(manifest)
    assert [r["file"] for r in rows] == ["data/raw/a.tif", "data/raw/b.tif"]
    assert rows[0]["version"] == "v2"
    assert rows[0]["source"] == "src-a2"
    assert rows[0]["sha256"] == hashlib.sha256(b"changed").hexdigest()
    assert rows[1]["sha256"] == hashlib.sha256(b"bbb").hexdigest()


def test_new_file_is_appended(tmp_path, manifest):
    common.log_download("DEM", "v1", "src-a", write_file(tmp_path, "data/raw/a.tif", b"aaa"))
    common.log_download("WC", "v1", "src-c", write_file(tmp_path, "data/raw/c.tif", b"ccc"))
    assert [r["file"] for r in read_rows(manifest)] == ["data/raw/a.tif", "data/raw/c.tif"]


def test_writes_lf_line_endings(tmp_path, manifest):
    a = write_file(tmp_path, "data/raw/a.tif", b"aaa")
    common.log_download("DEM", "v1", "src-a", a)
    common.log_download("DEM", "v1", "src-a", a)
    assert b"\r" not in manifest.read_bytes()
