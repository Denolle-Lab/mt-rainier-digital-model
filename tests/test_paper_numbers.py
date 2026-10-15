"""rainier3d.report.paper_numbers: groups with missing inputs are skipped and listed, not fatal."""

import json

import pytest

from rainier3d.config.domain import REPO
from rainier3d.report import paper_numbers as P


def test_missing_inputs_are_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(P, "OUT", tmp_path / "numbers.json")

    def missing():
        raise FileNotFoundError(2, "No such file", "outputs/none.json")

    monkeypatch.setitem(P.GROUPS, "missing", missing)
    P.make_all(only=["missing"])
    rec = json.loads((tmp_path / "numbers.json").read_text())
    assert rec["numbers"] == {}
    assert rec["skipped"] == {"missing": "missing input: outputs/none.json"}


def test_clean_rounds_and_drops_non_finite():
    assert P._clean({"a": [0.123456789, float("nan")]}) == {"a": [0.123457, None]}


@pytest.mark.skipif(
    not (REPO / "outputs/joint_calibration/history.json").exists(), reason="needs the S13 outputs"
)
def test_calibration_matches_config(tmp_path, monkeypatch):
    import yaml

    monkeypatch.setattr(P, "OUT", tmp_path / "numbers.json")
    num = P.make_all(only=["calibration"])
    cal = yaml.safe_load((REPO / "configs/velocity_calibration.yaml").read_text())
    assert num["cal.factor_v0"]["value"] == pytest.approx(cal["geology"]["factor_v0"])
    assert num["cal.data"]["value"]["n_events"] == cal["data"]["n_events"]
