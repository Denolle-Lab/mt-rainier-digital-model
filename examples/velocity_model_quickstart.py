"""Quick start with the rainier3d velocity model: download, inspect, sample, plot, export.

    pip install "git+https://github.com/Denolle-Lab/mt-rainier-digital-model"
    python examples/velocity_model_quickstart.py            # downloads the model once (about 200 MB)
    python examples/velocity_model_quickstart.py --let      # the model after the tomography (model_let)

Writes out/quickstart_profile.png, out/quickstart_section.png and out/rainier3d_500m.nc. The guide is
docs/velocity_model.md.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

import rainier3d.api as r3

SUMMIT = (-121.7603, 46.8523)  # Columbia Crest (lon, lat)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--let", action="store_true", help="use model_let (after the S37 tomography)")
    ap.add_argument("--archive", help="a local product archive instead of the download (testing)")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    product = "model_let" if a.let else "model"
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    # 1. Open: an xarray DataTree with /surface, /cz (critical zone) and /L1, /L2, /L3 (subsurface levels)
    if a.archive:
        sha = hashlib.sha256(Path(a.archive).read_bytes()).hexdigest()
        root = r3.fetch(product, url=a.archive, sha256=sha, force=True)
        tree = r3.open_model(next(root.glob("*.zarr")))
    else:
        tree = r3.open_model(product=product)
    l1 = tree["L1"].to_dataset()
    print(l1)  # every variable carries units and long_name
    print(dict(zip(l1.unit.attrs["flag_values"], l1.unit.attrs["flag_meanings"].split(), strict=True)))

    # 2. One point: lon, lat and depth below sea level (m); returns the level it came from
    print(r3.sample(tree, *SUMMIT, 5000))

    # 3. A vertical profile under the summit through the three levels; air cells are NaN
    x, y = 594500.0, 5189500.0  # UTM 10N metres, near the summit
    fig, ax = plt.subplots(figsize=(4, 6))
    for lev in ("L1", "L2", "L3"):
        c = tree[lev].to_dataset().sel(x=x, y=y, method="nearest")
        for v, ls in (("vp", "-"), ("vs", "--")):
            ax.plot(c[v] / 1e3, c.z / 1e3, ls, color="k" if lev == "L1" else ("C0" if lev == "L2" else "C1"))
    ax.set(
        xlabel="Vp (solid), Vs (dashed), km/s", ylabel="elevation (km, NAVD88)", title="Profile at the summit"
    )
    fig.savefig(out / "quickstart_profile.png", dpi=150, bbox_inches="tight")

    # 4. A west-east section of Vs through the summit on one uniform grid (air flagged by `air`)
    g = r3.grid(tree, dx=500, dz=250, zmin=-15000)
    sec = g.vs.where(g.air == 0).sel(y=y, method="nearest")
    fig, ax = plt.subplots(figsize=(8, 3.5))
    sec.plot(ax=ax, x="x", y="z", cmap="viridis_r", cbar_kwargs={"label": "Vs (m/s)"})
    ax.set(title="Vs, west-east through the summit", xlabel="easting (m)", ylabel="elevation (m)")
    fig.savefig(out / "quickstart_section.png", dpi=150, bbox_inches="tight")

    # 5. The top 150 m in detail: the critical-zone columns (depth below the ground or the glacier bed)
    from pyproj import Transformer

    lx, ly = Transformer.from_crs("EPSG:4326", "EPSG:32610", always_xy=True).transform(-121.813, 46.750)
    cz = tree["cz"].to_dataset().sel(x=lx, y=ly, method="nearest")  # Longmire, in the Nisqually valley
    print(
        "Longmire: bases of soil, cover, weathered, fractured (m):",
        [round(float(cz[k]), 1) for k in ("z_soil", "z_cover", "z_weathered", "z_fractured")],
    )
    print("Longmire Vs (m/s) at 0, 5, 10, 30, 60 m:",
          [round(float(cz.vs.sel(cz_depth=d, method="nearest"))) for d in (0, 5, 10, 30, 60)])  # fmt: skip

    # 6. Export the uniform grid for another code (also "nll", "emc", "specfem", "pylith", "csv")
    print(r3.export(g, "netcdf", out / "rainier3d_500m.nc"))
    ground = g.air == 0
    print(
        "Vp/Vs below the ground:",
        float((g.vp / g.vs).where(ground).min()),
        float((g.vp / g.vs).where(ground).max()),
    )


if __name__ == "__main__":
    main()
