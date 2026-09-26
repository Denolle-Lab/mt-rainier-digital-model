"""Virtual sensors: instruments repurposed to estimate a quantity they were not designed to measure.

The registry is configs/virtual_sensors.yaml (station code -> list of uses). Products that use a repurposed
instrument name its entry, and the viewer labels the instrument "virtual sensor".
"""

from __future__ import annotations

from pathlib import Path

import yaml

from rainier3d.config.domain import REPO

REGISTRY = REPO / "configs" / "virtual_sensors.yaml"
FIELDS = ("designed_for", "estimates", "method", "skill", "source", "used_by")


def load(path: Path = REGISTRY) -> dict[str, list[dict]]:
    """Station code -> its uses, each with every field of FIELDS and a source key of configs/sources.yaml."""
    from rainier3d.io.store import sources

    reg = yaml.safe_load(Path(path).read_text()) or {}
    known = sources()
    for code, uses in reg.items():
        if not isinstance(uses, list) or not uses:
            raise ValueError(f"{code}: a list of uses is expected")
        for u in uses:
            missing = [f for f in FIELDS if not u.get(f)]
            if missing:
                raise ValueError(f"{code}: missing {missing}")
            if u["source"] not in known:
                raise KeyError(f"{code}: source {u['source']!r} is not in configs/sources.yaml")
    return reg


def unregistered(codes, reg: dict | None = None) -> list[str]:
    """Codes used as virtual sensors that have no registry entry."""
    reg = load() if reg is None else reg
    return [c for c in codes if c not in reg]
