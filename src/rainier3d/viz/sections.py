"""Static cross-sections through the model (matplotlib), for QC and figures."""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from rainier3d.petro.table import unit_names


def _stack(tree: xr.DataTree, var: str, axis: str, at: float, levels=("L1", "L2", "L3")):
    """Pieces of a vertical section (distance, z, values) from each level, ready for pcolormesh."""
    other = "y" if axis == "x" else "x"
    for lev in levels:
        ds = tree[lev].to_dataset()
        sec = ds[var].sel({other: at}, method="nearest")
        yield sec[axis].values, sec["z"].values, sec.transpose("z", axis).values


def section_figure(
    tree: xr.DataTree,
    axis: str,
    at: float,
    path,
    zmin: float = -12000,
    variables=("unit", "vp_geology", "vp_regional", "vp", "vs", "alteration"),
):
    names = unit_names()
    fig, axs = plt.subplots(
        len(variables), 1, figsize=(11, 2.6 * len(variables)), sharex=True, constrained_layout=True
    )
    for ax, var in zip(axs, variables, strict=True):
        cmap = "tab20" if var == "unit" else ("turbo_r" if var.startswith("v") else "magma")
        vmin, vmax = (
            (0, 21)
            if var == "unit"
            else ((1500, 6800) if var.startswith("vp") else (500, 3900) if var.startswith("vs") else (0, 1))
        )
        for d, z, v in _stack(tree, var, axis, at):
            v = np.where(v == 0, np.nan, v) if var == "unit" else v
            m = ax.pcolormesh(d / 1e3, z / 1e3, v, cmap=cmap, vmin=vmin, vmax=vmax, shading="nearest")
        surf = tree["surface"].to_dataset()["elevation"]
        surf = surf.sel({"y" if axis == "x" else "x": at}, method="nearest")
        ax.plot(surf[axis] / 1e3, surf / 1e3, "k", lw=0.8)
        ax.set_ylim(zmin / 1e3, 4.6)
        ax.set_ylabel("z (km NAVD88)")
        ax.set_title(var, loc="left", fontsize=10)
        cb = fig.colorbar(m, ax=ax, pad=0.01)
        if var == "unit":
            present = sorted({int(u) for *_, v in _stack(tree, var, axis, at) for u in np.unique(v) if u > 0})
            cb.set_ticks(present)
            cb.set_ticklabels([names[u] for u in present], fontsize=6)
    axs[-1].set_xlabel(f"{'easting' if axis == 'x' else 'northing'} (km, EPSG:32610)")
    fig.suptitle(f"section along {axis} at {'y' if axis == 'x' else 'x'} = {at:.0f} m", fontsize=11)
    fig.savefig(path, dpi=130)
    plt.close(fig)
    return path
