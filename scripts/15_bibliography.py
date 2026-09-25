"""Bibliography: every citation in the repository -> docs/references.bib and docs/citations.csv.

Sources scanned: configs/sources.yaml (keys, doi, article_doi, url), and every DOI string in configs/, docs/
(Markdown), src/ and scripts/. BibTeX comes from doi.org content negotiation
(Crossref or DataCite) and is cached: entries already in references.bib are not fetched again.
Keys: the sources.yaml key for its ``doi`` (``<key>_article`` for ``article_doi``), so a ``source_key`` in
configs/ is also the citation key; other DOIs get ``<firstauthor><year>`` from the record.
Registry entries without a DOI but with a web URL become @misc; local files (file://) are listed in
citations.csv as internal and are not cited. Every key cited in docs/paper/*.md must come out of this run;
otherwise the script stops without writing, so a citation cannot silently lose its entry.

citations.csv columns: key, doi, kind (doi | url | internal), verified (from sources.yaml), fetched
(ok | failed), cited_in (files that mention the DOI or the key).

Usage: pixi run bib
"""

from __future__ import annotations

import html
import logging
import re
import time
import unicodedata

import pandas as pd
import requests
import yaml

from rainier3d.config.domain import REPO

BIB = REPO / "docs" / "references.bib"
CSV = REPO / "docs" / "citations.csv"
DOI_RE = re.compile(
    # SICI form, e.g. 10.1130/0016-7606(1997)109<0143:TOMFMR>2.3.CO;2
    r"10\.\d{4,9}/[\w.-]+\(\d{4}\)\d+<[^\s>]+>\d\.\d\.[A-Za-z]{2};\d"
    r"|10\.\d{4,9}/(?:[^\s,;|()\]\"'<>`]|\([^\s()]*\))+"
)  # balanced (...) kept: 0377-0273(94)00081-Q
SCAN = ["configs", "docs", "src", "scripts", "README.md", "AGENTS.md"]
SKIP_SUFFIX = {".png", ".html", ".bib", ".csv", ".lock"}

log = logging.getLogger(__name__)


def clean(doi: str) -> str:
    return doi.rstrip(".").removesuffix("</a>").strip()


def scan_files() -> dict[str, set[str]]:
    """DOI (lower case) -> files that mention it."""
    hits: dict[str, set[str]] = {}
    paths = []
    for s in SCAN:
        p = REPO / s
        paths += [p] if p.is_file() else [f for f in p.rglob("*") if f.is_file()]
    for f in paths:
        if f.suffix in SKIP_SUFFIX or "__pycache__" in f.parts:
            continue
        try:
            text = f.read_text()
        except UnicodeDecodeError:
            continue
        for d in DOI_RE.findall(text):
            hits.setdefault(clean(d).lower(), set()).add(str(f.relative_to(REPO)))
    return hits


def read_bib() -> dict[str, str]:
    """Existing entries by DOI (lower case)."""
    if not BIB.exists():
        return {}
    out = {}
    for block in re.split(r"\n(?=@)", BIB.read_text()):
        m = re.search(r"doi\s*=\s*[{\"]([^}\"]+)", block, re.I)
        if m:
            out[m.group(1).lower()] = block.strip()
    return out


def fetch(doi: str) -> str | None:
    try:
        r = requests.get(
            f"https://doi.org/{doi}", headers={"Accept": "application/x-bibtex; charset=utf-8"}, timeout=30
        )
    except requests.RequestException:
        return None
    if r.status_code != 200 or not r.text.lstrip().startswith("@"):
        return None
    r.encoding = "utf-8"
    return r.text.strip()


# Records with malformed author fields, corrected from the publications
AUTHOR_FIXES = {
    "10.1007/s000240050012": "Watters, R. J. and Zimbelman, D. R. and Bowman, S. D. and Crowley, J. K.",
    "10.7265/n5-rgi-60": "{RGI Consortium}",
    "10.1029/2018eo104623": "Blewitt, Geoffrey and Hammond, William C. and Kreemer, Corn{\\'e}",
    "10.5066/p14hj3ic": "Wirth Moriarty, Erin and Grant, Alex R. and Stone, Ian P. and "
    "Stephenson, William J. "
    "and Frankel, Arthur D.",
}


ORG_WORDS = {
    "service",
    "survey",
    "consortium",
    "center",
    "centre",
    "geological",
    "monitoring",
    "array",
    "agency",
    "society",
    "laboratory",
    "institute",
    "university",
    "program",
    "group",
    "network",
    "project",
    "wgms",
}


