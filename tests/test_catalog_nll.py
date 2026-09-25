"""NonLinLoc helpers of the catalogue relocation (S26): topography grid, observation file, summary parser."""

import numpy as np
import pandas as pd

from rainier3d.catalog import nll as N


def test_topo_grd_header_units_and_row_order(tmp_path):
    x = np.array([553000.0, 553100.0, 553200.0])
    y = np.array([5149000.0, 5149100.0])
    elev = np.array([[100.0, 200.0, 300.0], [400.0, 500.0, 600.0]])  # rows south -> north
    p = N.write_topo_grd(elev, x, y, tmp_path / "t.grd")
    lines = p.read_text().splitlines()
    assert "x_min: 553.0000 x_max: 553.2000 x_inc: 0.1000 name: km nx: 3" in lines[5]
    assert "name: km ny: 2" in lines[6]  # NLLoc treats the grid as km (not lat/lon) only if both units are km
    data = np.loadtxt(lines[9:])
    assert np.allclose(
        data, [[0.4, 0.5, 0.6], [0.1, 0.2, 0.3]]
    )  # km, northern row first (GMT scanline order)


def test_obs_file_has_one_block_per_event(tmp_path):
    picks = pd.DataFrame(
        {"event": ["e1", "e1", "e2"], "sta": ["RCM", "STAR", "RCM"], "phase": ["P", "S", "P"],
         "pick_time": ["2024-05-01T12:00:01.250000", "2024-05-01T12:00:03.5", "2024-05-02T00:00:00"]}
    )  # fmt: skip
    text = N.write_obs(picks, tmp_path / "o.obs").read_text()
    assert text.count("PUBLIC_ID") == 2
    line = [ln for ln in text.splitlines() if ln.startswith("STAR")][0].split()
    assert line[4] == "S" and line[6:9] == ["20240501", "1200", "3.5000"] and line[9] == "GAU"
    assert float(line[10]) == N.SIGMA["S"]


def test_read_hyp_parses_location_quality_and_uncertainty(tmp_path):
    hyp = """NLLOC "loc" "LOCATED" "Location completed."
PUBLIC_ID uw123
HYPOCENTER  x 594.5 y 5189.4 z 3.25  OT 12.5  ix -1 iy -1 iz -1
GEOGRAPHIC  OT 2024 05 01  12 00  12.5  Lat 46.85 Long -121.76 Depth 3.25
QUALITY  Pmax 1 MFmin 1 MFmax 1 RMS 0.08 Nphs 14 Gap 95 Dist 3.1 Mamp -9.9 0 Mdur -9.9 0
STATISTICS  ExpectX 594.5 Y 5189.4 Z 3.3  CovXX 0.04 XY -0.02 XZ 0.1 YY 0.05 YZ -0.08 ZZ 0.25 EllAz1  115.9
QML_OriginUncertainty  horUnc -1  minHorUnc 0.18  maxHorUnc 0.26  azMaxHorUnc 112.5
END_PHASE
END_NLLOC
"""
    (tmp_path / "s.hyp").write_text(hyp)
    r = N.read_hyp(tmp_path / "s.hyp").iloc[0]
    assert r.event == "uw123" and r.status == "LOCATED" and r.message == "Location completed."
    assert (r.x_km, r.y_km, r.z_km, r.nphs, r.gap) == (594.5, 5189.4, 3.25, 14, 95.0)
    assert np.isclose(r.z_sd_km, 0.5) and r.h_unc_max_km == 0.26
