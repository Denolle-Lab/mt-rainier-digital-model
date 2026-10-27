"""Uniform grids (rainier3d.export.grids.uniform): resampling the levels and the air mask."""

import numpy as np
import pytest
import xarray as xr

from rainier3d.export import grids


def _level(z, dz, v, xy, elev):
    vs = np.where(z[:, None, None] < elev, v, np.nan) * np.ones((1, xy.size, xy.size))
    ds = xr.Dataset({"vs": (("z", "y", "x"), vs.astype(np.float32))}, coords={"z": z, "y": xy, "x": xy})
    ds.attrs["dz"] = dz
    return ds


@pytest.mark.parametrize("elev", [-50.0, 300.0])
def test_gap_between_levels_keeps_air_above_the_ground(elev):
    # L1 (50 m cells, bottom centre 25 m) over L2 (250 m cells, top centre -125 m); the ground at -50 m lies
    # inside the gap between the two centres, at 300 m in L1
    xy = np.array([0.0, 1000.0])
    tree = xr.DataTree.from_dict(
        {
            "surface": xr.Dataset(
                {"elevation": (("y", "x"), np.full((2, 2), elev))}, coords={"y": xy, "x": xy}
            ),
            "L1": _level(np.arange(475.0, 0, -50), 50.0, 1000.0, xy, elev),
            "L2": _level(np.arange(-125.0, -1000, -250), 250.0, 2000.0, xy, elev),
            "L3": _level(np.array([-1500.0]), 1000.0, 3000.0, xy, elev),
        }
    )
    g = grids.uniform(tree, dx=1000.0, dz=25.0, z_top=500.0, z_bot=-1000.0, variables=("vs",))
    air = g.air.values[:, 0, 0].astype(bool)
    assert (air == (g.z.values > elev)).all()  # every cell above the ground is air, and only those
    assert np.isfinite(g.vs.values).all()  # air filled from the first rock cell
