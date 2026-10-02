"""The platform data freeze and the machine-local inputs (configs/platform.yaml)."""

from __future__ import annotations

import shutil
from datetime import datetime
from functools import cache
from pathlib import Path

import yaml

from rainier3d.config.domain import REPO

CFG = REPO / "configs" / "platform.yaml"


@cache
def config() -> dict:
    return yaml.safe_load(CFG.read_text())


def as_of() -> str:
    return str(config()["as_of"])


def as_of_datetime() -> datetime:
    """End of the as-of day (naive UTC): a sensor whose last epoch ends later counts as operating."""
    return datetime.fromisoformat(as_of()).replace(hour=23, minute=59, second=59)


def local_input(key: str, raw: Path | None = None) -> Path:
    """data/raw/<to> for a machine-local input, staged once from <from> when the copy is missing."""
    c = config()["local_inputs"][key]
    dst = (raw or REPO / "data" / "raw") / c["to"]
    if dst.exists():
        return dst
    src = Path(c["from"]).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"{key}: {dst} is not staged and {src} does not exist on this machine")
    dst.parent.mkdir(parents=True, exist_ok=True)
    (shutil.copytree if src.is_dir() else shutil.copy2)(src, dst)
    return dst
