import importlib.util
import os
import time

from rainier3d.config.domain import REPO
from rainier3d.config.platform import as_of, as_of_datetime, config

spec = importlib.util.spec_from_file_location("s32", REPO / "scripts" / "32_platform.py")
S32 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(S32)


def test_bundle_tarball_bytes_depend_only_on_the_files(tmp_path):
    src = tmp_path / "atlas"
    (src / "model").mkdir(parents=True)
    (src / "model" / "b.json").write_text("{}")
    (src / "a.bin").write_bytes(b"\x00\x01")
    S32.tarball(src, tmp_path / "one.tar.gz", mtime=0)
    time.sleep(1.1)
    os.utime(src / "a.bin")  # a newer file time must not change the archive
    S32.tarball(src, tmp_path / "two.tar.gz", mtime=0)
    assert (tmp_path / "one.tar.gz").read_bytes() == (tmp_path / "two.tar.gz").read_bytes()


def test_freeze_date_and_local_inputs_are_configured():
    assert as_of_datetime().date().isoformat() == as_of()
    for c in config()["local_inputs"].values():
        assert not c["to"].startswith(("/", "~"))  # staged under data/raw/
