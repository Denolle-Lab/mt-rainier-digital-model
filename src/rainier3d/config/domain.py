"""The model domain and grids: one definition, read from ``configs/domain.yaml``.

The grid is authoritative in EPSG:32610. Every stage builds its coordinates from :class:`Domain`
so that surface rasters and volume levels stay aligned; :func:`assert_on_grid` raises on a
misaligned array instead of letting it overlay silently.

Volume levels are regular grids in (x, y, z) with z = elevation (m, NAVD88, positive up). Cells
are addressed by their centres. Cells above the DEM are "air" and carry NaN properties.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import cached_property
from pathlib import Path

import numpy as np
import yaml

REPO = Path(__file__).resolve().parents[3]
CONFIG = REPO / "configs" / "domain.yaml"


@dataclass(frozen=True)
class Level:
    name: str
    dx: float
    dz: float
    z_top: float
    z_bot: float
    bounds: tuple  # (x0, y0, x1, y1)

    @property
    def x(self) -> np.ndarray:
        return _centres(self.bounds[0], self.bounds[2], self.dx)

    @property
    def y(self) -> np.ndarray:
        return _centres(self.bounds[1], self.bounds[3], self.dx)

    @property
    def z(self) -> np.ndarray:
        """Cell-centre elevations, top down."""
        return _centres(self.z_bot, self.z_top, self.dz)[::-1]

    @property
    def shape(self) -> tuple:
        return (self.z.size, self.y.size, self.x.size)


@dataclass(frozen=True)
class Domain:
    name: str
    crs: str
    vertical_datum: str
    bounds: tuple
    summit_lonlat: tuple
    surface_res_m: float
    levels: dict = field(default_factory=dict)
    cfg: dict = field(default_factory=dict, repr=False)

    @property
    def x(self) -> np.ndarray:
        return _centres(self.bounds[0], self.bounds[2], self.surface_res_m)

    @property
    def y(self) -> np.ndarray:
        return _centres(self.bounds[1], self.bounds[3], self.surface_res_m)

    @cached_property
    def summit_xy(self) -> tuple:
        from pyproj import Transformer

        tf = Transformer.from_crs("EPSG:4326", self.crs, always_xy=True)
        return tf.transform(*self.summit_lonlat)

    @property
    def bbox_4326(self) -> tuple:
        """Lon/lat box that CONTAINS the projected grid (fetch a little extra, clip to the grid)."""
        from pyproj import Transformer

        x0, y0, x1, y1 = self.bounds
        tf = Transformer.from_crs(self.crs, "EPSG:4326", always_xy=True)
        xs = np.r_[np.linspace(x0, x1, 50), np.full(50, x0), np.full(50, x1), np.linspace(x0, x1, 50)]
        ys = np.r_[np.full(50, y0), np.linspace(y0, y1, 50), np.linspace(y0, y1, 50), np.full(50, y1)]
        lon, lat = tf.transform(xs, ys)
        return (lon.min(), lat.min(), lon.max(), lat.max())

    def path(self, key: str) -> Path:
        p = REPO / self.cfg["paths"][key]
        p.mkdir(parents=True, exist_ok=True)
        return p


def _centres(a: float, b: float, d: float) -> np.ndarray:
    n = int(round((b - a) / d))
    if not np.isclose(n * d, b - a):
        raise ValueError(f"extent {b - a} m is not a whole number of {d} m cells")
    return a + d * (np.arange(n) + 0.5)


def load_domain(profile: str | None = None, config: Path = CONFIG) -> Domain:
    cfg = yaml.safe_load(Path(config).read_text())
    prof = cfg["profiles"][profile or cfg["profile"]]
    bounds = tuple(float(v) for v in cfg["bounds_utm"])
    levels = {
        k: Level(name=k, bounds=bounds, **{kk: float(vv) for kk, vv in v.items()})
        for k, v in prof["levels"].items()
    }
    return Domain(
        name=cfg["name"],
        crs=cfg["crs"],
        vertical_datum=cfg["vertical_datum"],
        bounds=bounds,
        summit_lonlat=tuple(cfg["summit_lonlat"]),
        surface_res_m=float(prof["surface_res_m"]),
        levels=levels,
        cfg=cfg,
    )


def assert_on_grid(da, x: np.ndarray, y: np.ndarray, what: str = "array") -> None:
    """Raise unless ``da`` has exactly the x/y cell centres given."""
    for name, ref in (("x", x), ("y", y)):
        got = np.asarray(da[name].values)
        if got.size != ref.size or not np.allclose(np.sort(got), np.sort(ref)):
            raise ValueError(f"{what} is not on the model grid along {name} ({got.size} vs {ref.size} cells)")
