"""
Visualize self-gridded GEDI L2B PAI (from grid_gedi_l2b_pai.py), with
station markers overlaid.

Panel order is always: mean value -> uncertainty -> footprint count ->
distinct-track count (our quality gate, shown last).

Requirements:
    pip install rasterio pandas numpy matplotlib
"""

import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from gedi_utils import read_band_reprojected, compute_grid_shape

# ---------------------------------------------------------------
# USER SETTINGS
# ---------------------------------------------------------------
GRID_DIR = "../../output_non-seismic_code/GEDI/gedi_l2b_pai/gridded"
STATION_CSV = "../../seismic_data/df_station_locations.csv"
OUT_FIG = "../../output_figures/gedi_l2b_pai_map.png"
TITLE = "GEDI L2B Gridded PAI (self-binned, not an official NASA product)"

# Mask mean/SE using distinct-track count -- mirrors L4B's own
# requirement of >= 2 tracks for its primary (hybrid) estimator.
# Set to None to show everything unmasked.
MIN_TRACKS = 2

# Cap the color scale at (max - N*std) so a few outlier pixels don't
# wash out the range. Set to None to disable for a given panel.
VMAX_STD_MULTIPLIER = 1
# ---------------------------------------------------------------

# Panel order: mean -> uncertainty -> count -> quality gate (last)
PANELS = [
    {"suffix": "mean", "label": "Mean PAI [m$^2$/m$^2$]", "cmap": "YlGn",
     "vmin": 0, "extend": "max", "apply_std_cap": True},
    {"suffix": "SE", "label": "Standard Error [m$^2$/m$^2$]", "cmap": "magma",
     "vmin": 0, "extend": "max", "apply_std_cap": True},
    {"suffix": "count", "label": "Footprint Count per Cell [-]", "cmap": "viridis",
     "vmin": 0, "extend": "max", "apply_std_cap": True},
    {"suffix": "ntracks", "label": "Distinct Ground-Track Count [-]", "cmap": "cividis",
     "vmin": 0, "extend": "max", "apply_std_cap": False},
]

data_by_suffix = {}
extent = None
for panel in PANELS:
    path = os.path.join(GRID_DIR, f"L2B_PAI_{panel['suffix']}.tif")
    if not os.path.exists(path):
        print(f"Skipping {panel['suffix']} -- file not found: {path}")
        continue
    data, extent = read_band_reprojected(path)
    print(f"L2B_PAI_{panel['suffix']}.tif: shape {data.shape}, "
          f"valid pixels {int(np.sum(~np.isnan(data)))}")
    data_by_suffix[panel["suffix"]] = data

if MIN_TRACKS is not None and "ntracks" in data_by_suffix:
    good = data_by_suffix["ntracks"] >= MIN_TRACKS
    for suffix in ["mean", "SE"]:
        if suffix in data_by_suffix:
            data_by_suffix[suffix] = np.where(good, data_by_suffix[suffix], np.nan)
    print(f"Masked mean/SE to >= {MIN_TRACKS} tracks: {int(np.sum(good))} valid cells kept")

stations = pd.read_csv(STATION_CSV)

active_panels = [p for p in PANELS if p["suffix"] in data_by_suffix]
n_rows, n_cols = compute_grid_shape(len(active_panels))
fig, axes = plt.subplots(n_rows, n_cols, figsize=(6 * n_cols, 5 * n_rows),
                          constrained_layout=True, squeeze=False)
axes = axes.ravel()

for i, panel in enumerate(active_panels):
    data = data_by_suffix[panel["suffix"]]
    ax = axes[i]

    vmin = panel["vmin"]
    if panel["apply_std_cap"] and VMAX_STD_MULTIPLIER is not None and np.any(~np.isnan(data)):
        vmax = np.nanmax(data) - VMAX_STD_MULTIPLIER * np.nanstd(data)
    else:
        vmax = np.nanmax(data) if np.any(~np.isnan(data)) else 1

    im = ax.imshow(data, extent=extent, cmap=panel["cmap"], origin="upper",
                    vmin=vmin, vmax=vmax)
    fig.colorbar(im, ax=ax, shrink=0.8, extend=panel["extend"], label=panel["label"])
    ax.set_title(panel["label"], fontsize=10)

    ax.scatter(stations["longitude"], stations["latitude"], s=10,
               facecolor="red", edgecolor="black", linewidth=0.3, zorder=5)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_xlim(extent[0], extent[1])
    ax.set_ylim(extent[2], extent[3])
    ax.set_aspect("equal")

for j in range(len(active_panels), len(axes)):
    axes[j].axis("off")

fig.suptitle(TITLE, fontsize=14)
os.makedirs(os.path.dirname(OUT_FIG) or ".", exist_ok=True)
plt.savefig(OUT_FIG, dpi=200)
print(f"\nSaved figure to {os.path.abspath(OUT_FIG)}")
plt.show()
