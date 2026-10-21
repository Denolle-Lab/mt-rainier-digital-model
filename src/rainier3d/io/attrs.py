"""Units and descriptions of every variable of model.zarr (S5 sets them; docs/velocity_model.md lists them).

One table for the levels L1-L3 and one for the critical-zone node /cz, so that `print(ds)` describes the model
without the paper. The unit codes of `unit` come from configs/units.yaml as CF flag values and meanings.
"""

from __future__ import annotations

import xarray as xr

COORDS = {
    "x": {"units": "m", "long_name": "easting, UTM zone 10N (EPSG:32610), cell centre"},
    "y": {"units": "m", "long_name": "northing, UTM zone 10N (EPSG:32610), cell centre"},
    "z": {"units": "m", "long_name": "elevation, NAVD88 (EPSG:5703), positive up, cell centre"},
}

LEVEL = {
    "vp": (
        "m/s",
        "P-wave speed of the fused model (geology below the critical zone, regional at long wavelengths)",
    ),
    "vs": ("m/s", "S-wave speed of the fused model"),
    "rho": ("kg/m3", "density of the fused model"),
    "qp": ("1", "P-wave quality factor (rule in the q block of configs/perturbations.yaml)"),
    "qs": ("1", "S-wave quality factor (rule in the q block of configs/perturbations.yaml)"),
    "vp_geology": ("m/s", "P-wave speed of the geology model (S4), before the fusion"),
    "vs_geology": ("m/s", "S-wave speed of the geology model (S4), before the fusion"),
    "vp_regional": (
        "m/s",
        "P-wave speed of the corrected regional model (CVM v1.7, CRESCENT below, blended 8-16 km deep)",
    ),
    "vs_regional": ("m/s", "S-wave speed of the corrected regional model"),
    "vs_unc_regional": ("m/s", "Vs uncertainty of CRESCENT Gen0, interpolated (not in the released product)"),
    "unit": ("1", "model unit (flag_values and flag_meanings; configs/units.yaml)"),
    "depth": ("m", "depth of the cell centre below the ground surface (top of glacier ice); negative in air"),
    "elevation": ("m", "ground surface elevation (top of glacier ice), NAVD88"),
    "alteration": ("1", "hydrothermal alteration intensity, 0 fresh to 1 fully altered (S22, EM survey)"),
    "magma_weight": (
        "1",
        "weight of the magma-body anomaly, 1 in the core to 0 outside (applied after the fusion)",
    ),
    "porosity": ("1", "porosity (1 in air)"),
    "log10_permeability": ("log10(m2)", "permeability"),
    "weathering_index": ("1", "weathering index, 1 regolith to 0 fresh rock"),
}

CZ = {
    "vp": ("m/s", "P-wave speed of the critical-zone column"),
    "vs": ("m/s", "S-wave speed of the critical-zone column"),
    "rho": ("kg/m3", "density"),
    "weathering_index": ("1", "weathering index, 1 regolith to 0 fresh rock"),
    "saturation": ("1", "water saturation"),
    "sigma_eff": ("Pa", "effective stress"),
    "porosity": ("1", "porosity"),
    "log10_permeability": ("log10(m2)", "permeability"),
    "theta_r": ("m3/m3", "van Genuchten residual water content"),
    "theta_s": ("m3/m3", "van Genuchten saturated water content"),
    "alpha": ("1/m", "van Genuchten alpha"),
    "n": ("1", "van Genuchten n"),
    "z_soil": ("m", "base of the soil, below the ground or the glacier bed"),
    "z_cover": ("m", "base of the Quaternary cover, below the ground or the glacier bed"),
    "z_weathered": ("m", "base of the weathered layer, below the ground or the glacier bed"),
    "z_fractured": ("m", "base of the fractured zone, below the ground or the glacier bed"),
    "ice_thickness": ("m", "glacier ice thickness above the column"),
    "water_table": ("m", "water-table depth below the ground (Fan et al. 2017); 0 under ice"),
    "cz_thickness": ("m", "thickness of each layer of the column"),
}


def _unit_flags() -> dict:
    from rainier3d.petro.table import unit_names

    names = unit_names()
    ids = sorted(names)
    return {"flag_values": ids, "flag_meanings": " ".join(names[i] for i in ids)}


def describe(ds: xr.Dataset, table: dict) -> xr.Dataset:
    """Set units and long_name of the variables of ``ds`` found in ``table`` (and of x, y, z)."""
    for v, (units, long_name) in table.items():
        if v in ds.variables:
            ds[v].attrs.update({"units": units, "long_name": long_name})
    for c, a in COORDS.items():
        if c in ds.coords:
            ds[c].attrs.update(a)
    if "unit" in ds and table is LEVEL:
        ds["unit"].attrs.update(_unit_flags())
    return ds
