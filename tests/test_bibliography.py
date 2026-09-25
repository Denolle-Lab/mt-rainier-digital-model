"""Every citation key in the paper has an entry in docs/references.bib (no network; runs in CI)."""

import importlib.util
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _bib_script():
    spec = importlib.util.spec_from_file_location("bib", REPO / "scripts" / "15_bibliography.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_paper_citation_is_in_references_bib():
    keys = _bib_script().paper_keys()
    bib = set(re.findall(r"^@\w+\{([^,]+),", (REPO / "docs" / "references.bib").read_text(), re.M))
    assert len(keys) > 50
    assert not sorted(keys - bib)


def test_cross_references_are_not_citations():
    mod = _bib_script()
    found = {k for k in mod.CITE_RE.findall("see [@fig:map] and [@tbl:raw]; @eq:crack; [@ni2023]; x@y.z")}
    assert {k for k in found if k.split(":")[0] not in mod.XREF} == {"ni2023"}
