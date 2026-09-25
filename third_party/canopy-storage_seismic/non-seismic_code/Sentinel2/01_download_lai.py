"""
Step 2: Download Sentinel-2 LAI (10m) for a large AOI by tiling requests,
then mosaic into a single GeoTIFF.

Uses the OFFICIAL SNAP biophysical-processor LAI evalscript, cloned directly from:
https://github.com/sentinel-hub/custom-scripts/blob/master/sentinel-2/lai/script.js
(same neural network as ESA SNAP's Biophysical Processor — verified, not hand-derived)
"""
import os
import math
import time
from dotenv import load_dotenv
from sentinelhub import (
    SHConfig, BBox, CRS, MimeType, SentinelHubRequest,
    DataCollection, bbox_to_dimensions,
)
import rasterio
from rasterio.merge import merge
import numpy as np

load_dotenv()

# ---------------- Config ----------------
config = SHConfig()
config.sh_client_id = os.getenv("SH_CLIENT_ID")
config.sh_client_secret = os.getenv("SH_CLIENT_SECRET")
config.sh_base_url = "https://sh.dataspace.copernicus.eu"
config.sh_token_url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"

if not config.sh_client_id or not config.sh_client_secret:
    raise SystemExit("Missing SH_CLIENT_ID / SH_CLIENT_SECRET in .env")

# IMPORTANT: DataCollection.SENTINEL2_L2A points at the old Sinergise endpoint
# (services.sentinel-hub.com) by default, which will 401 with CDSE credentials.
# Redefine it to use the CDSE service URL explicitly.
CDSE_SENTINEL2_L2A = DataCollection.SENTINEL2_L2A.define_from(
    "cdse_s2l2a", service_url=config.sh_base_url
)

# ---------------- AOI ----------------
AOI = (-122.5, 46.0, -120.5, 48.0)  # min_lon, min_lat, max_lon, max_lat
RESOLUTION = 10  # meters
TIME_INTERVAL = ("2023-07-01", "2023-08-15")  # pick a cloud-free summer window for PNW
OUTPUT_DIR = "../../output_non-seismic_code/Sentinel2/lai_tiles"
MOSAIC_OUT = "../../output_non-seismic_code/Sentinel2/lai_mosaic_pnw.tif"

MAX_PX = 2400  # Sentinel Hub hard limit is 2500x2500; keep margin since bbox_to_dimensions can round up
SLEEP_BETWEEN_TILES = 3  # seconds; spaces out requests to avoid hitting CDSE's rate limit

os.makedirs(OUTPUT_DIR, exist_ok=True)

# ---------------- Evalscript ----------------
# Official SNAP biophysical LAI NN, adapted to output raw float LAI (not /3-scaled PNG)
# and to mask no-data pixels using dataMask.
EVALSCRIPT_LAI = """
//VERSION=3
var degToRad = Math.PI / 180;

function setup() {
  return {
    input: [{
      bands: [
        "B03","B04","B05","B06","B07","B8A","B11","B12",
        "viewZenithMean","viewAzimuthMean","sunZenithAngles","sunAzimuthAngles",
        "dataMask"
      ]
    }],
    output: [
      { id: "lai", bands: 1, sampleType: "FLOAT32" }
    ]
  };
}

function normalize(unnormalized, min, max) {
  return 2 * (unnormalized - min) / (max - min) - 1;
}
function denormalize(normalized, min, max) {
  return 0.5 * (normalized + 1) * (max - min) + min;
}
function tansig(input) {
  return 2 / (1 + Math.exp(-2 * input)) - 1;
}

function neuron1(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra) {
  var sum = 4.96238030555279
    - 0.023406878966470*b03 + 0.921655164636366*b04 + 0.135576544080099*b05
    - 1.938331472397950*b06 - 3.342495816122680*b07 + 0.902277648009576*b8a
    + 0.205363538258614*b11 - 0.040607844721716*b12 - 0.083196409727092*vz
    + 0.260029270773809*sz + 0.284761567218845*ra;
  return tansig(sum);
}
function neuron2(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra) {
  var sum = 1.416008443981500
    - 0.132555480856684*b03 - 0.139574837333540*b04 - 1.014606016898920*b05
    - 1.330890038649270*b06 + 0.031730624503341*b07 - 1.433583541317050*b8a
    - 0.959637898574699*b11 + 1.133115706551000*b12 + 0.216603876541632*vz
    + 0.410652303762839*sz + 0.064760155543506*ra;
  return tansig(sum);
}
function neuron3(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra) {
  var sum = 1.075897047213310
    + 0.086015977724868*b03 + 0.616648776881434*b04 + 0.678003876446556*b05
    + 0.141102398644968*b06 - 0.096682206883546*b07 - 1.128832638862200*b8a
    + 0.302189102741375*b11 + 0.434494937299725*b12 - 0.021903699490589*vz
    - 0.228492476802263*sz - 0.039460537589826*ra;
  return tansig(sum);
}
function neuron4(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra) {
  var sum = 1.533988264655420
    - 0.109366593670404*b03 - 0.071046262972729*b04 + 0.064582411478320*b05
    + 2.906325236823160*b06 - 0.673873108979163*b07 - 3.838051868280840*b8a
    + 1.695979344531530*b11 + 0.046950296081713*b12 - 0.049709652688365*vz
    + 0.021829545430994*sz + 0.057483827104091*ra;
  return tansig(sum);
}
function neuron5(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra) {
  var sum = 3.024115930757230
    - 0.089939416159969*b03 + 0.175395483106147*b04 - 0.081847329172620*b05
    + 2.219895367487790*b06 + 1.713873975136850*b07 + 0.713069186099534*b8a
    + 0.138970813499201*b11 - 0.060771761518025*b12 + 0.124263341255473*vz
    + 0.210086140404351*sz - 0.183878138700341*ra;
  return tansig(sum);
}
function layer2(n1,n2,n3,n4,n5) {
  return 1.096963107077220 - 1.500135489728730*n1 - 0.096283269121503*n2
    - 0.194935930577094*n3 - 0.352305895755591*n4 + 0.075107415847473*n5;
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return { lai: [-9999] };
  }
  var b03 = normalize(sample.B03, 0, 0.253061520471542);
  var b04 = normalize(sample.B04, 0, 0.290393577911328);
  var b05 = normalize(sample.B05, 0, 0.305398915248555);
  var b06 = normalize(sample.B06, 0.006637972542253, 0.608900395797889);
  var b07 = normalize(sample.B07, 0.013972727018939, 0.753827384322927);
  var b8a = normalize(sample.B8A, 0.026690138082061, 0.782011770669178);
  var b11 = normalize(sample.B11, 0.016388074192258, 0.493761397883092);
  var b12 = normalize(sample.B12, 0, 0.493025984460231);
  var vz  = normalize(Math.cos(sample.viewZenithMean * degToRad), 0.918595400582046, 1);
  var sz  = normalize(Math.cos(sample.sunZenithAngles * degToRad), 0.342022871159208, 0.936206429175402);
  var ra  = Math.cos((sample.sunAzimuthAngles - sample.viewAzimuthMean) * degToRad);

  var n1 = neuron1(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra);
  var n2 = neuron2(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra);
  var n3 = neuron3(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra);
  var n4 = neuron4(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra);
  var n5 = neuron5(b03,b04,b05,b06,b07,b8a,b11,b12,vz,sz,ra);
  var l2 = layer2(n1,n2,n3,n4,n5);
  var lai = denormalize(l2, 0.000319182538301, 14.4675094548151);

  return { lai: [lai] };
}
"""


