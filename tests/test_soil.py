import numpy as np
import pytest
import xarray as xr
import yaml

from rainier3d.config.domain import REPO
from rainier3d.surface import soil as S


def test_usda_texture_class_at_points_of_the_triangle():
    # (clay, sand, silt) -> class, one point inside each USDA class
    cases = {
        (3, 92, 5): "Sand",
        (6, 80, 14): "Loamy sand",
        (10, 65, 25): "Sandy loam",
        (20, 40, 40): "Loam",
        (15, 20, 65): "Silt loam",
        (5, 5, 90): "Silt",
        (27, 60, 13): "Sandy clay loam",
        (33, 32, 35): "Clay loam",
        (33, 10, 57): "Silty clay loam",
        (40, 50, 10): "Sandy clay",
        (45, 5, 50): "Silty clay",
        (60, 20, 20): "Clay",
    }
    label = {v: lab for v, lab, _ in S.TEXTURE}
    clay, sand, silt = (np.array([k[i] for k in cases]) for i in range(3))
    got = [label[int(v)] for v in S.usda_texture(clay, sand, silt)]
    assert got == list(cases.values())


def test_usda_texture_rescales_and_flags_missing():
    # fractions that sum to 50 are rescaled (loam); a missing fraction gives 0
    assert S.usda_texture([10], [20], [20]).tolist() == [4]
    assert S.usda_texture([np.nan], [40], [40]).tolist() == [0]


def test_depth_weighted_mean_of_point_predictions():
    z = np.array([0, 0.05, 0.15, 0.3, 0.6, 1.0, 1.5])
    da = xr.DataArray(np.broadcast_to(z[:, None, None], (7, 1, 1)).copy(), dims=("soil_depth", "y", "x"))
    da = da.assign_coords(soil_depth=z)
    # a linear profile v = z averages to the mid depth, 0.5 m, over 0-1 m
    assert S.mean_over_points(da, 0.0, 1.0)[0, 0] == pytest.approx(0.5)
    # below a lithic contact at 0.3 m SOLUS is empty: the mean is over the 0-0.3 m soil column
    da[4:] = np.nan
    assert S.mean_over_points(da, 0.0, 1.0)[0, 0] == pytest.approx(0.15)
    with pytest.raises(ValueError):
        S.mean_over_points(da, 0.0, 0.8)


def test_unit_conversions():
    # 1 cm/hr = 2.78e-6 m/s; 1 kPa-1 = 9.81 m-1 of water head
    assert 10 ** (0 + S.LOG10_CMHR_TO_MS) == pytest.approx(0.01 / 3600)
    assert 10 ** (0 + S.LOG10_KPA_TO_M) == pytest.approx(9.80665)


def test_soil_config_names_registry_keys():
    cfg = S.config()
    reg = yaml.safe_load((REPO / "configs" / "sources.yaml").read_text())
    keys = {k for ks in cfg["source_keys"].values() for k in ks}
    assert keys <= set(reg)
    assert cfg["summary_cm"][1] in cfg["solus"]["depths_cm"]  # summaries end on a prediction depth
