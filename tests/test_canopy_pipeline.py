"""S26: the vendored canopy-storage code is unmodified; S19 prefers the pipeline product when it exists."""

import hashlib
import importlib.util
import subprocess
from pathlib import Path

import rainier3d.surface.canopy as C

REPO = Path(__file__).resolve().parents[1]
VENDOR = REPO / "third_party" / "canopy-storage_seismic"


def test_vendored_code_is_unmodified_and_licensed():
    assert (VENDOR / "LICENSE").read_text().startswith("MIT License")
    assert (VENDOR / "LICENSE-DATA").exists() and (VENDOR / "PROVENANCE.md").exists()
    # the files are committed exactly as vendored: no working-tree edits against the index
    r = subprocess.run(["git", "diff", "--quiet", "--", str(VENDOR)], cwd=REPO)
    assert r.returncode == 0


def test_every_runner_step_points_at_a_vendored_script():
    spec = importlib.util.spec_from_file_location("s25", REPO / "scripts" / "26_canopy_pipeline.py")
    s25 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(s25)
    for folder, script, _, _ in s25.STEPS.values():
        assert (s25.VENDOR / folder / script).is_file()


def test_source_path_prefers_the_pipeline_product(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "PIPELINE_OUT", tmp_path)
    spec = {"file": "~/Downloads/x/lai.tif", "pipeline_file": "Sentinel2/lai.tif"}
    assert C.source_path(spec, tmp_path / "dl") == tmp_path / "dl" / "x" / "lai.tif"  # not built yet
    (tmp_path / "Sentinel2").mkdir()
    (tmp_path / "Sentinel2" / "lai.tif").write_bytes(hashlib.sha256(b"x").digest())
    assert C.source_path(spec, tmp_path / "dl") == tmp_path / "Sentinel2" / "lai.tif"
    assert C.source_path({"file": "~/Downloads/y.tif"}, tmp_path / "dl") == tmp_path / "dl" / "y.tif"
