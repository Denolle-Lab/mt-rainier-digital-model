"""Command line for the published rainier3d products (``rainier3d`` or ``python -m rainier3d``).

  rainier3d list
  rainier3d fetch model
  rainier3d export model --format specfem --bbox -122.0 46.7 -121.6 47.0 --dx 250 --dz 250 --zmin -10000 \
                         --out out/tomography_model.xyz
  rainier3d export model --format nll --dx 500 --dz 500 --out out/nll/rainier3d
  rainier3d export surface --layers elevation soil_thickness gedi_biomass --out out/surface/
  rainier3d sample --lon -121.76 --lat 46.85 --depth 5000

``--model PATH`` uses a local model.zarr instead of the published one (e.g. a pipeline build).
"""

from __future__ import annotations

import argparse
import json
import sys

from rainier3d import api


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rainier3d", description="Download and format rainier3d products.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="published products")
    f = sub.add_parser("fetch", help="download a product into the cache ($RAINIER3D_DATA)")
    f.add_argument("product")
    f.add_argument("--force", action="store_true")
    e = sub.add_parser("export", help="write the model or its surface layers for other codes")
    e.add_argument("what", choices=["model", "surface"])
    e.add_argument("--model", help="local model.zarr (default: the published product)")
    e.add_argument("--format", choices=api.FORMATS, default="netcdf")
    e.add_argument("--bbox", nargs=4, type=float, metavar=("LON_W", "LAT_S", "LON_E", "LAT_N"))
    e.add_argument("--dx", type=float, default=500.0)
    e.add_argument("--dz", type=float, default=250.0)
    e.add_argument("--zmin", type=float, default=-20000.0, help="lowest elevation, m (NAVD88)")
    e.add_argument(
        "--zmax", type=float, default=None, help="highest elevation, m (default: above the summit)"
    )
    e.add_argument("--vars", nargs="+", default=["vp", "vs", "rho", "qp", "qs"])
    e.add_argument("--layers", nargs="+", help="surface layers (default: all)")
    e.add_argument("--out", required=True)
    s = sub.add_parser("sample", help="model values at one point")
    s.add_argument("--lon", type=float, required=True)
    s.add_argument("--lat", type=float, required=True)
    s.add_argument("--depth", type=float, required=True, help="metres below sea level")
    s.add_argument("--model")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for k, p in api.products().items():
            state = f"{p['version']}, {p['bytes'] / 1e6:.0f} MB" if p.get("url") else "not published yet"
            print(f"{k:14s} {state:24s} {p['description']}\n{'':14s} licence: {p['license']}")
        return 0
    if a.cmd == "fetch":
        print(api.fetch(a.product, force=a.force))
        return 0
    tree = api.open_model(getattr(a, "model", None))
    if a.cmd == "sample":
        print(json.dumps(api.sample(tree, a.lon, a.lat, a.depth), indent=1))
        return 0
    if a.what == "surface":
        for p in api.export_surface(tree, a.out, a.layers):
            print(p)
        return 0
    g = api.grid(tree, bbox=a.bbox, dx=a.dx, dz=a.dz, zmin=a.zmin, zmax=a.zmax, variables=a.vars)
    for p in api.export(g, a.format, a.out, tree=tree):
        print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
