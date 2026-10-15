"""Every variable of the built model is self-describing: units and long_name (rainier3d.io.attrs, S5)."""

import os

import pytest
import xarray as xr

from rainier3d.config.domain import load_domain

STORE = os.environ.get("RAINIER3D_MODEL") or str(load_domain().path("processed") / "model.zarr")


@pytest.mark.skipif(not os.path.exists(STORE), reason="needs the built model (S5)")
@pytest.mark.parametrize("node", ["L1", "L2", "L3", "cz"])
def test_every_variable_has_units_and_long_name(node):
    ds = xr.open_datatree(STORE, engine="zarr", consolidated=False)[node].to_dataset()
    missing = [v for v in ds.variables if not {"units", "long_name"} <= set(ds[v].attrs)]
    assert not missing, f"{node}: {missing}"
    if node != "cz":
        names = ds.unit.attrs["flag_meanings"].split()
        assert len(names) == len(ds.unit.attrs["flag_values"]) and names[0] == "air"
