"""Rule-based 3D geology (M1), in the spirit of the USGS SF-CVM: map units extended to depth with
simple, stated rules. Replaced by map2loop + LoopStructural in M3.

Column rule, top down, for a cell at elevation z with depth d = DEM - z below the ground:
  d < 0                                    air
  d < H_ice                                ice
  d < H_ice + T_unconsolidated             surface deposit (drift, alluvium, lahar, water)
  inside the edifice footprint, z > base   rainier_andesite
  young_volcanics / distal andesite cap    that unit, to cap_thickness below the bedrock top
  z > base of the bedrock unit             bedrock unit (map unit, or nearest mapped basement unit)
  otherwise                                middle_crust
then the magma_mush ellipsoid overrides whatever it contains.

The edifice base is the pre-volcanic surface: DEM elevations where basement crops out against the
edifice footprint, interpolated linearly across it.
"""

from __future__ import annotations

import numpy as np
import xarray as xr
from scipy.interpolate import griddata
from scipy.ndimage import binary_closing, binary_dilation, binary_fill_holes, label

from rainier3d.config.domain import Domain, Level
from rainier3d.surface.geology import fill_nearest

AIR, ICE, WATER, EDIFICE, CAP, MIDDLE, MAGMA = 0, 1, 2, 6, 7, 20, 21


def kinds(units_cfg: dict) -> dict[int, str]:
    return {int(k): v.get("kind", "") for k, v in units_cfg["units"].items()}


def bedrock_units(surface_unit: np.ndarray, kind: dict[int, str], exclude=()) -> np.ndarray:
    """Basement unit under every cell: the mapped unit where basement crops out, else the nearest one."""
    keep = np.isin(
        surface_unit, [u for u, k in kind.items() if k in ("pluton", "supracrustal") and u not in exclude]
    )
    return fill_nearest(surface_unit, keep)


def edifice_footprint(
    surface_unit: np.ndarray,
    x: np.ndarray,
    y: np.ndarray,
    summit_xy: tuple,
    radius_m: float,
    closing_m: float,
    res_m: float,
) -> np.ndarray:
    xx, yy = np.meshgrid(x, y)
    near = np.hypot(xx - summit_xy[0], yy - summit_xy[1]) < radius_m
    m = near & np.isin(surface_unit, [EDIFICE, ICE])
    n = max(1, int(round(closing_m / res_m)))
    m = binary_fill_holes(binary_closing(m, structure=np.ones((n, n)), iterations=1))
    lab, _ = label(m)
    iy, ix = np.argmin(np.abs(y - summit_xy[1])), np.argmin(np.abs(x - summit_xy[0]))
    if lab[iy, ix] == 0:
        raise ValueError("summit is not inside the edifice footprint; check the crosswalk")
    return lab == lab[iy, ix]


def edifice_base(
    dem: np.ndarray,
    footprint: np.ndarray,
    surface_unit: np.ndarray,
    kind: dict[int, str],
    x: np.ndarray,
    y: np.ndarray,
) -> np.ndarray:
    """Pre-volcanic surface elevation over the footprint (NaN outside)."""
    basement = np.isin(surface_unit, [u for u, k in kind.items() if k in ("pluton", "supracrustal")])
    ring = binary_dilation(footprint, iterations=2) & ~footprint & basement
    if ring.sum() < 10:
        raise ValueError("too few basement contacts around the edifice to interpolate its base")
    xx, yy = np.meshgrid(x, y)
    pts = np.c_[xx[ring], yy[ring]]
    base = griddata(pts, dem[ring], (xx, yy), method="linear")
    near = griddata(pts, dem[ring], (xx, yy), method="nearest")
    base = np.where(np.isnan(base), near, base)
    return np.where(footprint, base, np.nan)


def ellipsoid(xx, yy, zz, cx, cy, cz, ah, av):
    return ((xx - cx) ** 2 + (yy - cy) ** 2) / ah**2 + (zz - cz) ** 2 / av**2 <= 1.0


def surface_on_level(surf: xr.Dataset, lev: Level) -> xr.Dataset:
    """Surface fields at the level's cell centres: linear for continuous fields, nearest for units."""
    alt = [v for v in surf.data_vars if v.startswith(("alt_a_", "alt_doi_"))]  # S22 maps, when present
    cont = surf[["elevation", "ice_thickness", "edifice_base", *alt]]
    cont = cont.interp(x=lev.x, y=lev.y, method="linear")
    cat = surf[["surface_unit", "bedrock_unit", "bedrock_unit_under", "footprint"]]
    cat = cat.sel(x=lev.x, y=lev.y, method="nearest")
    cat = cat.assign_coords(x=lev.x, y=lev.y)
    return xr.merge([cont, cat], compat="override")


