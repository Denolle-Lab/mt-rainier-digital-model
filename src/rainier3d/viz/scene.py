"""3D scene: geology-draped DEM, fence slices of Vs, alteration isosurface, PNSN seismicity,
optional raster drape (a KMZ overlay GeoTIFF, e.g. USGS I-432) and sensors (atlas sites, DAS fiber)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pyvista as pv
import xarray as xr

from rainier3d.export.vtk import level_grid, surface_grid
from rainier3d.petro.table import unit_names


def _cut(mesh, summit_xy):
    pts = mesh.points
    return mesh.extract_points(
        ~((pts[:, 0] > summit_xy[0]) & (pts[:, 1] < summit_xy[1])), adjacent_cells=False
    )


def drape_mesh(surf: xr.Dataset, tif, crs: str, lift_m: float = 12.0, max_px: int = 4096):
    """DEM patch covering the GeoTIFF footprint, texture-mapped with the image (full resolution)."""
    import rioxarray  # noqa: F401
    from PIL import Image
    from pyproj import Transformer

    img = xr.open_dataarray(tif, engine="rasterio")
    w, s, e, n = img.rio.bounds()
    to_utm = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
    xs, ys = to_utm.transform([w, e, e, w], [s, s, n, n])
    sub = surf.sel(x=slice(min(xs), max(xs)), y=slice(min(ys), max(ys)))
    xx, yy = np.meshgrid(sub.x.values, sub.y.values)
    lon, lat = to_utm.transform(xx, yy, direction="INVERSE")
    inside = (lon >= w) & (lon <= e) & (lat >= s) & (lat <= n)
    grid = pv.StructuredGrid(xx, yy, sub["elevation"].values + lift_m)
    tc = np.c_[((lon - w) / (e - w)).ravel(order="F"), ((lat - s) / (n - s)).ravel(order="F")]
    grid.point_data["tcoords"] = tc
    grid = grid.extract_points(inside.ravel(order="F"), adjacent_cells=False)
    arr = np.moveaxis(img.values, 0, -1).astype(np.uint8)
    im = Image.fromarray(arr)
    im.thumbnail((max_px, max_px))
    return grid, pv.numpy_to_texture(np.asarray(im)[::-1])


def build_scene(
    tree: xr.DataTree,
    summit_xy: tuple,
    events: pd.DataFrame | None = None,
    off_screen: bool = True,
    cut_quadrant: bool = True,
    drape_tif=None,
    crs: str = "EPSG:32610",
    sites: list | None = None,
    das: pd.DataFrame | None = None,
    family_colors: dict | None = None,
) -> pv.Plotter:
    pl = pv.Plotter(off_screen=off_screen, window_size=(1600, 1000))
    pl.set_background("#10131a", top="#2b3a55")
    names = unit_names()

    surf = surface_grid(tree["surface"].to_dataset(), stride=2)
    if cut_quadrant:  # open the SE quadrant around the summit to expose the interior
        pts = surf.points
        keep = ~((pts[:, 0] > summit_xy[0]) & (pts[:, 1] < summit_xy[1]))
        surf = surf.extract_points(keep, adjacent_cells=False)
    present = sorted(int(u) for u in np.unique(surf.point_data["surface_unit"]) if u > 0)
    pl.add_mesh(
        surf,
        scalars="surface_unit",
        cmap="tab20",
        clim=(0, 21),
        categories=True,
        show_scalar_bar=False,
        smooth_shading=True,
        opacity=1.0,
    )
    pl.add_text(
        "surface: DNR GeMS 1:100k units -> model units\n" + ", ".join(names[u] for u in present),
        position="lower_left",
        font_size=7,
        color="w",
    )

    sds = tree["surface"].to_dataset()
    if drape_tif is not None:
        dm, tex = drape_mesh(sds, drape_tif, crs)
        if cut_quadrant:
            dm = _cut(dm, summit_xy)
        dm.active_texture_coordinates = dm.point_data["tcoords"]
        pl.add_mesh(dm, texture=tex, smooth_shading=True)

    def ground(x, y, lift):
        return sds["elevation"].interp(x=xr.DataArray(x), y=xr.DataArray(y)).values + lift

    if sites:
        from pyproj import Transformer

        tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        by_fam = {}
        for s_ in sites:
            p = s_["properties"]
            if p["status"] != "operating":
                continue
            by_fam.setdefault(p["family"], []).append(tf.transform(*s_["geometry"]["coordinates"]))
        for fam, xy in by_fam.items():
            xy = np.array(xy)
            z = ground(xy[:, 0], xy[:, 1], 60.0)
            ok = np.isfinite(z)
            if ok.any():
                pl.add_mesh(
                    pv.PolyData(np.c_[xy[ok], z[ok]]),
                    color=(family_colors or {}).get(fam, "w"),
                    point_size=9 if fam != "nodes" else 5,
                    render_points_as_spheres=True,
                )
    if das is not None and len(das):
        from pyproj import Transformer

        tf = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        x, y = tf.transform(das.lon.values, das.lat.values)
        line = pv.lines_from_points(np.c_[x, y, das.elev.values + 15.0])
        pl.add_mesh(line.tube(radius=35.0), color="#f8f9fa")

    for lev in ("L1", "L2", "L3"):
        g = level_grid(tree[lev].to_dataset()).cell_data_to_point_data()
        for normal, origin in ((("y"), summit_xy), (("x"), summit_xy)):
            o = (origin[0], origin[1], 0)
            sl = g.slice(normal=normal, origin=o)
            if cut_quadrant:
                sl = (
                    sl.clip(normal="x" if normal == "y" else "-y", origin=o, invert=False)
                    if sl.n_points
                    else sl
                )
            if sl.n_points:
                pl.add_mesh(
                    sl,
                    scalars="vs",
                    cmap="turbo_r",
                    clim=(500, 3900),
                    nan_opacity=0.0,
                    scalar_bar_args={"title": "Vs (m/s)", "color": "w"} if lev == "L1" else None,
                    show_scalar_bar=lev == "L1",
                )
        if lev == "L1":
            iso = g.contour([0.5], scalars="alteration")
            if iso.n_points:
                pl.add_mesh(iso, color="#f4d35e", opacity=0.55, label="alteration 0.5")
    if events is not None and len(events):
        pts = pv.PolyData(np.c_[events.x, events.y, events.z])
        pts["depth_km"] = -events.z.values / 1e3
        pl.add_mesh(
            pts,
            scalars="depth_km",
            cmap="cool",
            point_size=7,
            render_points_as_spheres=True,
            scalar_bar_args={"title": "PNSN depth (km)", "color": "w"},
        )
    pl.add_axes(color="w")
    pl.camera_position = [
        (summit_xy[0] + 45000, summit_xy[1] - 55000, 35000),
        (summit_xy[0], summit_xy[1], -2000),
        (0, 0, 1),
    ]
    return pl