def unbrace_names(author: str) -> str:
    """DataCite writes {Gina M Belair}, which BibTeX reads as one surname; organisations stay braced."""

    def fix(m):
        words = m.group(1).split()
        if 2 <= len(words) <= 4 and not {w.strip("()").lower() for w in words} & ORG_WORDS:
            return f"{words[-1]}, {' '.join(words[:-1])}"
        return m.group(0)

    inner = author[1:-1] if author.startswith("{") and author.endswith("}") else author
    return "{" + re.sub(r"\{([^{},]+)\}", fix, inner) + "}"


def split_fields(body: str) -> list[str]:
    """Split 'a={x, y}, b=2' at top-level commas."""
    out, depth, cur = [], 0, ""
    for ch in body:
        depth += ch == "{"
        depth -= ch == "}"
        if ch == "," and depth == 0:
            out.append(cur.strip())
            cur = ""
        else:
            cur += ch
    return [f for f in [*out, cur.strip()] if f]


def normalize(entry: str, doi: str, key: str, override: dict | None = None) -> str:
    """One field per line, BibTeX-safe text (no HTML, ASCII page dashes), key set, author fixes applied."""
    m = re.match(r"\s*@(\w+)\s*\{(.*)\}\s*$", entry, re.S)
    typ, body = m.group(1).lower(), m.group(2)
    fields = split_fields(body)
    if "=" not in fields[0].split("{")[0]:  # drop the original key, which may itself contain commas
        fields = fields[1:]
    while fields and "=" not in fields[0]:
        fields = fields[1:]
    out = {}
    for f in fields:
        name, _, val = f.partition("=")
        val = val.strip()
        val = re.sub(r"<i>(.*?)</i>", r"\\textit{\1}", val)
        val = re.sub(r"</?(scp|sub|sup|b|span)[^>]*>", "", val)
        val = html.unescape(val).replace("\u2010", "-").replace("\u2009", " ")  # &amp;, Unicode hyphen
        val = re.sub(r"(?<!\\)&", r"\\&", val)  # BibTeX needs \& for a literal ampersand
        if name.strip().lower() not in ("url", "doi"):
            val = re.sub(r"(?<!\\)([_%#])", r"\\\1", val)  # e.g. ETH_GlobalCanopyHeight in a title
        out[name.strip().lower()] = val
    if "pages" in out:
        out["pages"] = out["pages"].replace("–", "--").replace("—", "--")
    if "author" in out:
        out["author"] = unbrace_names(out["author"])
    if doi in AUTHOR_FIXES:
        out["author"] = "{" + AUTHOR_FIXES[doi] + "}"
    for field, value in (override or {}).items():  # bib_author, bib_title, bib_year from the registry
        out[field] = "{" + str(value) + "}"
    body = ",\n".join(f"  {k} = {v}" for k, v in out.items())
    return f"@{typ}{{{key},\n{body}\n}}"


def auto_key(entry: str, used: set[str]) -> str:
    """<first author's family name><year>, e.g. desiena2014; a letter is added on collisions."""
    a = re.search(r"author\s*=\s*\{+([^,}]+)", entry)
    y = re.search(r"year\s*=\s*\{?(\d{4})", entry)
    name = unicodedata.normalize("NFKD", a.group(1) if a else "anon").encode("ascii", "ignore").decode()
    base = re.sub(r"[^a-z]", "", name.lower()) + (y.group(1) if y else "")
    key, i = base, 0
    while key in used:
        i += 1
        key = base + "abcdefghij"[i - 1]
    return key


def bib_escape(s: str) -> str:
    return s.replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")


PAPER = REPO / "docs" / "paper"
CITE_RE = re.compile(r"(?<![\w.])@([A-Za-z][\w:-]*[A-Za-z0-9])")
XREF = ("fig", "tbl", "eq", "sec")  # pandoc-crossref labels, not citations


