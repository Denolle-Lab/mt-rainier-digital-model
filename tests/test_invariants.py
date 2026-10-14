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
    # The rock law keeps Vp/Vs below 3. Cells that contain critical zone (weathering index W > 0, or an
    # unconsolidated unit) average a saturated granular layer, whose Vp/Vs reaches 4 to 4.5 (Pasquet et al.
    # 2015, saturated loess): bounded at 5. The bound tests each law, not the thickness of a placeholder layer
    # (decision of 2026-10-05, paper Sect. "One effective stress for the whole model").
    w = np.nan_to_num(ds["weathering_index"].values) if "weathering_index" in ds else np.zeros_like(r)
    loose = np.isin(u, [k for k, v in kinds(units_config()).items() if v == "unconsolidated"])
    cz = rock & (loose | (w > 0))
    assert np.nanmin(r[rock]) >= 1.5 and np.nanmax(r[rock & ~cz], initial=0) <= 3.0
    assert np.nanmax(r[cz], initial=0) <= 5.0
    # fused Vp/Vs lies between the geology and regional ratios (CVM v1.7 itself reaches 2.22 at >1 km); below
    # lambda_z_from_depth_m the geology enters the fusion low-passed in the vertical (lambda_z_m), so its
    # low-passed ratio is a bound too
    rg = (ds["vp_geology"] / ds["vs_geology"]).values
    rr = (ds["vp_regional"] / ds["vs_regional"]).values
    lo, hi = np.fmin(rg, rr), np.fmax(rg, rr)
    fc = DOM.cfg["fusion"]
    if fc.get("lambda_z_m", 0) > 0:
        from rainier3d.fusion.blend import lowpass_v_growing

        d, dz, z0 = ds["depth"].values, float(ds.attrs["dz"]), fc["lambda_z_from_depth_m"]
        vm = (u != AIR) & (d - dz / 2 >= z0)
        rgf = np.exp(lowpass_v_growing(np.log(rg), vm, d, z0, fc["lambda_z_m"], dz))
        lo, hi = np.fmin(lo, rgf), np.fmax(hi, rgf)
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
    assert slow_air(air, skin_cells=2)[:, 0, 0].tolist() == [True, False, False, False, False, False]


def test_l1_keeps_the_travel_time_of_the_critical_zone(tree):
    # vertical S time through the top two rock cells of L1, the first from the ground down, equals that of the
    # fine columns they average (to their base, at most 125 m: inside the 150 m columns); columns without ice
    if "cz" not in tree.children:
        pytest.skip("model without the critical zone")
    l1, cz = tree["L1"].to_dataset(), tree["cz"].to_dataset()
    d, u, vs = l1["depth"].values, l1["unit"].values, l1["vs"].values
    rock = (u != AIR) & (u != ICE)
    k0 = np.argmax(rock, axis=0)
    k = np.minimum(k0, rock.shape[0] - 2)[None]  # columns without two rock cells in L1: masked below
    dz = float(l1.attrs["dz"])
    base = np.take_along_axis(d, k + 1, 0)[0] + dz / 2
    t_l1 = (base - dz) / np.take_along_axis(vs, k, 0)[0] + dz / np.take_along_axis(vs, k + 1, 0)[0]
    top = cz["cz_depth"].values - cz["cz_thickness"].values / 2
    w = np.clip(
        np.minimum(top[:, None, None] + cz["cz_thickness"].values[:, None, None], base) - top[:, None, None],
        0,
        None,
    )
    t_cz = (w / cz["vs"].values).sum(0)
    ok = (cz["ice_thickness"].values == 0) & ~(u == ICE).any(0) & rock.any(0) & (k0 < rock.shape[0] - 1)
    ok &= np.isfinite(t_cz)
    r = t_l1[ok] / t_cz[ok]
    assert np.abs(r - 1).max() < 1e-3, (
        f"L1/cz S time over the top two rock cells: {r.min():.4f}-{r.max():.4f}"
    )
