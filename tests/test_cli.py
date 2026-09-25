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
