"""
01_download_lidar_tiles.py

Downloads exactly the DSM/DTM lidar tiles needed to compute CHM_height_meter
at every station -- nothing more -- from the WA DNR Lidar Portal
(https://lidarportal.dnr.wa.gov/), the source behind the paper's
WGS2023RainierWali citation. That portal doesn't expose a documented public
API; the endpoints below were reverse-engineered from its own web app
(js/lidar.js) and confirmed to work:

  POST /query    body: geojson=<GeoJSON geometry>
                 -> JSON list of {dataset_id, dataset_name, project_name,
                    files, bytes} for every dataset intersecting that
                    geometry (DSM, DTM, DSM/DTM Hillshade, Metadata, Point
                    Cloud, one entry per lidar acquisition project).
  GET  /download?geojson=<geometry>&ids=<comma-separated dataset_id list>
                 -> a ZIP, containing only the individual GeoTIFF tiles
                    (per dataset) whose footprint intersects the geometry
                    -- not the whole project. Requires a 'dlgate' cookie,
                    set by first GETting / (the portal's homepage); no
                    login needed, this is just a lightweight bot gate.

The WA DNR lidar holdings are organized into many separate, adjacently-
tiled acquisition projects (e.g. "Rainier Wali 2022", "Puyallup Watershed
Wali 2022", "Cascades North Wali 2023", ...) each covering a specific
watershed, not one single statewide project -- despite the paper's single
WGS2023RainierWali citation. This script does NOT hardcode one project
name; instead, for each station it finds whichever project(s) actually
cover it and downloads from those, filtering to project names containing
"wali" (case-insensitive) so only the intended 2022/2023 WA DNR lidar
campaign is used, never an older or unrelated overlapping survey. Some
outlying stations may fall outside all "Wali" project footprints entirely
-- those are reported, not silently skipped, and simply won't get a
CHM_height_meter value from 02_process_chm.py (written as NaN, same
graceful fallback merge_station_veg.py already has for a missing CHM
file).

Why clustering, not one download: the 240 stations span roughly 200 km
end to end, mostly empty of stations. Requesting DSM+DTM for one big
bounding box around all of them would pull in tiles over that empty
space too -- wasteful given each DSM/DTM tile is itself already
hundreds of MB to ~1 GB (native ~1.5 ft resolution). Instead, stations
are grid-snapped and flood-fill merged into separate geographic
clusters (GRID_CELL_DEG, 8-connected), and each cluster gets its own
small, buffered bounding-box query/download -- tighter geometries also
avoid a server-side timeout we hit when sending one complex, many-part
geometry in a single request.

Total size is still large: DSM+DTM tiles across every matched cluster
add up to roughly 100+ GB (confirmed against the live API while writing
this script). That's inherent to the data (sub-meter resolution over a
~200 km network), not something this script can shrink further --
downloading only the intersecting tiles per cluster is already the
minimum the portal's API can hand back.

Resumable: each successfully downloaded+extracted cluster is marked with
a small sentinel file, and individual tiles already present in RAW_DIR
are skipped on extraction -- so an interrupted run (very plausible at
this size) can just be restarted.

Output: RAW_DIR/<project_slug>/<dsm|dtm>/<tile>.tif, one project
sub-folder per WA DNR "Wali" project that actually covers a station.
02_process_chm.py reads directly from here.

Usage
-----
    python 01_download_lidar_tiles.py
"""

import os
import io
import json
import zipfile
import numpy as np
import pandas as pd
import requests

# ═════════════════════════════════════════════════════════════════════════════
# CONFIG
# ═════════════════════════════════════════════════════════════════════════════
STATIONS_CSV = "../../seismic_data/df_station_locations.csv"
RAW_DIR = "../../output_non-seismic_code/CHM/raw"

BASE_URL = "https://lidarportal.dnr.wa.gov"

