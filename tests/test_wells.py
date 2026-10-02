import numpy as np
import pandas as pd

from rainier3d.config.domain import load_domain
from rainier3d.hydromet import wells as W


def test_well_table_units_qc_and_duplicates(tmp_path):
    dom = load_domain()
    cfg = W.config()
    lon, lat = -121.9, 46.8
    eco = tmp_path / "eco.csv"
    pd.DataFrame(
        {
            "ID": [1, 2, 35552],
            "StaticWaterLvl": ["10", "500", "20"],  # ft; 500 ft is deeper than the well
            "CompletedDepth": ["100", "100", "100"],
            "WorkCompletionDate": ["2001-01-01"] * 3,
            "lon": [lon] * 3,
            "lat": [lat] * 3,
        }
    ).to_csv(eco, index=False)
    sites, levels = tmp_path / "s.csv", tmp_path / "l.csv"
    pd.DataFrame(
        {"monitoring_location_id": ["USGS-1"], "lon": [lon], "lat": [lat], "well_depth_ft": [50.0]}
    ).to_csv(sites, index=False)
    pd.DataFrame(
        {
            "monitoring_location_id": ["USGS-1"] * 3,
            "time": ["2001-01-01", "2002-01-01", "2003-01-01"],
            "value": [10.0, 20.0, 30.0],
            "unit_of_measure": ["ft"] * 3,
        }
    ).to_csv(levels, index=False)
    bh = pd.DataFrame(
        {
            "BOREHOLE_ID": ["a", "b"],
            "LONGITUDE": [lon, lon],
            "LATITUDE": [lat, lat],
            "BOREHOLE_DEPTH_FT": ["100", "100"],
            "BOREHOLE_DATE": ["2001-01-01"] * 2,
            "ECYID": [np.nan, "35552.0"],  # b is Ecology report 35552
        }
    )
    wgs = {
        "borehole_information": bh,
        "hydrologic": pd.DataFrame({"BOREHOLE_ID": ["a", "b"], "DEPTH_TO_WATER_FT": ["5", "20"]}),
        "bedrock": pd.DataFrame({"BOREHOLE_ID": ["a"], "DEPTH_TO_BEDROCK_FT": ["131.234"]}),
    }
    t = W.well_table(dom, cfg, eco, (sites, levels), wgs).set_index(["source", "site_id"])
    assert t.loc[("ecology", "1"), "depth_to_water_m"] == np.float64(10 * W.FT)
    assert t.loc[("ecology", "2"), "qc_water"] == "rejected"  # deeper than the completed depth
    assert t.loc[("nwis", "USGS-1"), "depth_to_water_m"] == np.float64(20 * W.FT)  # median of the levels
    assert t.loc[("nwis", "USGS-1"), "n_levels"] == 3
    assert t.loc[("wgs", "b"), "qc_water"] == "duplicate"  # counted once, under Ecology
    assert abs(t.loc[("wgs", "a"), "depth_to_bedrock_m"] - 40.0) < 0.01