def make_tiles(bbox, resolution, max_px):
    """Split a bbox into sub-tiles that each stay under max_px x max_px at given resolution."""
    minx, miny, maxx, maxy = bbox
    lat_mid = (miny + maxy) / 2
    m_per_deg_lon = 111320 * math.cos(math.radians(lat_mid))
    m_per_deg_lat = 111320

    max_deg_lon = (max_px * resolution) / m_per_deg_lon
    max_deg_lat = (max_px * resolution) / m_per_deg_lat

    n_x = math.ceil((maxx - minx) / max_deg_lon)
    n_y = math.ceil((maxy - miny) / max_deg_lat)

    dx = (maxx - minx) / n_x
    dy = (maxy - miny) / n_y

    tiles = []
    for i in range(n_x):
        for j in range(n_y):
            tminx = minx + i * dx
            tmaxx = minx + (i + 1) * dx
            tminy = miny + j * dy
            tmaxy = miny + (j + 1) * dy
            tiles.append((tminx, tminy, tmaxx, tmaxy))
    print(f"AOI split into {n_x} x {n_y} = {len(tiles)} tiles")
    return tiles


def download_tile(tile_bbox, idx, config):
    bbox = BBox(bbox=tile_bbox, crs=CRS.WGS84)
    size = bbox_to_dimensions(bbox, resolution=RESOLUTION)
    size = (min(size[0], 2500), min(size[1], 2500))  # hard safety clamp against API limit

    request = SentinelHubRequest(
        evalscript=EVALSCRIPT_LAI,
        input_data=[SentinelHubRequest.input_data(
            data_collection=CDSE_SENTINEL2_L2A,
            time_interval=TIME_INTERVAL,
            mosaicking_order="leastCC",  # least cloud cover pixel per position
        )],
        responses=[SentinelHubRequest.output_response("lai", MimeType.TIFF)],
        bbox=bbox,
        size=size,
        config=config,
        data_folder=OUTPUT_DIR,
    )

    print(f"  Tile {idx}: bbox={tile_bbox}, size={size} px — requesting...")
    data = request.get_data(save_data=True)
    return data


def find_tiff_files(folder):
    tiffs = []
    for root, _, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(".tif") or f.lower().endswith(".tiff"):
                tiffs.append(os.path.join(root, f))
    return tiffs


def mosaic_tiles(tiff_paths, out_path):
    srcs = [rasterio.open(p) for p in tiff_paths]
    mosaic, transform = merge(srcs, nodata=-9999)
    meta = srcs[0].meta.copy()
    meta.update({
        "driver": "GTiff",
        "height": mosaic.shape[1],
        "width": mosaic.shape[2],
        "transform": transform,
        "nodata": -9999,
        "compress": "lzw",
    })
    with rasterio.open(out_path, "w", **meta) as dst:
        dst.write(mosaic)
    for s in srcs:
        s.close()
    print(f"Mosaic written to {out_path}, shape={mosaic.shape}")


if __name__ == "__main__":
    tiles = make_tiles(AOI, RESOLUTION, MAX_PX)

    for i, t in enumerate(tiles):
        download_tile(t, i, config)
        if i < len(tiles) - 1:
            time.sleep(SLEEP_BETWEEN_TILES)

    tiff_paths = find_tiff_files(OUTPUT_DIR)
    print(f"Found {len(tiff_paths)} downloaded tile TIFFs")

    if tiff_paths:
        mosaic_tiles(tiff_paths, MOSAIC_OUT)

        # quick sanity check
        with rasterio.open(MOSAIC_OUT) as src:
            arr = src.read(1)
            valid = arr[arr != -9999]
            print(f"LAI stats — min: {valid.min():.2f}, max: {valid.max():.2f}, "
                  f"mean: {valid.mean():.2f}, valid px: {valid.size}/{arr.size}")
    else:
        print("No tiles downloaded — check auth/quota.")