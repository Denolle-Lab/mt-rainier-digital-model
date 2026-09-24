"""Invariants of the built model (skipped until pixi run s5 has produced data/processed/model.zarr)."""

import numpy as np
import pandas as pd
import pytest

from rainier3d.config.domain import load_domain
from rainier3d.geomodel.rules import AIR, ICE, MAGMA, kinds
from rainier3d.petro.table import units_config

DOM = load_domain()
MODEL = DOM.path("processed") / "model.zarr"
pytestmark = pytest.mark.skipif(not MODEL.exists(), reason="model.zarr not built")


@pytest.fixture(scope="module")
def tree():
    from rainier3d.io.store import read_tree

    return read_tree(MODEL)


@pytest.mark.parametrize("lev", ["L1", "L2", "L3"])
def test_no_properties_in_air_and_all_in_rock(tree, lev):
    ds = tree[lev].to_dataset()
    air = ds["unit"].values == AIR
    for v in ("vp", "vs", "rho"):
        a = ds[v].values
        assert np.isnan(a[air]).all()
        assert np.isfinite(a[~air]).all()


@pytest.mark.parametrize("lev", ["L1", "L2", "L3"])
def test_physical_ranges(tree, lev):
    ds = tree[lev].to_dataset()
    u = ds["unit"].values
    rock = (u != AIR) & (u != ICE) & (u != MAGMA)
    r = (ds["vp"] / ds["vs"]).values
    assert np.nanmin(r[rock]) >= 1.5 and np.nanmax(r[rock]) <= 3.0
    # fused Vp/Vs lies between the geology and regional ratios (CVM v1.7 itself reaches 2.22 at >1 km)
    rg = (ds["vp_geology"] / ds["vs_geology"]).values
    rr = (ds["vp_regional"] / ds["vs_regional"]).values
    lo, hi = np.fmin(rg, rr), np.fmax(rg, rr)
    assert np.all((r[rock] >= lo[rock] * (1 - 1e-4)) & (r[rock] <= hi[rock] * (1 + 1e-4)))
    rho = ds["rho"].values[u != AIR]
    assert rho.min() >= 900 and rho.max() <= 3100


def test_lowpass_matches_regional():
    rep = DOM.path("outputs") / "fusion_report.csv"
    if not rep.exists():
        pytest.skip("fusion_report.csv missing")
    df = pd.read_csv(rep)
    tol = DOM.cfg["fusion"]["lowpass_rms_tol"]
    bad = df[df["lowpass_rms_lnV"] > tol]
    assert bad.empty, f"low-pass misfit above {tol}:\n{bad}"


def test_top_rock_cell_matches_mapped_bedrock(tree):
    """Where bedrock crops out, the top L1 cell carries the mapped unit (>= 95 % of columns)."""
    kind = kinds(units_config())
    ds = tree["L1"].to_dataset()
    u = ds["unit"].values
    top = np.argmax(u != AIR, axis=0)
    top_unit = np.take_along_axis(u, top[None], 0)[0]
    su = tree["surface"].to_dataset()["surface_unit"].sel(x=ds.x, y=ds.y, method="nearest").values
    rock = np.isin(su, [k for k, v in kind.items() if v in ("pluton", "supracrustal", "cap")])
    frac = float((top_unit[rock] == su[rock]).mean())
    assert frac >= 0.95, f"only {frac:.1%} of bedrock columns match"


def test_nll_air_skin():
    """NonLinLoc grids: air above a one-cell skin is slow; the skin and rock keep their velocity."""
    import numpy as np

    from rainier3d.export.grids import slow_air

    air = np.zeros((6, 1, 2), bool)
    air[:3, 0, 0] = True  # column 0: 3 air cells above the ground
    air[:1, 0, 1] = True  # column 1: 1 air cell (all skin)
    s = slow_air(air, skin_cells=1)
    assert s[:, 0, 0].tolist() == [True, True, False, False, False, False]
    assert not s[:, 0, 1].any()
