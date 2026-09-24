"""Zarr I/O and provenance attributes.

Local zarr v3 stores under ``data/processed``; the Kopah S3 target used by
gwl-space-time-smooth (``src/io/zarr_store.py``) plugs in here later. Every layer carries the
four GAIA provenance attributes (``gaia:source``, ``gaia:measurement``, ``gaia:resolution_m``,
``gaia:uncertainty_path``), with the source resolved from ``configs/sources.yaml``.
"""

from __future__ import annotations

from pathlib import Path

import xarray as xr
import yaml

from rainier3d.config.domain import REPO

SOURCES = REPO / "configs" / "sources.yaml"


def sources() -> dict:
    return yaml.safe_load(SOURCES.read_text())


def provenance(
    da: xr.DataArray,
    source_keys: list[str],
    measurement: str,
    resolution_m: float,
    uncertainty_path: str | None = None,
) -> xr.DataArray:
    reg = sources()
    missing = [k for k in source_keys if k not in reg]
    if missing:
        raise KeyError(f"source keys not in configs/sources.yaml: {missing}")
    da.attrs.update(
        {
            "gaia:source": "; ".join(reg[k].get("doi") or reg[k].get("url") or k for k in source_keys),
            "gaia:source_keys": ",".join(source_keys),
            "gaia:measurement": measurement,
            "gaia:resolution_m": float(resolution_m),
            "gaia:uncertainty_path": uncertainty_path or "none",
        }
    )
    return da


def write(obj: xr.Dataset | xr.DataTree, path: Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    obj.to_zarr(path, mode="w", consolidated=False, zarr_format=3)
    return path


def read(path: Path) -> xr.Dataset:
    return xr.open_zarr(path, consolidated=False).load()


def read_tree(path: Path) -> xr.DataTree:
    return xr.open_datatree(path, engine="zarr", consolidated=False).load()
