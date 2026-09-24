import json

import numpy as np

from rainier3d.config.domain import REPO, load_domain
from rainier3d.petro import relations as rel
from rainier3d.petro.table import petro_table, unit_names
from rainier3d.surface.geology import build_crosswalk


def test_levels_are_contiguous_and_whole_cells():
    for prof in ("m1", "full"):
        dom = load_domain(prof)
        levs = list(dom.levels.values())
        for a, b in zip(levs[:-1], levs[1:], strict=True):
            assert a.z_bot == b.z_top
        for lev in levs:
            assert lev.z.size * lev.dz == lev.z_top - lev.z_bot
            assert np.isclose(lev.x[0] - lev.dx / 2, dom.bounds[0])


def test_every_mapped_symbol_has_a_unit():
    cw = json.loads((REPO / "configs" / "crosswalk_geology.json").read_text())
    assert cw, "run pixi run s1 first"
    assert not [s for s, v in cw.items() if v["unit_id"] is None]


def test_crosswalk_rules_on_known_symbols():
    cw = build_crosswalk(
        [
            "Qva(mr)",
            "Qian(mr)",
            "Qvl(o)",
            "Migd(t)",
            "Miv(sx)",
            "Ovc(oh)",
            "Qt",
            "Qad(e)",
            "QPLva(g)",
            "PLOib",
            "Ec(2pg)",
        ]
    )
    got = {s: v["unit"] for s, v in cw.items()}
    assert got == {
        "Qva(mr)": "rainier_andesite",
        "Qian(mr)": "rainier_andesite",
        "Qvl(o)": "lahar_deposits",
        "Migd(t)": "miocene_intrusive",
        "Miv(sx)": "miocene_volcanics",
        "Ovc(oh)": "ohanapecosh",
        "Qt": "alluvium_colluvium",
        "Qad(e)": "glacial_drift",
        "QPLva(g)": "young_volcanics",
        "PLOib": "miocene_intrusive",
        "Ec(2pg)": "eocene_sedimentary",
    }


def test_every_unit_has_petrophysics():
    t = petro_table()
    assert set(unit_names()) - {0} <= set(t.index)


def test_brocher_relations():
    # regression values of Brocher (2005) Eqs. at Vp = 6 km/s
    assert np.isclose(rel.brocher_vs_from_vp(6.0), 3.549, atol=2e-3)
    assert np.isclose(rel.nafe_drake_rho_from_vp(6.0), 2.717, atol=2e-3)
    # the forward and inverse fits are separate regressions: they disagree by up to 2.7 % at Vp = 3 km/s
    vp = np.linspace(3, 7.5, 10)
    assert np.allclose(rel.brocher_vp_from_vs(rel.brocher_vs_from_vp(vp)), vp, rtol=0.03)


def test_crack_closure_limits():
    assert np.isclose(rel.crack_closure(3.0, 6.0, 0.0, 30.0), 3.0)
    assert np.isclose(rel.crack_closure(3.0, 6.0, 1e4, 30.0), 6.0)
    assert np.all(np.diff(rel.crack_closure(3.0, 6.0, np.linspace(0, 200, 20), 30.0)) > 0)
