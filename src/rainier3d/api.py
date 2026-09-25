"""Python API to the published rainier3d products: download, open, subset and write them for other codes.

    import rainier3d.api as r3
    r3.products()                                    # what is published, with version, size and licence
    tree = r3.open_model()                           # downloads once (SHA-256 checked), then reads the cache
    g = r3.grid(tree, bbox=(-122.0, 46.7, -121.6, 47.0), dx=250, dz=250, zmin=-10000)
    r3.export(g, "specfem", "out/tomography_model.xyz")   # or netcdf, nll, emc, csv

Downloads go to $RAINIER3D_DATA (default ~/.cache/rainier3d). Only derived products are published; inputs
with restricted licences are rebuilt by the pipeline with the user's own access (docs/data_policy.md).
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from importlib import resources
from pathlib import Path

import numpy as np
import xarray as xr

FORMATS = ("netcdf", "nll", "emc", "specfem", "csv")
CRS = "EPSG:32610"


def cache_dir() -> Path:
    return Path(os.environ.get("RAINIER3D_DATA", Path.home() / ".cache" / "rainier3d")).expanduser()


def products() -> dict:
    """The product catalog shipped with the package (rainier3d/products.json)."""
    return json.loads(resources.files("rainier3d").joinpath("products.json").read_text())["products"]


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _remote_sha256(url: str) -> str | None:
    """The checksum a rolling release publishes as <file>.sha256 ('<hex>  <file>'); None when unreachable."""
    import requests

    try:
        r = requests.get(url, timeout=60)
        r.raise_for_status()
    except requests.RequestException:
        return None
    return r.text.split()[0]


def fetch(name: str, url: str | None = None, sha256: str | None = None, force: bool = False) -> Path:
    """Download (or copy, for a local path) a product archive, check its SHA-256, unzip it; return the folder.

    ``url``/``sha256`` default to the catalog entry. A rolling product (refreshed on a schedule, e.g. gnss)
    publishes its checksum next to the archive; the cached copy is kept while that checksum is unchanged and
    replaced when a newer archive is out. Raises if the product is not published yet or the checksum does
    not match.
    """
    p = products().get(name, {})
    explicit = url is not None
    url, sha256 = url or p.get("url"), sha256 or p.get("sha256")
    if not url:
        raise LookupError(
            f"product {name!r} is not published yet (catalog has no url); build it with the pipeline"
        )
    root = cache_dir() / name
    archive = root / Path(url.split("?")[0]).name
    target = root / "extracted"
    if sha256 is None and not explicit and p.get("sha256_url"):
        sha256 = _remote_sha256(p["sha256_url"])
        if sha256 is None and target.exists():
            return target  # offline: keep the cached copy
        if target.exists() and archive.exists() and _sha256(archive) == sha256 and not force:
            return target
    elif target.exists() and not force:
        return target
    root.mkdir(parents=True, exist_ok=True)
    if Path(url).expanduser().exists():
        shutil.copy(Path(url).expanduser(), archive)
    else:
        import requests

        with requests.get(url, stream=True, timeout=600) as r:
            r.raise_for_status()
            with open(archive, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    f.write(chunk)
    if sha256 and _sha256(archive) != sha256:
        archive.unlink()
        raise ValueError(f"{name}: checksum mismatch for {url}")
    if target.exists():
        shutil.rmtree(target)
    with zipfile.ZipFile(archive) as z:
        z.extractall(target)
    return target


def open_model(path: str | Path | None = None) -> xr.DataTree:
    """The fused model as an xarray DataTree (/surface, /L1, /L2, /L3). Downloads it when no path is given."""
    if path is None:
        root = fetch("model")
        path = next(root.glob("*.zarr"), root)
    return xr.open_datatree(path, engine="zarr", consolidated=False)


def grid(
    tree: xr.DataTree,
    bbox=None,
    dx: float = 500.0,
    dz: float = 250.0,
    zmin: float = -20000.0,
    zmax: float | None = None,
    variables=("vp", "vs", "rho", "qp", "qs"),
) -> xr.Dataset:
    """One uniform (z, y, x) grid in UTM 10N / NAVD88 metres, optionally cut to a lon/lat box and z range.
    Air cells keep the values of the first rock cell below them, flagged by ``air``."""
    from pyproj import Transformer

    from rainier3d.export.grids import uniform

    g = uniform(tree, dx=dx, dz=dz, z_top=zmax, z_bot=zmin, variables=tuple(variables))
    if bbox is not None:
        w, s, e, n = bbox
        tf = Transformer.from_crs("EPSG:4326", CRS, always_xy=True)
        xs, ys = tf.transform([w, e, w, e], [s, s, n, n])
        g = g.sel(x=slice(min(xs), max(xs)), y=slice(min(ys), max(ys)))
    g.attrs["bbox_lonlat"] = list(bbox) if bbox is not None else "full domain"
    return g


def export(g: xr.Dataset, fmt: str, out: str | Path, tree: xr.DataTree | None = None) -> list[Path]:
    """Write a uniform grid for another code: netcdf (CF), nll (NonLinLoc P/S; dx must equal dz), emc
    (lon/lat/depth netCDF3; needs ``tree``), specfem (SPECFEM3D tomography_model.xyz) or csv."""
    from types import SimpleNamespace

    from rainier3d.export import grids

    out = Path(out)
    if fmt == "netcdf":
        return [grids.write_netcdf(g, out)]
    if fmt == "nll":
        return grids.write_nll(g, out)
    if fmt == "specfem":
        return [grids.write_specfem_xyz(g, out)]
    if fmt == "csv":
        return [grids.write_csv(g, out)]
    if fmt == "emc":
        if tree is None:
            raise ValueError("emc export needs the model tree")
        from pyproj import Transformer

        tf = Transformer.from_crs(CRS, "EPSG:4326", always_xy=True)
        lon, lat = tf.transform([g.x.min(), g.x.max()], [g.y.min(), g.y.max()])
        dom = SimpleNamespace(bbox_4326=(lon[0], lat[0], lon[1], lat[1]), crs=CRS)
        return [grids.write_emc(tree, dom, out)]
    raise ValueError(f"unknown format {fmt!r}; one of {FORMATS}")


def surface(tree: xr.DataTree, layers=None) -> xr.Dataset:
    """The surface layers (elevation, units, ice, soil, water, canopy, ...) on the 100 m grid."""
    s = tree["surface"].to_dataset()
    return s[list(layers)] if layers else s


def export_surface(tree: xr.DataTree, out_dir: str | Path, layers=None) -> list[Path]:
    """One GeoTIFF per surface layer (UTM 10N)."""
    import rioxarray  # noqa: F401

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for k, da in surface(tree, layers).data_vars.items():
        if da.ndim != 2:
            continue
        a = da.astype("float32") if da.dtype == bool else da
        a = a.rio.write_crs(CRS).sortby("y", ascending=False)
        p = out_dir / f"{k}.tif"
        a.rio.to_raster(p)
        written.append(p)
    return written


def sample(tree: xr.DataTree, lon: float, lat: float, depth_m: float) -> dict:
    """Model values at one point (depth below sea level, metres)."""
    from pyproj import Transformer

    x, y = Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform(lon, lat)
    z = -depth_m
    for lev in ("L1", "L2", "L3"):
        ds = tree[lev].to_dataset()
        half = ds.attrs["dz"] / 2
        if float(ds.z.min()) - half <= z <= float(ds.z.max()) + half:
            p = ds.sel(x=x, y=y, z=z, method="nearest")
            return {
                v: (float(p[v]) if np.isfinite(p[v]) else None)
                for v in ("vp", "vs", "rho", "qp", "qs", "unit")
                if v in p
            } | {"level": lev}
    return {}