# Station clustering: grid-snap to this cell size (degrees, ~5.5 km at this
# latitude), then flood-fill merge 8-connected occupied cells into clusters
# -- keeps each cluster's query/download geometry a single simple rectangle
# (complex multi-part geometries were seen to cause a server-side timeout).
GRID_CELL_DEG = 0.05
# Extra margin around each cluster's cell extent (degrees, ~5.5 km --
# roughly one full tile width). Confirmed empirically while writing this
# script: a station sitting near its grid cell's edge, queried with only
# a ~1.1 km margin, can miss the one tile that actually covers it even
# though the query geometry does contain the station's point -- the
# portal's own spatial index doesn't reliably return every intersecting
# tile for a very tight query box. A margin of about one tile width
# avoids that.
BUFFER_DEG = 0.05

# Only download datasets from projects matching this (case-insensitive
# substring) -- the WA DNR 2022/2023 lidar campaign this paper's
# WGS2023RainierWali citation refers to; never an older overlapping survey.
PROJECT_NAME_FILTER = "wali"
WANTED_DATASETS = ("DSM", "DTM")

REQUEST_TIMEOUT_S = 120
DOWNLOAD_TIMEOUT_S = 900
# ═════════════════════════════════════════════════════════════════════════════


def get_session():
    """A requests.Session with the 'dlgate' cookie /download requires --
    set by the portal on any GET of its homepage, no login involved."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; canopy-storage-seismic CHM download script)",
    })
    resp = session.get(BASE_URL + "/", timeout=REQUEST_TIMEOUT_S)
    resp.raise_for_status()
    if "dlgate" not in session.cookies.get_dict():
        raise RuntimeError(
            "Didn't receive the expected 'dlgate' cookie from the lidar "
            "portal homepage -- it may have changed how it gates downloads. "
            "Check https://lidarportal.dnr.wa.gov/ manually."
        )
    return session


def cluster_stations(df, cell_deg=GRID_CELL_DEG, buffer_deg=BUFFER_DEG):
    """Grid-snap station (lon, lat) to `cell_deg` cells, flood-fill merge
    8-connected occupied cells into clusters, and return one buffered
    (minlon, minlat, maxlon, maxlat) bbox per cluster, plus the list of
    station indices (into df) that fall in each."""
    gi = np.floor(df["longitude"] / cell_deg).astype(int)
    gj = np.floor(df["latitude"] / cell_deg).astype(int)
    cell_to_stations = {}
    for idx, (ci, cj) in enumerate(zip(gi, gj)):
        cell_to_stations.setdefault((ci, cj), []).append(idx)

    cells_set = set(cell_to_stations)
    visited = set()
    clusters = []
    for c in list(cells_set):
        if c in visited:
            continue
        stack, comp = [c], []
        visited.add(c)
        while stack:
            cx, cy = stack.pop()
            comp.append((cx, cy))
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nb = (cx + dx, cy + dy)
                    if nb in cells_set and nb not in visited:
                        visited.add(nb)
                        stack.append(nb)
        clusters.append(comp)

    out = []
    for comp in clusters:
        xs = [c[0] * cell_deg for c in comp]
        ys = [c[1] * cell_deg for c in comp]
        bbox = (
            min(xs) - buffer_deg, min(ys) - buffer_deg,
            max(xs) + cell_deg + buffer_deg, max(ys) + cell_deg + buffer_deg,
        )
        station_idx = [i for c in comp for i in cell_to_stations[c]]
        out.append((bbox, station_idx))
    return out


def bbox_to_geojson(bbox):
    minlon, minlat, maxlon, maxlat = bbox
    return {
        "type": "Polygon",
        "coordinates": [[
            [minlon, minlat], [maxlon, minlat],
            [maxlon, maxlat], [minlon, maxlat], [minlon, minlat],
        ]],
    }


def query_datasets(session, bbox):
    """POST /query for one bbox -- returns the raw list of dataset dicts
    the portal has intersecting it (every project, every dataset type)."""
    geojson = json.dumps(bbox_to_geojson(bbox))
    resp = session.post(
        BASE_URL + "/query", data={"geojson": geojson}, timeout=REQUEST_TIMEOUT_S,
    )
    resp.raise_for_status()
    return resp.json()


def matching_datasets(datasets):
    """DSM/DTM datasets from a 'Wali' project only."""
    return [
        d for d in datasets
        if d["dataset_name"] in WANTED_DATASETS
        and PROJECT_NAME_FILTER in d["project_name"].lower()
    ]


def project_slug(project_name):
    return project_name.strip().lower().replace(" ", "_")


def download_cluster(session, bbox, dataset_ids, raw_dir):
    """GET /download for this bbox + dataset ids, streamed into memory
    (single ZIP, not re-downloadable piecemeal) then extracted -- skipping
    any .tif already present in raw_dir (already fetched by an earlier,
    possibly overlapping cluster, or a prior interrupted run)."""
    geojson = json.dumps(bbox_to_geojson(bbox))
    ids_param = ",".join(str(i) for i in dataset_ids)
    resp = session.get(
        BASE_URL + "/download",
        params={"geojson": geojson, "ids": ids_param},
        timeout=DOWNLOAD_TIMEOUT_S,
        stream=True,
    )
    resp.raise_for_status()
    buf = io.BytesIO()
    for chunk in resp.iter_content(chunk_size=1 << 20):
        buf.write(chunk)
    buf.seek(0)

    extracted, skipped = [], []
    with zipfile.ZipFile(buf) as zf:
        for member in zf.namelist():
            if not member.lower().endswith(".tif"):
                continue
            # member looks like datasetsB/<project_slug>/<dsm|dtm>/<file>.tif
            parts = member.split("/")
            dest = os.path.join(raw_dir, *parts[1:])
            if os.path.isfile(dest):
                skipped.append(dest)
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            with zf.open(member) as src, open(dest, "wb") as out:
                out.write(src.read())
            extracted.append(dest)
    return extracted, skipped


def main():
    df = pd.read_csv(STATIONS_CSV, dtype={"station": str})
    os.makedirs(RAW_DIR, exist_ok=True)
    session = get_session()

    clusters = cluster_stations(df)
    print(f"{len(df)} stations -> {len(clusters)} geographic cluster(s) to query/download.\n")

    uncovered_stations = []
    total_new_bytes = 0
    for i, (bbox, station_idx) in enumerate(clusters):
        marker = os.path.join(RAW_DIR, f".done_cluster_{i}")
        stations_here = df.iloc[station_idx]["station"].tolist()
        if os.path.isfile(marker):
            print(f"[cluster {i+1}/{len(clusters)}] stations {stations_here}: "
                  f"already done, skipping.")
            continue

        print(f"[cluster {i+1}/{len(clusters)}] stations {stations_here}: querying...")
        datasets = query_datasets(session, bbox)
        matches = matching_datasets(datasets)
        if not matches:
            print(f"  no '{PROJECT_NAME_FILTER}' DSM/DTM project covers this cluster -- "
                  f"these stations will have no CHM_height_meter (NaN).")
            uncovered_stations.extend(stations_here)
            open(marker, "w").close()
            continue

        by_project = {}
        for d in matches:
            by_project.setdefault(d["project_name"], {})[d["dataset_name"]] = d
        for proj, dsets in by_project.items():
            missing = set(WANTED_DATASETS) - set(dsets)
            if missing:
                print(f"  NOTE: project {proj!r} is missing {missing} in this area -- "
                      f"downloading what's available ({set(dsets)}).")

        ids = [d["dataset_id"] for d in matches]
        expected_bytes = sum(d["bytes"] for d in matches)
        print(f"  downloading {len(ids)} dataset(s) from {sorted(by_project)}, "
              f"~{expected_bytes / 1e9:.2f} GB expected...")
        extracted, skipped = download_cluster(session, bbox, ids, RAW_DIR)
        new_bytes = sum(os.path.getsize(p) for p in extracted)
        total_new_bytes += new_bytes
        print(f"  wrote {len(extracted)} new tile(s) ({new_bytes / 1e9:.2f} GB), "
              f"{len(skipped)} already present.")
        open(marker, "w").close()

    print(f"\nDone. {total_new_bytes / 1e9:.2f} GB newly downloaded this run.")
    if uncovered_stations:
        print(f"{len(uncovered_stations)} station(s) have no '{PROJECT_NAME_FILTER}' "
              f"DSM/DTM coverage at all: {uncovered_stations}")
        print("These will come out of 02_process_chm.py with CHM_height_meter = NaN.")


if __name__ == "__main__":
    main()
