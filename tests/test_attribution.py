"""Viewer attribution: every layer source carries its licence from configs/sources.yaml."""

import json

import pytest

from rainier3d.export.atlas import short_license, tag_licences


def test_short_license_labels():
    assert short_license("CC-BY-NC-ND-4.0; used for non-commercial research") == "CC-BY-NC-ND-4.0"
    assert short_license("public domain: USGS-authored data") == "public domain"
    assert (
        short_license("Washington Geological Survey content: free to use")
        == "Washington Geological Survey content"
    )
    assert short_license(None) == ""


def test_tag_licences_adds_licence_and_attribution(tmp_path):
    (tmp_path / "model").mkdir()
    layers = {
        "layers": [
            {"key": "water_table_depth", "sources": [{"key": "ma2026_wtd", "title": "t", "link": "l"}]},
            {"key": "x", "sources": [{"key": "vallance_scott_1997", "title": "t2", "link": ""}]},
        ]
    }
    (tmp_path / "model" / "layers.json").write_text(json.dumps(layers))
    assert tag_licences(tmp_path) == 2
    out = json.loads((tmp_path / "model" / "layers.json").read_text())["layers"]
    wt = out[0]["sources"][0]
    assert wt["license"] == "CC-BY-NC-ND-4.0" and "Ma et al. (2026)" in wt["attribution"]
    assert wt["title"] == "t" and wt["link"] == "l"  # title and link are kept
    assert "license" not in out[1]["sources"][0]  # an article without a licence gets no label


def test_unknown_source_key_fails(tmp_path):
    (tmp_path / "model").mkdir()
    bad = {"layers": [{"key": "x", "sources": [{"key": "not_in_registry", "title": "t", "link": ""}]}]}
    (tmp_path / "model" / "layers.json").write_text(json.dumps(bad))
    with pytest.raises(KeyError, match="not_in_registry"):
        tag_licences(tmp_path)
