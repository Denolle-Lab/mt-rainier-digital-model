"""Client API and CLI (rainier3d.api, rainier3d.cli): catalog, checksummed fetch, writers."""

import hashlib
import zipfile

import numpy as np
import pytest
import xarray as xr

from rainier3d import api
from rainier3d.export import grids


def _tiny_grid():
    z, y, x = np.array([500.0, 0.0, -500.0]), np.array([10.0, 20.0]), np.array([1.0, 2.0, 3.0])
    shape = (z.size, y.size, x.size)
    ds = xr.Dataset(
        {
            v: (("z", "y", "x"), np.full(shape, val, np.float32))
            for v, val in (("vp", 5000.0), ("vs", 2900.0), ("rho", 2700.0), ("qp", 200.0), ("qs", 100.0))
        },
        coords={"z": z, "y": y, "x": x},
    )
    ds["air"] = (("z", "y", "x"), np.zeros(shape, np.int8))
    ds.attrs = {"dx_m": 1.0, "dz_m": 500.0}
    return ds


def test_catalog_lists_products():
    p = api.products()
    assert {"model", "gnss", "edifice_load"} <= set(p)
    assert all("license" in v and "description" in v for v in p.values())


def test_specfem_xyz_header_and_order(tmp_path):
    f = grids.write_specfem_xyz(_tiny_grid(), tmp_path / "tomo.xyz")
    lines = f.read_text().splitlines()
    assert lines[1].split() == ["1.0", "10.0", "500.0"] and lines[2].split() == ["3", "2", "3"]
    first, second = lines[4].split(), lines[5].split()
    assert float(first[2]) == -500.0 and float(second[0]) == 2.0  # bottom up, x fastest
    assert len(lines) == 4 + 3 * 2 * 3


def test_fetch_checks_sha256(tmp_path, monkeypatch):
    monkeypatch.setenv("RAINIER3D_DATA", str(tmp_path / "cache"))
    src = tmp_path / "p.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("hello.txt", "x")
    good = hashlib.sha256(src.read_bytes()).hexdigest()
    out = api.fetch("model", url=str(src), sha256=good)
    assert (out / "hello.txt").read_text() == "x"
    with pytest.raises(ValueError):
        api.fetch("model", url=str(src), sha256="0" * 64, force=True)


def test_unpublished_product_raises(monkeypatch):
    monkeypatch.setattr(api, "products", lambda: {"model": {"url": None}})
    with pytest.raises(LookupError):
        api.fetch("model")


def test_cli_list(capsys):
    from rainier3d.cli import main

    assert main(["list"]) == 0
    assert "model" in capsys.readouterr().out


def test_rolling_fetch_follows_published_checksum(tmp_path, monkeypatch):
    """A rolling product (weekly GNSS) keeps its cache while the published <file>.sha256 is unchanged,
    replaces it when a newer archive is out, and keeps it when the checksum cannot be reached (offline)."""
    monkeypatch.setenv("RAINIER3D_DATA", str(tmp_path / "cache"))
    src = tmp_path / "rainier3d_gnss.zip"

    def publish(text):
        with zipfile.ZipFile(src, "w") as z:
            z.writestr("gnss/summary.json", text)
        return hashlib.sha256(src.read_bytes()).hexdigest()

    entry = {"url": str(src), "sha256_url": "https://example.org/rainier3d_gnss.zip.sha256", "rolling": True}
    monkeypatch.setattr(api, "products", lambda: {"gnss": entry})
    remote = {"sha": publish('{"as_of": "2026-09-21"}')}
    monkeypatch.setattr(api, "_remote_sha256", lambda url: remote["sha"])
    out = api.fetch("gnss")
    assert "09-21" in (out / "gnss" / "summary.json").read_text()
    publish("stale local file that must not be read")  # unchanged checksum -> cache is kept
    assert "09-21" in (api.fetch("gnss") / "gnss" / "summary.json").read_text()
    remote["sha"] = publish('{"as_of": "2026-09-28"}')  # new refresh -> replaced
    assert "09-28" in (api.fetch("gnss") / "gnss" / "summary.json").read_text()
    remote["sha"] = None  # offline -> cached copy
    assert "09-28" in (api.fetch("gnss") / "gnss" / "summary.json").read_text()


def test_rolling_fetch_refuses_unverified_download(tmp_path, monkeypatch):
    """No cache and no reachable checksum: fetch raises instead of extracting an unverified archive."""
    monkeypatch.setenv("RAINIER3D_DATA", str(tmp_path / "cache"))
    src = tmp_path / "rainier3d_gnss.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.writestr("gnss/summary.json", "{}")
    entry = {"url": str(src), "sha256_url": "https://example.org/x.sha256", "rolling": True}
    monkeypatch.setattr(api, "products", lambda: {"gnss": entry})
    monkeypatch.setattr(api, "_remote_sha256", lambda url: None)
    with pytest.raises(ConnectionError):
        api.fetch("gnss")
    assert not (tmp_path / "cache" / "gnss" / "extracted").exists()


def test_remote_sha256_rejects_non_checksum_bodies(monkeypatch):
    import requests

    class R:
        def __init__(self, text):
            self.text = text

        def raise_for_status(self):
            pass

    good = "a" * 64
    for body, want in ((f"{good}  rainier3d_gnss.zip\n", good), ("", None), ("<html>404</html>", None)):
        monkeypatch.setattr(requests, "get", lambda *a, _b=body, **k: R(_b))
        assert api._remote_sha256("https://example.org/x.sha256") == want


def test_fetch_missing_local_path_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("RAINIER3D_DATA", str(tmp_path / "cache"))
    with pytest.raises(FileNotFoundError):
        api.fetch("model", url=str(tmp_path / "nope.zip"))


def test_pylith_simplegrid_header_and_rows(tmp_path):
    """SimpleGridDB: counts and names in the header, one coordinate list per axis, x-fastest rows of
    x y z density vs vp, and the .cfg snippet that points PyLith at the file."""
    path, cfg = grids.write_pylith_simplegrid(_tiny_grid(), tmp_path / "rainier3d.spatialdb")
    text = path.read_text()
    assert "#SPATIAL_GRID.ascii 1" in text and "value-names = density vs vp" in text
    assert (
        "num-x = 3" in text
        and "num-y = 2" in text
        and "num-z = 3" in text
        and "crs-string = EPSG:32610" in text
    )
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("//")]
    body = lines[lines.index("}") + 1 :]
    assert [len(ln.split()) for ln in body[:3]] == [3, 2, 3]  # x, y, z coordinate lists
    rows = np.loadtxt(body[3:])
    assert rows.shape == (3 * 2 * 3, 6)
    assert rows[1, 0] == 2.0 and rows[1, 1] == 10.0  # x varies fastest
    assert rows[0, 2] == -500.0 and rows[-1, 2] == 500.0  # z increasing (bottom up)
    assert np.allclose(rows[:, 3:], [2700.0, 2900.0, 5000.0])
    assert "db_auxiliary_field.filename = rainier3d.spatialdb" in cfg.read_text()
