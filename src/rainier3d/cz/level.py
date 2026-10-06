"""The critical zone inside the subsurface model (S4): one medium (rainier3d.cz.medium) on the columns of
each level, with the near-surface cells set to the travel-time average of the columns inside them.

Inputs, sampled at the cell columns of each level: the geology model's surface node (S3: ice thickness,
surface unit, bedrock unit, deposit thickness) and the S2 layers (soil thickness, bulk density, clay, POLARIS
hydraulics, depth to bedrock, canopy height, the water table named in configs/cz.yaml medium.water_table).
"""

from __future__ import annotations

import logging

import numpy as np
import xarray as xr
import yaml

from rainier3d.config.domain import REPO
from rainier3d.cz import medium as M
from rainier3d.geomodel.rules import AIR, ICE
from rainier3d.petro.table import rock_unit_ids
from rainier3d.properties.assign import rock_properties

ROWS = 40  # rows of columns per chunk (memory)


def _integral(cum, edges, dz, e):
    """Integral from the top to depth e (per column) of a field given by its cumulative values on edges."""
    i = np.clip(np.searchsorted(edges, e, side="right") - 1, 0, len(dz) - 1)
    c0 = np.take_along_axis(cum, i[None], 0)[0]
    rate = (np.take_along_axis(cum, (i + 1)[None], 0)[0] - c0) / dz[i]
    return c0 + rate * (e - edges[i])


