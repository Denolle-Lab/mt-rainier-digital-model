import csv
import importlib.util
import re

import pytest
import xarray as xr

from rainier3d.config.domain import REPO, load_domain

spec = importlib.util.spec_from_file_location("s20", REPO / "scripts" / "20_publish_products.py")
S20 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S20)


def test_every_product_has_a_recipe_with_known_stages_and_cached_inputs():
    sp = S20.spec()
    tasks = set(re.findall(r"^(s\d+)\s*=", (REPO / "pixi.toml").read_text(), re.M))
    reg = __import__("yaml").safe_load((REPO / "configs" / "sources.yaml").read_text())
    folders = {r["path"].split("/")[0] for r in csv.DictReader((REPO / "docs" / "data_manifest.csv").open())}
    for key in S20.PRODUCTS:
        r = sp["rebuild"][key]
        assert set(r["stages"]) <= tasks, key
        assert set(r.get("raw", [])) <= folders, key
        assert set(r.get("needs", [])) <= set(S20.PRODUCTS), key
        assert set(r.get("manual", [])) <= set(reg), key  # registry keys, not citation keys


def test_every_surface_variable_of_the_model_is_classified_once():
    model = load_domain().path("processed") / "model.zarr"
    if not model.exists():
        pytest.skip("needs the built model")
    s = S20.spec()["model"]["surface"]
    classes = [set(s[k]) for k in ("geometry", "computed", "resampled")]
    assert not any(a & b for i, a in enumerate(classes) for b in classes[i + 1 :])  # one class each
    have = set(xr.open_datatree(model, engine="zarr", consolidated=False)["surface"].to_dataset().data_vars)
    assert have <= set().union(*classes), sorted(have - set().union(*classes))
