"""The S13 calibration hooks in S4 (geology multipliers) and S5 (static bias of the regional model)."""

import numpy as np
import xarray as xr

from rainier3d.fusion.build import apply_bias, regional_bias
from rainier3d.petro.table import perturbations, petro_table, rock_unit_ids, unit_names
from rainier3d.properties.assign import assign


def _level():
    names = {v: k for k, v in unit_names().items()}
    units = np.array(
        [names["rainier_andesite"], names["miocene_intrusive"], names["glacial_drift"], names["ice"]]
    )
    u = np.broadcast_to(units[None, None, :], (3, 1, 4)).astype(np.uint8)
    depth = np.broadcast_to(np.array([100.0, 1000.0, 3000.0])[:, None, None], u.shape)
    return xr.Dataset(
        {
            "unit": (("z", "y", "x"), u),
            "depth": (("z", "y", "x"), depth),
            "alteration": (("z", "y", "x"), np.zeros(u.shape)),
        },
        coords={"z": [0.0, -1.0, -2.0], "y": [0.0], "x": np.arange(4.0)},
    )


def test_geology_multipliers_act_on_rock_only():
    lev, t, p = _level(), petro_table(), perturbations()
    a = assign(lev, t, p)
    assert all(np.allclose(a[v], assign(lev, t, p, {})[v], equal_nan=True) for v in ("vp", "vs"))
    b = assign(lev, t, p, {"ln_v0": 0.1, "ln_pstar": -0.3, "ln_vs": 0.05})
    rock = np.isin(lev.unit.values, rock_unit_ids())
    assert np.all(b.vp.values[rock] > a.vp.values[rock])  # faster V0 and faster closure
    assert np.allclose(b.vp.values[~rock], a.vp.values[~rock])
    assert np.allclose(b.vs.values[~rock], a.vs.values[~rock])


def test_v0_multiplier_is_capped_below_vinf():
    lev, t, p = _level(), petro_table(), perturbations()
    b = assign(lev, t, p, {"ln_v0": 5.0})
    vinf = t.loc[lev.unit.values[0, 0, 1], "vpinf_kms"] * 1e3
    assert 0.98 * vinf - 1e-3 <= b.vp.values[0, 0, 1] <= vinf + 1e-3  # V0 capped at 0.98 Vinf, V(P) <= Vinf


def test_regional_bias_reads_all_calibration_versions():
    k = [0.0, 1000.0, 2000.0]
    v2 = {
        "regional_bias": {"knots_m": k, "vp": {"log_factor": [0, 0, 0.1]}, "vs": {"log_factor": [0, 0, 0.2]}}
    }
    v1 = {"knots_m": k, "vp": {"log_factor": [0.1, 0, 0]}, "vs": {"log_factor": [0.2, 0, 0]}}
    s12 = {"knots_m": k, "log_factor": [0.3, 0, 0]}
    assert regional_bias(v2)[1]["vp"][2] == 0.1
    assert regional_bias(v1)[1]["vs"][0] == 0.2
    kn, lf = regional_bias(s12)
    assert lf["vp"] is None and lf["vs"][0] == 0.3
    assert regional_bias(None) is None
    reg = {"vp": np.array([6000.0]), "vs": np.array([3000.0]), "vs_unc": np.array([1.0])}
    out = apply_bias(reg, np.array([2000.0]), v2)
    assert np.isclose(out["vp"][0], 6000 * np.exp(0.1))
    assert np.isclose(out["vs"][0], min(3000 * np.exp(0.2), out["vp"][0] / 1.6))
    assert reg["vp"][0] == 6000.0  # input untouched