def build_level(
    s: xr.Dataset, lev: Level, geo: dict, kind: dict[int, str], summit_xy: tuple, summit_z: float
) -> xr.Dataset:
    z = lev.z[:, None, None]
    dem = s["elevation"].values[None]
    d = dem - z
    ice = s["ice_thickness"].values[None]
    su = s["surface_unit"].values[None]
    br = s["bedrock_unit"].values[None]
    br_thick = s["bedrock_unit_under"].values[None]
    base = s["edifice_base"].values[None]
    foot = s["footprint"].values[None].astype(bool)

    t_unc = np.zeros_like(su, dtype=float)
    for uid, t in geo["unconsolidated_thickness_m"].items():
        t_unc = np.where(su == int(uid), float(t), t_unc)

    thin = np.zeros_like(br, dtype=float)
    for uid, t in geo["max_thickness_m"].items():
        thin = np.where(br == uid, t, thin)
    br = np.where((thin > 0) & (d > ice + t_unc + thin), br_thick, br)
    kbr = np.vectorize(lambda u: kind.get(int(u), ""))(br)
    br_base = np.where(kbr == "pluton", geo["pluton_base_z"], geo["supracrustal_base_z"])

    unit = np.full(np.broadcast_shapes(d.shape, su.shape), MIDDLE, dtype=np.uint8)
    unit = np.where(z > br_base, br, unit)
    cap = (su == CAP) | ((su == EDIFICE) & ~foot)
    unit = np.where(cap & (d < ice + t_unc + geo["cap_thickness_m"]), su, unit)
    unit = np.where(foot & (z > base), EDIFICE, unit)
    unit = np.where(d < ice + t_unc, np.where(t_unc > 0, su, unit), unit)
    unit = np.where(d < ice, ICE, unit)
    unit = np.where(d < 0, AIR, unit).astype(np.uint8)

    xx, yy = np.meshgrid(lev.x, lev.y)
    mb = geo["magma_body"]
    inside = ellipsoid(
        xx[None], yy[None], z, *summit_xy, mb["center_z"], mb["semi_axis_h_m"], mb["semi_axis_v_m"]
    )
    unit = np.where(inside & (unit != AIR), MAGMA, unit).astype(np.uint8)

    al = geo["alteration"]
    if al.get("source") == "finn_2001":
        # S22 maps from the helicopter EM survey; depth below the glacier bed (the EM sounds the rock)
        from rainier3d.alteration.finn2001 import alteration_3d

        fields = {v: s[v].fillna(0).values[None] for v in s.data_vars if v.startswith(("alt_a_", "alt_doi_"))}
        if not fields:
            raise ValueError("alteration source finn_2001 needs the S22 maps: run S22, then S3")
        allowed = np.isin(unit, al["finn_2001"]["units"])
        alt = alteration_3d(fields, d - np.nan_to_num(ice), allowed)
    else:
        r2 = ((xx - summit_xy[0]) ** 2 + (yy - summit_xy[1]) ** 2)[None]
        fz = np.clip((z - al["z_bottom"]) / (summit_z - al["z_bottom"]), 0, 1)
        alt = np.exp(-r2 / al["r0_m"] ** 2) * fz
    alt = np.where((unit == AIR) | (unit == ICE), 0.0, alt).astype(np.float32)

    coords = {"z": lev.z, "y": lev.y, "x": lev.x}
    dims = ("z", "y", "x")
    return xr.Dataset(
        {
            "unit": (dims, unit),
            "alteration": (dims, alt),
            "depth": (dims, np.broadcast_to(d, unit.shape).astype(np.float32)),
            "elevation": (("y", "x"), s["elevation"].values.astype(np.float32)),
        },
        coords=coords,
        attrs={"dx": lev.dx, "dz": lev.dz},
    )


def build(dom: Domain, surf: xr.Dataset, units_cfg: dict) -> tuple[xr.Dataset, dict[str, xr.Dataset]]:
    geo = dict(units_cfg["geometry"])
    kind = kinds(units_cfg)
    geo["max_thickness_m"] = {
        int(k): float(v["max_thickness_m"]) for k, v in units_cfg["units"].items() if "max_thickness_m" in v
    }
    su = surf["surface_unit"].values
    dem = surf["elevation"].values
    br = bedrock_units(su, kind)
    br_under = bedrock_units(su, kind, exclude=tuple(geo["max_thickness_m"]))
    foot = edifice_footprint(
        su,
        dom.x,
        dom.y,
        dom.summit_xy,
        geo["edifice"]["radius_m"],
        geo["edifice"]["closing_m"],
        dom.surface_res_m,
    )
    base = edifice_base(dem, foot, su, kind, dom.x, dom.y)
    base = np.where(foot, np.minimum(base, dem - surf["ice_thickness"].values), np.nan)
    surf2 = surf.assign(
        bedrock_unit=(("y", "x"), br.astype(np.uint8)),
        bedrock_unit_under=(("y", "x"), br_under.astype(np.uint8)),
        footprint=(("y", "x"), foot),
        edifice_base=(("y", "x"), np.where(foot, base, dem)),
    )
    summit_z = float(dem.max())
    levels = {
        name: build_level(surface_on_level(surf2, lev), lev, geo, kind, dom.summit_xy, summit_z)
        for name, lev in dom.levels.items()
    }
    surf2["edifice_base"] = surf2["edifice_base"].where(foot)
    return surf2, levels
