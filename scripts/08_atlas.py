"""S8: build the Rainier Sensor Atlas data -> web/atlas/data/ (then `pixi run atlas` to serve it).

Writes sites.geojson (one point per site, sensors as a JSON string property), das.geojson (cable
segments by lithology) and das_channels.geojson, events.geojson (PNSN, ComCat), overlay images
with their corner coordinates, and summary.json (families, counts, regions).
Also writes georeferenced GeoTIFFs of the KMZ overlays to data/processed/overlays/ for the 3D scene.
"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path

import numpy as np
import requests
import yaml
from PIL import Image

from rainier3d.config.domain import REPO, load_domain
from rainier3d.io import kmz
from rainier3d.sensors import inventory as inv

WEB = REPO / "web" / "atlas"
DATA = WEB / "data"
OVERLAYS = REPO / "configs" / "overlays.yaml"
REGIONS = [  # name, [west, south, east, north]
    ("Model domain", None),
    ("Summit & edifice", [-121.84, 46.80, -121.68, 46.90]),
    ("Paradise–Nisqually DAS corridor", [-121.93, 46.72, -121.72, 46.80], {"pitch": 35, "bearing": 30}),
    ("West Rainier Seismic Zone", [-122.05, 46.75, -121.90, 47.00]),
    ("Carbon River & Mowich", [-121.95, 46.92, -121.75, 47.05]),
    ("Sunrise & White River", [-121.70, 46.85, -121.50, 46.98]),
    ("Ohanapecosh & Cowlitz", [-121.62, 46.65, -121.45, 46.80]),
    ("2025 node deployment extent", "nodes"),
]


def feature(geom, props):
    return {"type": "Feature", "geometry": geom, "properties": props}


def clean(o):
    """NaN/inf -> None, numpy scalars -> Python: browsers reject NaN in JSON."""
    if isinstance(o, dict):
        return {k: clean(v) for k, v in o.items()}
    if isinstance(o, list | tuple):
        return [clean(v) for v in o]
    if isinstance(o, np.generic):
        o = o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def write(name, obj):
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / name).write_text(json.dumps(clean(obj), separators=(",", ":"), allow_nan=False))


def site_features(sites, fam):
    feats = []
    for s in sites:
        counts = {}
        for x in s["sensors"]:
            counts[x["family"]] = counts.get(x["family"], 0) + 1
        prim = max(counts, key=counts.get)
        feats.append(
            feature(
                {"type": "Point", "coordinates": [s["lon"], s["lat"]]},
                {
                    "id": s["id"],
                    "name": s["name"],
                    "source": s["source"],
                    "status": s["status"],
                    "elev": s.get("elev"),
                    "url": s.get("url", ""),
                    "family": prim,
                    "families": ",".join(sorted(counts)),
                    "n": len(s["sensors"]),
                    "in_model": s["in_model_domain"],
                    "deployers": s.get("deployers", ""),
                    "notes": s.get("notes", ""),
                    "sensors": json.dumps(s["sensors"]),
                    "color": fam[prim]["color"],
                },
            )
        )
    return feats


def das_features(das_csv):
    d = inv.das_channels(das_csv)
    seg, segs = [], []
    lith = d.Lithology.fillna("?").values
    for i in range(len(d)):
        seg.append(i)
        if i == len(d) - 1 or lith[i + 1] != lith[i]:
            idx = seg + ([i + 1] if i + 1 < len(d) else [])
            segs.append(
                feature(
                    {"type": "LineString", "coordinates": d[["lon", "lat"]].values[idx].tolist()},
                    {
                        "lithology": lith[i],
                        "ch0": int(d.Channel.iloc[seg[0]]),
                        "ch1": int(d.Channel.iloc[seg[-1]]),
                    },
                )
            )
            seg = []
    pts = [
        feature(
            {"type": "Point", "coordinates": [r.lon, r.lat]},
            {
                "ch": int(r.Channel),
                "optical_m": r.optical_m,
                "road_m": r.road_m,
                "elev": r.elev,
                "lithology": r.Lithology,
                "notice": r.Notice if isinstance(r.Notice, str) else "",
            },
        )
        for r in d.itertuples()
    ]
    return segs, pts, len(d)


def events(dom, start="2015-01-01", minmag=0.5):
    w, s, e, n = dom.bbox_4326
    r = requests.get(
        "https://earthquake.usgs.gov/fdsnws/event/1/query",
        params=dict(
            format="geojson",
            catalog="uw",
            starttime=start,
            minmagnitude=minmag,
            minlatitude=s,
            maxlatitude=n,
            minlongitude=w,
            maxlongitude=e,
            orderby="time-asc",
            limit=20000,
        ),
        timeout=180,
    )
    r.raise_for_status()
    out = []
    for f in r.json()["features"]:
        lon, lat, dep = f["geometry"]["coordinates"]
        p = f["properties"]
        out.append(
            feature(
                {"type": "Point", "coordinates": [lon, lat]},
                {"mag": p["mag"], "depth": dep, "time": p["time"], "type": p["type"], "id": f["id"]},
            )
        )
    return out


def overlays(dom, cfg):
    meta = {}
    outdir = dom.path("processed") / "overlays"
    for key, c in cfg.items():
        if "kmz" in c:
            img, b = kmz.mosaic(Path(c["kmz"]).expanduser())
            if c.get("crop"):
                left, t, r, btm = c["crop"]
                h, w = img.shape[:2]
                W, S, E, N = b
                img = img[int(t * h) : int(btm * h), int(left * w) : int(r * w)]
                b = (W + left * (E - W), N - btm * (N - S), W + r * (E - W), N - t * (N - S))
            if c.get("white_transparent"):
                img = img.copy()
                img[(img[..., :3] > 235).all(-1), 3] = 0
            kmz.to_geotiff(img, b, outdir / f"{key}.tif")
            m = kmz.to_web(img, b, DATA / key, jpeg=c.get("jpeg", False))
        else:
            m = model_geology_png(dom, DATA / key)
        meta[key] = {
            **m,
            "label": c["label"],
            "opacity": c["opacity"],
            "registration": c.get("registration", ""),
        }
    return meta


def model_geology_png(dom, stem):
    import matplotlib
    import rioxarray  # noqa: F401

    from rainier3d.io.store import read

    u = read(dom.path("processed") / "surface.zarr")["surface_unit"].rio.write_crs(dom.crs)
    u = u.sortby("y", ascending=False).rio.reproject("EPSG:4326", nodata=0)
    cmap = matplotlib.colormaps["tab20"]
    rgba = (cmap(np.clip(u.values, 0, 21) / 21.0) * 255).astype(np.uint8)
    rgba[u.values == 0, 3] = 0
    Image.fromarray(rgba).save(stem.with_suffix(".png"))
    w, s, e, n = (float(v) for v in u.rio.bounds())
    m = {
        "url": stem.with_suffix(".png").name,
        "coordinates": [[w, n], [e, n], [e, s], [w, s]],
        "bounds": [w, s, e, n],
    }
    stem.with_suffix(".json").write_text(json.dumps(m))
    return m


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--das", default=str(Path.home() / "Downloads/Paradise2NisquallyEntrace_Channels.csv"))
    a = ap.parse_args()
    dom = load_domain()
    fam = inv.families()["families"]

    sites = inv.inventory(dom)
    write("sites.geojson", {"type": "FeatureCollection", "features": site_features(sites, fam)})
    segs, pts, nch = das_features(Path(a.das))
    write("das.geojson", {"type": "FeatureCollection", "features": segs})
    write("das_channels.geojson", {"type": "FeatureCollection", "features": pts})
    ev = events(dom)
    write("events.geojson", {"type": "FeatureCollection", "features": ev})
    ov = overlays(dom, yaml.safe_load(OVERLAYS.read_text()))
    model = dom.path("processed") / "model.zarr"
    mmeta = None
    if model.exists():  # the 3D model for sections, depth slices and the underground view
        from rainier3d.export.web import export_model
        from rainier3d.io.store import read_tree

        mmeta = export_model(read_tree(model), dom, DATA / "model")
        logging.info("model export: %.1f MB (gzip)", mmeta["bytes"] / 1e6)

    counts = {k: {"sites": 0, "sensors": 0, "operating": 0} for k in fam}
    for s in sites:
        for x in s["sensors"]:
            counts[x["family"]]["sensors"] += 1
            counts[x["family"]]["operating"] += x["status"] == "operating"
        for f in {x["family"] for x in s["sensors"]}:
            counts[f]["sites"] += 1
    counts["das"] = {"sites": 1, "sensors": nch, "operating": nch}
    regions = []
    for name, box, *cam in REGIONS:
        if box is None:
            box = list(dom.bbox_4326)
        elif box == "nodes":
            nl = [(s["lon"], s["lat"]) for s in sites if s["id"].startswith("node-")]
            box = [min(p[0] for p in nl), min(p[1] for p in nl), max(p[0] for p in nl), max(p[1] for p in nl)]
        n = sum(box[0] <= s["lon"] <= box[2] and box[1] <= s["lat"] <= box[3] for s in sites)
        regions.append(
            {"name": name, "bbox": [float(v) for v in box], "sites": int(n), **(cam[0] if cam else {})}
        )
    summary = {
        "title": "Mount Rainier Sensor Atlas",
        "families": fam,
        "counts": counts,
        "regions": regions,
        "n_sites": len(sites),
        "n_sensors": int(sum(len(s["sensors"]) for s in sites)),
        "n_operating": int(sum(x["status"] == "operating" for s in sites for x in s["sensors"])),
        "n_events": len(ev),
        "overlays": ov,
        "model": {"available": mmeta is not None},
        "domain_bbox": [float(v) for v in dom.bbox_4326],
        "summit": list(dom.summit_lonlat),
        "sources": "FDSN station metadata: EarthScope. GNSS: EarthScope/UNAVCO. "
        "Met & streamflow: Synoptic via "
        "gaia-hazlab/catalog. Nodes: 2025 UW deployment sheet. DAS: Paradise-Nisqually Entrance channel "
        "table. Events: PNSN via USGS ComCat (M>=0.5, 2015-). "
        "Terrain: AWS Terrain Tiles (Mapzen/3DEP). Geology: USGS I-432 (Fiske et al. 1963). "
        "Soils: NRCS/NPS general soil map (approx. placement).",
    }
    write("summary.json", summary)
    logging.info(
        "%d sites, %d sensors (%d operating), %d DAS channels, %d events, overlays %s",
        summary["n_sites"],
        summary["n_sensors"],
        summary["n_operating"],
        nch,
        len(ev),
        list(ov),
    )


if __name__ == "__main__":
    main()
