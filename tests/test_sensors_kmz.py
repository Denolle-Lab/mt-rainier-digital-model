import io
import zipfile

import numpy as np
import pandas as pd
from PIL import Image

from rainier3d.io import kmz
from rainier3d.sensors.inventory import classify, families


def _tile(color):
    buf = io.BytesIO()
    Image.new("RGBA", (4, 4), color).save(buf, format="PNG")
    return buf.getvalue()


def _overlay(name, href, n, s, e, w):
    return (
        f"<kml><GroundOverlay><name>{name}</name><Icon><href>{href}</href></Icon><LatLonBox>"
        f"<north>{n}</north><south>{s}</south><east>{e}</east><west>{w}</west></LatLonBox></GroundOverlay></kml>"
    )


def test_superoverlay_keeps_leaf_tiles_in_place(tmp_path):
    p = tmp_path / "t.kmz"
    with zipfile.ZipFile(p, "w") as z:
        z.writestr("root.kml", _overlay("root", "r.png", 2, 0, 2, 0))  # coarse level, must be ignored
        z.writestr("r.png", _tile((9, 9, 9, 255)))
        colors = {
            (0, 0): (255, 0, 0, 255),
            (0, 1): (0, 255, 0, 255),
            (1, 0): (0, 0, 255, 255),
            (1, 1): (255, 255, 0, 255),
        }
        for (i, j), c in colors.items():  # i: row from north, j: column from west
            z.writestr(f"t{i}{j}.kml", _overlay(f"t{i}{j}", f"t{i}{j}.png", 2 - i, 1 - i, j + 1, j))
            z.writestr(f"t{i}{j}.png", _tile(c))
    img, b = kmz.mosaic(p)
    assert b == (0, 0, 2, 2)
    assert img.shape == (8, 8, 4)
    assert tuple(img[0, 0]) == colors[(0, 0)] and tuple(img[0, 7]) == colors[(0, 1)]
    assert tuple(img[7, 0]) == colors[(1, 0)] and tuple(img[7, 7]) == colors[(1, 1)]


def test_fdsn_channel_classification():
    cfg = families()
    df = pd.DataFrame(
        {
            "Channel": ["HHZ", "EHZ", "ENE", "BDF", "DPZ", "BS1", "LFE", "LQN", "VM1", "LOG"],
            "Network": ["UW"] * 9 + ["SY"],
        }
    )
    out = classify(df, cfg)
    got = dict(zip(out.Channel, out.family, strict=True))
    assert got == {
        "HHZ": "seismic",
        "EHZ": "seismic",
        "ENE": "strong",
        "BDF": "infrasound",
        "DPZ": "nodes",
        "BS1": "strain",
        "LFE": "mt",
        "LQN": "mt",
    }
    assert not np.isin(["VM1", "LOG"], out.Channel).any()  # state of health, synthetic network
