"""Virtual sensors: the registry is complete and every entry names a registered source."""

import pytest
import yaml

from rainier3d.sensors import virtual as V


def test_registry_entries_are_complete():
    reg = V.load()
    assert {"CC.PR02", "CC.PR03", "CC.STYX"} <= set(reg)
    for uses in reg.values():
        for u in uses:
            assert all(u[f] for f in V.FIELDS)


def test_unregistered_codes_are_reported():
    assert V.unregistered(["CC.PR03", "UW.XXX"]) == ["UW.XXX"]


def test_bad_entries_are_refused(tmp_path):
    p = tmp_path / "v.yaml"
    p.write_text(yaml.safe_dump({"UW.X": [{"designed_for": "a", "estimates": "b"}]}))
    with pytest.raises(ValueError, match="missing"):
        V.load(p)
    good = dict.fromkeys(V.FIELDS, "x")
    p.write_text(yaml.safe_dump({"UW.X": [{**good, "source": "not_a_key"}]}))
    with pytest.raises(KeyError, match="not_a_key"):
        V.load(p)
