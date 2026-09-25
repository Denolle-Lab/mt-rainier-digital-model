"""
Visualize GEDI L3 Gridded Land Surface Metrics (canopy height and/or
ground elevation), with station markers overlaid.

Panel order is always: mean value(s) -> std dev(s) -> footprint counts.
Only panels whose files actually exist in CROP_DIR are shown, so this
works whether you downloaded just canopy height, just elevation, or both.

No masking is applied here -- L3 has no quality flag; NASA's own
"counts" layer is the closest analog, shown as its own panel.

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
CROP_DIR = "../../output_non-seismic_code/GEDI/gedi_l3/cropped"
STATION_CSV = "../../seismic_data/df_station_locations.csv"
OUT_FIG = "../../output_figures/gedi_l3_map.png"
TITLE = "GEDI L3 Gridded Land Surface Metrics"

# Cap the color scale at (max - N*std) so a few outlier pixels don't
# wash out the range. Set to None to disable.
VMAX_STD_MULTIPLIER = 1
# ---------------------------------------------------------------

# Panel order: all means -> all std devs -> counts (always last)
PANELS = [
    {"suffix": "rh100_mean", "label": "Mean Canopy Height [m]", "cmap": "YlGn",
     "vmin": 0, "extend": "max"},
    {"suffix": "elev_lowestmode_mean", "label": "Mean Ground Elevation [m]",
     "cmap": "terrain", "vmin": None, "extend": "neither"},
    {"suffix": "rh100_stddev", "label": "Canopy Height Std Dev [m]", "cmap": "magma",
     "vmin": 0, "extend": "max"},
    {"suffix": "elev_lowestmode_stddev", "label": "Ground Elevation Std Dev [m]",
     "cmap": "magma", "vmin": 0, "extend": "max"},
    {"suffix": "counts", "label": "Footprint Count per Cell [-]", "cmap": "viridis",
     "vmin": 0, "extend": "max"},
]

data_by_suffix = {}
extent = None
for panel in PANELS:
    path = os.path.join(CROP_DIR, f"L3_{panel['suffix']}.tif")
    if not os.path.exists(path):
        continue
    data, extent = read_band_reprojected(path)
    print(f"L3_{panel['suffix']}.tif: shape {data.shape}, "
          f"valid pixels {int(np.sum(~np.isnan(data)))}")
    data_by_suffix[panel["suffix"]] = data

if not data_by_suffix:
    raise FileNotFoundError(f"No L3 files found in {CROP_DIR}")

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
    if VMAX_STD_MULTIPLIER is not None and np.any(~np.isnan(data)):
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
