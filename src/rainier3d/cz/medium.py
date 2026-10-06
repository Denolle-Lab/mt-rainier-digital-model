"""One medium from soil to fresh rock (configs/cz.yaml ``medium``; docs/critical_zone.md, "Consistency").

A weathering index W is 1 in soil, cover and weathered rock and falls linearly to 0 across the fractured
zone. The granular frame (Hertz-Mindlin / soft sand with Gassmann-Brie fluid, rainier3d.cz.rockphysics) and
the rock law of the subsurface model (crack closure with the unit, alteration and magma factors,
rainier3d.properties.assign.rock_properties) are evaluated at the same effective stress and blended by a
Hill average of their moduli weighted by W, so the velocities are continuous from the soil into L1. Porosity
and permeability are blended the same way (permeability in log space); the van Genuchten class follows the
dominant end-member. All arrays are (depth, ...) with depth below the top of the column: the ground, or the
glacier bed."""

from __future__ import annotations

import numpy as np

from rainier3d.cz import rockphysics as R

SOIL, COVER, WEATHERED, ROCK = 0, 1, 2, 3


def fine_grid(cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """Layer centres and thicknesses (m) of the fine columns, geometric from top_m to medium.fine_base_m."""
    c, base = cfg["column"], cfg["medium"]["fine_base_m"]
    h, tops = c["top_m"], [0.0]
    while tops[-1] + h < base:
        tops.append(tops[-1] + h)
        h *= c["growth"]
    edges = np.append(tops, base)
    return 0.5 * (edges[:-1] + edges[1:]), np.diff(edges)


def boundaries(inp: dict, cfg: dict) -> tuple:
    """Bases (m) of soil, cover, weathered rock and the fractured zone, with the weathering drivers: the prior
    depth scaled on young surfaces and under tall forest; no weathered layer under present ice."""
    lay, w = cfg["layers"], cfg["medium"]["weathering"]
    ice = inp["under_ice"]
    z1 = np.where(ice, 0.0, np.clip(np.nan_to_num(inp["soil_thickness"]), 0.0, 2.01))
    z2 = np.where(ice, 0.0, np.maximum(z1, np.nan_to_num(inp["cover_base"])))
    prior = np.nan_to_num(inp["weathered_prior"], nan=2 * lay["weathered_min_thickness_m"])
    fac = np.ones_like(prior)
    for uid, f in inp["unit_factor"].items():
        fac = np.where(inp["surface_unit"] == uid, f, fac)
    fc = w["forest"]
    fac = np.where(np.nan_to_num(inp["canopy_height"]) >= fc["canopy_height_m"], fac * fc["factor"], fac)
    z3 = np.maximum(z2 + lay["weathered_min_thickness_m"], prior * fac)
    z3 = np.where(ice, 0.0, z3)
    return z1, z2, z3, z3 + lay["fractured_thickness_m"]


def profile(z, dz, inp: dict, rock_fn, cfg: dict, head=None) -> dict:
    """Fine columns. ``inp``: arrays broadcastable over the columns (see rainier3d.cz.level);
    ``rock_fn(p_mpa)`` returns the rock end-member vp, vs (m/s) and rho (kg/m3) on the same (depth, ...)
    shape; ``head`` (m) replaces the hydrostatic pressure head of the water table."""
    rp, lay, md = cfg["rock_physics"], cfg["layers"], cfg["medium"]
    shape = (len(z),) + np.shape(inp["soil_thickness"])
    Z = np.broadcast_to(np.reshape(z, (-1,) + (1,) * (len(shape) - 1)), shape)
    DZ = np.broadcast_to(np.reshape(dz, (-1,) + (1,) * (len(shape) - 1)), shape)
    z1, z2, z3, z4 = boundaries(inp, cfg)
    W = np.clip((z4 - Z) / np.maximum(z4 - z3, 1e-6), 0.0, 1.0)
    W = np.where(Z < z3, 1.0, W)
    W = np.where(inp["under_ice"], md["weathering"]["under_ice"], W)
    cls = np.select([Z < z1, Z < z2, Z < z3], [SOIL, COVER, WEATHERED], ROCK)

    rho_s, rho_w = rp["grain_density_kgm3"], rp["water_density_kgm3"]
    phi_soil = np.clip(1 - np.nan_to_num(inp["bulk_density"], nan=1.2) * 1000 / rho_s, 0.05, 0.8)
    p0, p1 = lay["weathered_porosity"]
    frac = np.clip((Z - z2) / np.maximum(z3 - z2, 1e-6), 0, 1)
    phi_g = np.select(
        [cls == SOIL, cls == COVER, cls == WEATHERED],
        [phi_soil, lay["cover_porosity"], p0 + (p1 - p0) * frac],
        p1,
    )

    vg_c, vg_w, vg_r = (
        np.array(lay["vg_cover"]),
        np.array(lay["vg_weathered"]),
        np.array(md["rock_hydraulics"]["vg"]),
    )
    vgs = [
        np.nan_to_num(inp[k], nan=v) for k, v in zip(("theta_r", "theta_s", "alpha", "n"), vg_c, strict=True)
    ]
    tr, ts, al, n = (
        np.select([cls == SOIL, cls == COVER, cls == WEATHERED], [vgs[i], vg_c[i], vg_w[i]], vg_w[i])
        for i in range(4)
    )
    h = Z - np.where(inp["under_ice"], 0.0, inp["water_table"])
    if head is not None:
        h = h.copy()
        h[: len(head)] = head
    psi = np.maximum(-h, 0.0)
    se = np.where(h >= 0, 1.0, R.vg_se(psi, al, n))
    S = np.clip((tr + (ts - tr) * se) / ts, 0, 1)

    # density: granular from porosity and saturation; rock from the rock law at a first-guess pressure
    rho_g = (1 - phi_g) * rho_s + phi_g * S * rho_w
    p_guess = 1.5e-2 * (Z + 1.0)  # ~ (2500 - 1000) g z in MPa
    _, _, rho_r0 = rock_fn(p_guess)
    rho = W * rho_g + (1 - W) * rho_r0
    w = rho * R.G * DZ
    sig_tot = inp["overburden_pa"] + np.cumsum(w, axis=0) - w / 2
    u = np.where(h > 0, rho_w * R.G * h, R.suction_stress(psi, se, rho_w) * W)
    sig = np.maximum(sig_tot - u, cfg["column"]["min_effective_stress_kpa"] * 1e3)

    vp_r, vs_r, rho_r = rock_fn(sig / 1e6)
    clay = np.where(cls <= COVER, np.nan_to_num(inp["clay_fraction"]), 0.0)
    K_s, mu_s = R.hill(
        clay, [v * 1e9 for v in rp["quartz_feldspar_moduli_gpa"]], [v * 1e9 for v in rp["clay_moduli_gpa"]]
    )
    Kd, mud = R.soft_sand(
        sig, phi_g, K_s, mu_s, rp["coordination_number"], rp["slip_fraction"], rp["critical_porosity"]
    )
    Kf = R.brie(S, rp["water_modulus_gpa"] * 1e9, rp["air_modulus_gpa"] * 1e9, rp["brie_exponent"])
    Kg = R.gassmann(Kd, K_s, Kf, np.maximum(phi_g, 1e-6))
    mu_r = rho_r * vs_r**2
    K_r = rho_r * vp_r**2 - 4 / 3 * mu_r

    def hill(a, b):
        voigt = W * a + (1 - W) * b
        reuss = 1 / (W / np.maximum(a, 1.0) + (1 - W) / np.maximum(b, 1.0))
        return 0.5 * (voigt + reuss)

    K, mu = hill(Kg, K_r), hill(mud, mu_r)
    rho = W * rho_g + (1 - W) * rho_r
    vs = np.sqrt(mu / rho)
    vp = np.sqrt((K + 4 / 3 * mu) / rho)

    rh = md["rock_hydraulics"]
    ksat = np.select(
        [cls == SOIL, cls == COVER],
        [
            10.0 ** np.nan_to_num(inp["log10_ksat"], nan=np.log10(lay["ksat_ms"]["cover"])),
            lay["ksat_ms"]["cover"],
        ],
        lay["ksat_ms"]["weathered"],
    )
    log_k_g = np.log10(ksat * md["water_viscosity_pa_s"] / (rho_w * R.G))
    depth_total = Z + inp["ice_thickness"]
    log_k_r = log10_k_rock(depth_total, rh)
    rock_dom = W < 0.5
    return {
        "vp": vp,
        "vs": vs,
        "rho": rho,
        "weathering_index": W,
        "class": cls,
        "saturation": S,
        "sigma_eff": sig,
        "porosity": W * phi_g + (1 - W) * rh["porosity"],
        "log10_permeability": W * log_k_g + (1 - W) * log_k_r,
        "theta_r": np.where(rock_dom, vg_r[0], tr),
        "theta_s": np.where(rock_dom, vg_r[1], ts),
        "alpha": np.where(rock_dom, vg_r[2], al),
        "n": np.where(rock_dom, vg_r[3], n),
        "head": h,
        "boundaries": (z1, z2, z3, z4),
    }


def log10_k_rock(depth_m, rh: dict):
    """Permeability of fresh rock (log10 m2) on the crustal permeability-depth curve, capped near the
    surface."""
    zk = np.maximum(np.asarray(depth_m, float), 1.0) / 1000.0
    return np.minimum(rh["log10_k_at_1km"] + rh["log10_k_slope"] * np.log10(zk), rh["log10_k_cap"])
