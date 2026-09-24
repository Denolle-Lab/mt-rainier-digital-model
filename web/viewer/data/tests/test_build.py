import numpy as np

from rainier import build


def test_count_mismatch_is_an_error():
    st = {"counts": {"stations": 5, "sites": 1}, "sites": [{"stations": [{}, {}, {}, {}], "kinds": ["seismometer"]}], "kinds": ["seismometer"]}
    errs = build.check_counts(st)
    assert any("station count" in e for e in errs)


def test_counts_that_reconcile_pass():
    st = {"counts": {"stations": 2, "sites": 1}, "sites": [{"stations": [{}, {}], "kinds": ["seismometer"]}], "kinds": ["seismometer"]}
    assert build.check_counts(st) == []


def test_bundle_over_the_limit_is_an_error(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"x" * 200)
    assert any("bundle too large" in e for e in build.check_size(tmp_path, limit=100))
    assert build.check_size(tmp_path, limit=1000) == []


def test_summit_that_disagrees_with_the_overview_is_an_error():
    ov = np.full((10, 10), 2000.0)
    meta = {"cols": 10, "rows": 10, "x0": 0.0, "z0": 0.0, "dx": 1.0, "dz": 1.0}
    xs, zs = np.meshgrid(np.arange(2, 8) + 0.5, np.arange(2, 8) + 0.5)
    assert build.check_summit_rms(np.full(xs.shape, 2010.0), xs, zs, ov, meta) == []
    assert any("summit" in e for e in build.check_summit_rms(np.full(xs.shape, 2100.0), xs, zs, ov, meta))


def test_counts_reconcile_against_what_the_service_returned():
    st = {"counts": {"stations": 2, "sites": 1, "returned": 5, "excluded": 2}, "sites": [{"stations": [{}, {}], "kinds": ["seismometer"]}], "kinds": ["seismometer"]}
    assert any("reconcile" in e for e in build.check_counts(st))   # 5 returned − 2 excluded ≠ 2 kept
    st["counts"]["excluded"] = 3
    assert build.check_counts(st) == []


def test_partial_build_without_quakes_does_not_need_quakes_json(tmp_path, monkeypatch):
    # --only with no quakes step on an output that has no quakes.json yet: quakes are optional in the bundle
    (tmp_path / "terrain").mkdir()
    (tmp_path / "summit").mkdir()
    (tmp_path / "terrain" / "terrain.json").write_text("{}")
    (tmp_path / "summit" / "index.json").write_text("{}")
    (tmp_path / "stations.json").write_text('{"asOf": "2026-09-24", "counts": {"stations": 0, "sites": 0, "sitesOnMap": 0}}')
    monkeypatch.setattr(build, "validate", lambda *a: [])
    assert build.main(["--out", str(tmp_path), "--cache", str(tmp_path / "cache"), "--only", "none"]) == 0
    assert (tmp_path / "manifest.json").exists()