class Context:
    def __init__(
        self, geo_surface: xr.Dataset, layers: xr.Dataset, soil: xr.Dataset | None, cfg: dict, units: dict
    ):
        self.cfg, md = cfg, cfg["medium"]
        names = {v["name"]: int(k) for k, v in units.items()}
        w = md["weathering"]
        hard = w["consolidated_kinds"]
        self.unit_factor = {
            int(k): w["consolidated_factor"] for k, v in units.items() if v.get("kind") in hard
        }
        self.unit_factor.update({names[k]: f for k, f in w["surface_unit_factor"].items()})
        g = geo_surface
        src = {
            "ice_thickness": g["ice_thickness"],
            "surface_unit": g["surface_unit"],
            "bedrock_unit": g["bedrock_unit"],
            "cover_base": g["unconsolidated_thickness"] if "unconsolidated_thickness" in g else None,
            "soil_thickness": layers["soil_thickness"],
            "bulk_density": layers["bulk_density_0_100cm"],
            "clay_fraction": layers["clay_0_100cm"] / 100.0,
            "log10_ksat": layers["log10_ksat_0_100cm"],
            "theta_s": layers["theta_s_0_100cm"],
            "weathered_prior": layers[md["weathering"]["prior"]],
            "canopy_height": layers["canopy_height"],
            "water_table": layers[md["water_table"]],
        }
        if soil is not None and "theta_r" in soil:
            top = soil["layer_bottom"] <= 1.0
            src["theta_r"] = soil["theta_r"].where(top).mean("polaris_layer")
            src["alpha"] = (10 ** soil["log10_vg_alpha"]).where(top).mean("polaris_layer")
            src["n"] = soil["vg_n"].where(top).mean("polaris_layer")
        self.src = {k: v for k, v in src.items() if v is not None}
        self.z, self.dz = M.fine_grid(cfg)
        self.profiles = {}

    def inputs(self, x, y) -> dict:
        """2D inputs at the columns (x, y) of a level (nearest surface cell)."""
        out = {k: v.sel(x=x, y=y, method="nearest").values for k, v in self.src.items()}
        out.setdefault("cover_base", np.zeros_like(out["soil_thickness"]))
        out["under_ice"] = np.nan_to_num(out["ice_thickness"]) > 0
        out["ice_thickness"] = np.nan_to_num(out["ice_thickness"])
        out["overburden_pa"] = self.cfg["medium"]["ice_density_kgm3"] * 9.81 * out["ice_thickness"]
        out["unit_factor"] = self.unit_factor
        out["water_table"] = np.nan_to_num(out["water_table"], nan=10.0)
        return out

    def water_table_depth(self, level: xr.Dataset):
        """Depth below the ground of the water table of the effective pressure: at the bed under ice."""
        i = self.inputs(level.x, level.y)
        return np.where(i["under_ice"], i["ice_thickness"], i["ice_thickness"] + i["water_table"])[None]

    def apply(self, level, vp, vs, rho, d, table, pert, geo_cal):
        """Near-surface cells from the fine columns (travel-time average of vp and vs, mean density);
        porosity, permeability and the weathering index of every cell. vp, vs in km/s, rho in g/cm3."""
        md = self.cfg["medium"]
        u = level["unit"].values
        zl = level.z.values
        dzl = float(abs(zl[1] - zl[0]))
        inp_all = self.inputs(level.x, level.y)
        vp, vs, rho = vp.copy(), vs.copy(), rho.copy()
        rh = md["rock_hydraulics"]
        phi = np.full(u.shape, rh["porosity"], float)
        logk = M.log10_k_rock(d, rh)
        W3 = np.zeros(u.shape)
        edges = np.append(0.0, np.cumsum(self.dz))
        keep = {}
        ny = u.shape[1]
        for j0 in range(0, ny, ROWS):
            sl = slice(j0, min(j0 + ROWS, ny))
            inp = {k: (v[sl] if isinstance(v, np.ndarray) else v) for k, v in inp_all.items()}
            ice = inp["ice_thickness"]
            pr = self._profile(level, inp, sl, slice(None), table, pert, geo_cal)
            # cumulative slowness, mass, porosity and log-permeability on the fine layer edges
            cum = {
                key: np.concatenate(
                    [np.zeros((1,) + pr["vp"].shape[1:]), np.cumsum(val * self.dz[:, None, None], axis=0)]
                )
                for key, val in (
                    ("tp", 1 / pr["vp"]),
                    ("ts", 1 / pr["vs"]),
                    ("m", pr["rho"]),
                    ("phi", pr["porosity"]),
                    ("lk", pr["log10_permeability"]),
                    ("w", pr["weathering_index"]),
                )
            }
            base = edges[-1]
            for kk in range(len(zl)):
                a = np.clip(d[kk, sl] - dzl / 2 - ice, 0.0, None)  # the cell in column coordinates
                b = d[kk, sl] + dzl / 2 - ice
                touch = (u[kk, sl] != AIR) & (u[kk, sl] != ICE) & (b > 0) & (a < base)
                if not touch.any():
                    continue
                bb = np.minimum(b, base)
                h = np.maximum(bb - a, 1e-9)
                deep = np.maximum(b - base, 0.0)  # below the fine columns the cell keeps its rock value
                tot = h + deep
                part = {
                    key: _integral(cum[key], edges, self.dz, bb) - _integral(cum[key], edges, self.dz, a)
                    for key in cum
                }
                vp_new = tot / (part["tp"] + deep / (vp[kk, sl] * 1e3)) / 1e3
                vs_new = tot / (part["ts"] + deep / (vs[kk, sl] * 1e3)) / 1e3
                rho_new = (part["m"] + rho[kk, sl] * 1e3 * deep) / tot / 1e3
                vp[kk, sl] = np.where(touch, vp_new, vp[kk, sl])
                vs[kk, sl] = np.where(touch, vs_new, vs[kk, sl])
                rho[kk, sl] = np.where(touch, rho_new, rho[kk, sl])
                phi[kk, sl] = np.where(touch, (part["phi"] + phi[kk, sl] * deep) / tot, phi[kk, sl])
                logk[kk, sl] = np.where(touch, (part["lk"] + logk[kk, sl] * deep) / tot, logk[kk, sl])
                W3[kk, sl] = np.where(touch, part["w"] / tot, 0.0)
            keep[j0] = pr
        self.profiles[level.sizes["x"], level.sizes["y"]] = (keep, inp_all)
        return vp, vs, rho, {"porosity": phi, "log10_permeability": logk, "weathering_index": W3}

    def _profile(self, level, inp, sy, sx, table, pert, geo_cal, head=None) -> dict:
        """Fine columns of the level columns (sy, sx): the unit and alteration of the level cell at each fine
        depth (deposits and ice give way to the bedrock unit) feed the rock law of S4."""
        u = level["unit"].values[:, sy, sx]
        alt = level["alteration"].values[:, sy, sx]
        dem = level["elevation"].values[sy, sx]
        zl = level.z.values
        ice = inp["ice_thickness"]
        elev = dem[None] - (self.z.reshape((-1,) + (1,) * dem.ndim) + ice[None])
        k = np.clip(np.rint((zl[0] - elev) / (zl[0] - zl[1])).astype(int), 0, len(zl) - 1)
        uf = np.take_along_axis(u, k, axis=0)
        af = np.nan_to_num(np.take_along_axis(alt, k, axis=0))
        uf = np.where(np.isin(uf, np.array(sorted(rock_unit_ids()))), uf, inp["bedrock_unit"][None])

        def rock_fn(p_mpa):
            a, b, c = rock_properties(uf, p_mpa, af, table, pert, geo_cal)
            return a * 1e3, b * 1e3, c * 1e3

        return M.profile(self.z, self.dz, inp, rock_fn, self.cfg, head=head)

    def column(self, level, x: float, y: float, table, pert, geo_cal, head=None, override=None) -> dict:
        """The fine column of the level column nearest (x, y), with an optional pressure head (m) over its top
        layers: the same medium and rock law as the model, for synthetics at a station."""
        j = int(np.abs(level.y.values - y).argmin())
        i = int(np.abs(level.x.values - x).argmin())
        inp = self.inputs(level.x[i : i + 1], level.y[j : j + 1])
        inp = {k: (v[0, 0] if isinstance(v, np.ndarray) and v.ndim == 2 else v) for k, v in inp.items()}
        inp.update(override or {})  # e.g. a trial weathering depth in calibration
        pr = self._profile(level, inp, j, i, table, pert, geo_cal, head=head)
        pr["z"], pr["dz"], pr["column_index"] = self.z, self.dz, (j, i)
        pr["ice_thickness"] = float(inp["ice_thickness"])
        return pr

    def fine_dataset(self, level: xr.Dataset) -> xr.Dataset:
        """The fine columns of a level (after ``apply``) as the /cz node: (cz_depth, y, x)."""
        keep, inp = self.profiles[level.sizes["x"], level.sizes["y"]]
        names = (
            "vp",
            "vs",
            "rho",
            "weathering_index",
            "saturation",
            "sigma_eff",
            "porosity",
            "log10_permeability",
            "theta_r",
            "theta_s",
            "alpha",
            "n",
        )
        arrays = {
            k: np.concatenate([keep[j][k] for j in sorted(keep)], axis=1).astype("float32") for k in names
        }
        b = [
            np.concatenate(
                [np.broadcast_to(keep[j]["boundaries"][i], keep[j]["vp"].shape[1:]) for j in sorted(keep)],
                axis=0,
            )
            for i in range(4)
        ]
        coords = {"cz_depth": self.z, "y": level.y.values, "x": level.x.values}
        ds = xr.Dataset({k: (("cz_depth", "y", "x"), v) for k, v in arrays.items()}, coords=coords)
        for name, v in zip(("z_soil", "z_cover", "z_weathered", "z_fractured"), b, strict=True):
            ds[name] = (("y", "x"), v.astype("float32"))
        ds["ice_thickness"] = (("y", "x"), inp["ice_thickness"].astype("float32"))
        ds["water_table"] = (
            ("y", "x"),
            np.where(inp["under_ice"], 0.0, inp["water_table"]).astype("float32"),
        )
        ds["cz_depth"].attrs = {
            "units": "m",
            "long_name": "depth below the ground or the glacier bed (layer centre)",
        }
        ds["cz_thickness"] = ("cz_depth", self.dz.astype("float32"))
        return ds


def context_from_disk(dom, geo) -> Context | None:
    """The critical zone of configs/cz.yaml from the S2 stores, or None without them (the M1 model)."""
    from rainier3d.petro.table import units_config

    layers = dom.path("processed") / "surface_layers.zarr"
    if not layers.exists():
        logging.getLogger(__name__).warning("no %s: properties without the critical zone", layers)
        return None
    soil = dom.path("processed") / "soil_profile.zarr"
    return Context(
        geo["surface"].to_dataset(),
        xr.open_zarr(layers, consolidated=False).load(),
        xr.open_zarr(soil, consolidated=False).load() if soil.exists() else None,
        yaml.safe_load((REPO / "configs" / "cz.yaml").read_text()),
        units_config()["units"],
    )
