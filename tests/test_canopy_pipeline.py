"""S28: the vendored canopy-storage code is unmodified; S19 prefers the pipeline product when it exists."""

import hashlib
import importlib.util
from pathlib import Path

import pytest

import rainier3d.surface.canopy as C

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "third_party" / "canopy-storage_seismic"


def test_vendored_code_is_unmodified_and_licensed():
    """Every vendored file matches the SHA-256 recorded at vendoring (SHA256SUMS; no git needed)."""
    assert (VENDOR / "LICENSE").read_text().startswith("MIT License")
    assert (VENDOR / "PROVENANCE.md").exists()
    sums = [line.split(maxsplit=1) for line in (VENDOR / "SHA256SUMS").read_text().splitlines() if line]
    assert len(sums) == 16  # 13 files of non-seismic_code, LICENSE, LICENSE-DATA, environment.yml
    for digest, name in sums:
        assert hashlib.sha256((VENDOR / name).read_bytes()).hexdigest() == digest, name


def test_every_runner_step_points_at_a_vendored_script():
    spec = importlib.util.spec_from_file_location("s28", REPO / "scripts" / "28_canopy_pipeline.py")
    s28 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s28)
    for folder, script, _, _ in s28.STEPS.values():
        assert (s28.VENDOR / folder / script).is_file()


def test_source_path_prefers_the_pipeline_product(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "PIPELINE_OUT", tmp_path)
    spec = {"file": "~/Downloads/x/lai.tif", "pipeline_file": "Sentinel2/lai.tif"}
    assert C.source_path(spec, tmp_path / "dl") == tmp_path / "dl" / "x" / "lai.tif"  # not built yet
    (tmp_path / "Sentinel2").mkdir()
    (tmp_path / "Sentinel2" / "lai.tif").write_bytes(b"x")
    assert C.source_path(spec, tmp_path / "dl") == tmp_path / "Sentinel2" / "lai.tif"
    assert C.source_path({"file": "~/Downloads/y.tif"}, tmp_path / "dl") == tmp_path / "dl" / "y.tif"


@pytest.mark.parametrize("bad", ["/etc/passwd", "../outside.tif", "GEDI/../../x.tif"])
def test_pipeline_file_must_stay_inside_the_output_folder(tmp_path, bad):
    with pytest.raises(ValueError):
        C.source_path({"file": "~/Downloads/y.tif", "pipeline_file": bad}, tmp_path)
