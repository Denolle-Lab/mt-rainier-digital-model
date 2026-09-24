"""Load the unit petrophysics table and the perturbation factors."""

from __future__ import annotations

import pandas as pd
import yaml

from rainier3d.config.domain import REPO

PETRO = REPO / "configs" / "petrophysics.csv"
PERTURB = REPO / "configs" / "perturbations.yaml"
UNITS = REPO / "configs" / "units.yaml"


def units_config() -> dict:
    return yaml.safe_load(UNITS.read_text())


def unit_names() -> dict[int, str]:
    return {int(k): v["name"] for k, v in units_config()["units"].items()}


def petro_table() -> pd.DataFrame:
    df = pd.read_csv(PETRO)
    by_name = {v: k for k, v in unit_names().items()}
    missing = set(by_name) - {"air"} - set(df["unit"])
    if missing:
        raise ValueError(f"units without petrophysics rows: {sorted(missing)}")
    df["unit_id"] = df["unit"].map(by_name)
    return df.set_index("unit_id")


def perturbations() -> dict:
    return yaml.safe_load(PERTURB.read_text())