def paper_keys() -> set[str]:
    """Citation keys ([@key] and @key) used in the paper's Markdown."""
    keys = set()
    for f in PAPER.glob("*.md"):
        keys |= {k for k in CITE_RE.findall(f.read_text()) if k.split(":")[0] not in XREF}
    return keys


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    reg = yaml.safe_load((REPO / "configs" / "sources.yaml").read_text())
    hits = scan_files()
    cached = read_bib()

    # DOI -> (key, verified) from the registry
    by_doi: dict[str, tuple[str, str]] = {}
    overrides: dict[str, dict] = {}  # registry corrections of a DOI record: bib_author, bib_title, bib_year
    for k, v in reg.items():
        for field, suffix in (("doi", ""), ("article_doi", "_article"), ("data_doi", "_data")):
            if v.get(field):
                by_doi[str(v[field]).lower()] = (k + suffix, str(v.get("verified", "")))
        if v.get("doi"):
            overrides[str(v["doi"]).lower()] = {
                f: v[f"bib_{f}"] for f in ("author", "title", "year") if v.get(f"bib_{f}")
            }
    dois = sorted(set(hits) | set(by_doi))

    entries, rows, used = [], [], set()
    for d in dois:
        entry = cached.get(d)
        status = "cached" if entry else None
        if entry is None:
            entry = fetch(d)
            status = "ok" if entry else "failed"
            time.sleep(0.2)
        key, verified = by_doi.get(d, (None, ""))
        if entry:
            key = key or auto_key(entry, used)
            entry = normalize(entry, d, key, overrides.get(d))
            entries.append(entry)
        key = key or d
        used.add(key)
        files = set(hits.get(d, set()))
        files |= {s for s in hits.get(key, set())}
        rows.append(
            {
                "key": key,
                "doi": d,
                "kind": "doi",
                "verified": verified,
                "fetched": status,
                "cited_in": "; ".join(sorted(files)),
            }
        )

    # registry entries without a DOI
    for k, v in reg.items():
        if any(v.get(f) for f in ("doi", "article_doi", "data_doi")):
            continue
        url = str(v.get("url", ""))
        internal = url.startswith("file://") or not url
        rows.append(
            {
                "key": k,
                "doi": "",
                "kind": "internal" if internal else "url",
                "verified": str(v.get("verified", "")),
                "fetched": "",
                "cited_in": "configs/sources.yaml",
            }
        )
        if not internal:
            who = (
                f"  author = {{{v['bib_author']}}},\n  year = {{{v.get('bib_year', '')}}},\n"
                if v.get("bib_author")
                else ""
            )
            entries.append(
                f"@misc{{{k},\n{who}  title = {{{bib_escape(str(v['title']))}}},\n"
                f"  howpublished = {{\\url{{{v.get('bib_url', url)}}}}}\n}}"
            )  # licence and verification are in citations.csv and sources.yaml, not in the citation

    # key usage in the code and docs (source_key, citation keys)
    key_re = {r["key"]: re.compile(rf"\b{re.escape(r['key'])}\b") for r in rows}
    for f in [p for s in SCAN for p in ((REPO / s).rglob("*") if (REPO / s).is_dir() else [REPO / s])]:
        if not f.is_file() or f.suffix in SKIP_SUFFIX or f.name == "sources.yaml":
            continue
        try:
            text = f.read_text()
        except UnicodeDecodeError:
            continue
        for r in rows:
            if key_re[r["key"]].search(text):
                r["cited_in"] = "; ".join(
                    sorted(set(filter(None, r["cited_in"].split("; "))) | {str(f.relative_to(REPO))})
                )

    # every key the paper cites must be produced here; otherwise stop before overwriting references.bib
    produced = {re.match(r"@\w+\{([^,]+),", e).group(1) for e in entries}
    missing = sorted(paper_keys() - produced)
    if missing:
        raise SystemExit(
            f"the paper cites keys this run does not produce: {', '.join(missing)}. "
            "Add them to configs/sources.yaml (doi, or url with bib_author/bib_year); "
            "references.bib was not written."
        )

    header = "% Generated by scripts/15_bibliography.py (pixi run bib); edit configs/sources.yaml.\n\n"
    BIB.write_text(header + "\n\n".join(entries) + "\n")
    df = pd.DataFrame(rows)
    df.to_csv(CSV, index=False)
    log.info(
        "%d DOIs (%d failed), %d URL sources, %d internal -> %s",
        (df.kind == "doi").sum(),
        (df.fetched == "failed").sum(),
        (df.kind == "url").sum(),
        (df.kind == "internal").sum(),
        BIB.relative_to(REPO),
    )
    for r in df[df.fetched == "failed"].itertuples():
        log.warning("no BibTeX for %s (%s)", r.doi, r.cited_in)


if __name__ == "__main__":
    main()
