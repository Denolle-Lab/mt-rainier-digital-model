"""S17: GNSS daily positions from the original archives -> data/processed/gnss/.

  PANGA (CWU, primary): panga_raw.zip (all sites, NA-fixed) and the NA20 velocity field
  UNR (NGL, backup): NA-fixed tenv3 for network sites PANGA does not have, plus shared sites for frame checks

Every download is cached under data/raw/gnss/<archive>/ and listed with its SHA-256 in
data/raw/gnss/manifest.csv; reruns read the cache (--refresh re-downloads). Series are cut at
configs/gnss.yaml as_of, or at --as-of (a date, or "today" for the weekly refresh in
.github/workflows/gnss-weekly.yml). Writes daily.parquet (common table), sites.csv, steps.csv and fetch.json
(the as_of date used, which S18 reads).

Usage: pixi run s17 [-- --refresh] [--as-of today]
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
import time
import zipfile

import numpy as np
import pandas as pd
import yaml

from rainier3d.config.domain import REPO, load_domain
from rainier3d.geodesy import archive as A

CFG = REPO / "configs" / "gnss.yaml"


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument(
        "--as-of", help='cut the series at this date (YYYY-MM-DD or "today"); default: configs/gnss.yaml'
    )
    ap.add_argument(
        "--unr-shared", type=int, default=20, help="shared PANGA/UNR sites fetched for frame checks"
    )
    a = ap.parse_args()
    dom = load_domain()
    cfg = yaml.safe_load(CFG.read_text())
    raw, out = dom.path("raw") / "gnss", dom.path("processed") / "gnss"
    out.mkdir(parents=True, exist_ok=True)
    man = raw / "manifest.csv"
    w, s, e, n = cfg["network_bbox"]
    as_of = a.as_of or cfg["as_of"]
    if as_of == "today":
        as_of = dt.datetime.now(dt.UTC).date().isoformat()
    as_of, start = pd.Timestamp(as_of), pd.Timestamp(cfg["start"])

    # PANGA: site coordinates and velocities, then every in-box site from the zip
    hv = A.fetch(A.PANGA_HVEL, raw / "panga" / "panga_nam20_hvel.xml", "panga", man, refresh=a.refresh)
    vv = A.fetch(A.PANGA_VVEL, raw / "panga" / "panga_nam20_vvel.xml", "panga", man, refresh=a.refresh)
    pv = A.parse_panga_velocities(hv, vv)
    pv = pv[(pv.lon >= w) & (pv.lon <= e) & (pv.lat >= s) & (pv.lat <= n)]
    zpath = A.fetch(
        A.PANGA_ZIP.format(proc="raw"),
        raw / "panga" / "panga_raw.zip",
        "panga",
        man,
        timeout=900,
        refresh=a.refresh,
    )
    series, steps, sites = [], [], []
    with zipfile.ZipFile(zpath) as zf:
        names = {m.split("/")[-1].split(".")[0].upper() for m in zf.namelist() if m.endswith(".lat")}
        for _, r in pv.iterrows():
            if r.site not in names:
                continue
            key = next(
                m
                for m in zf.namelist()
                if m.endswith(".lat") and m.split("/")[-1].split(".")[0].upper() == r.site
            )
            d, st = A.parse_panga_site(zf, key.split("/")[-1].split(".")[0], proc=key.split("/")[0])
            d["lon"], d["lat"] = r.lon, r.lat
            series.append(d)
            steps += [{"site": r.site, "decyear": x, "source": "panga dqrfit header"} for x in st]
            sites.append({"site": r.site, "lat": r.lat, "lon": r.lon, "archive": "panga"})
    log = logging.getLogger("s17")
    log.info("PANGA: %d sites in the network box", len(series))

    # UNR: sites PANGA lacks, plus a fixed set of shared sites (the longest PANGA series) for frame alignment
    hold = A.parse_unr_holdings(
        A.fetch(A.UNR_HOLDINGS, raw / "unr" / "DataHoldings.txt", "unr", man, refresh=a.refresh),
        cfg["network_bbox"],
    )
    have = {x["site"] for x in sites}
    lengths = sorted(((len(d), d.site.iloc[0]) for d in series), reverse=True)
    shared = [site for _, site in lengths if site in set(hold.site)][: a.unr_shared]
    want = [x for x in hold.site if x not in have] + shared
    stp = A.parse_unr_steps(A.fetch(A.UNR_STEPS, raw / "unr" / "steps.txt", "unr", man, refresh=a.refresh))
    for site in want:
        try:
            p = A.fetch(
                A.UNR_TENV3_NA.format(site=site),
                raw / "unr" / f"{site}.NA.tenv3",
                "unr",
                man,
                refresh=a.refresh,
            )
        except Exception as ex:  # a listed site without an NA-fixed file: skip, never fill
            log.warning("UNR %s: %s", site, ex)
            continue
        d = A.parse_unr_tenv3(p, frame="NA (UNR)")
        series.append(d)
        r = hold[hold.site == site].iloc[0]
        sites.append(
            {"site": site, "lat": r.lat, "lon": r.lon, "archive": "unr" if site not in have else "unr-shared"}
        )
        time.sleep(0.2)
    s1 = stp[stp.site.isin(want) & (stp.code == 1)]
    steps += [
        {"site": x.site, "decyear": x.decyear, "source": f"unr steps: {x.what}"} for x in s1.itertuples()
    ]
    log.info("UNR: %d series (%d shared with PANGA)", len(want), len(shared))

    daily = pd.concat(series, ignore_index=True)
    daily = daily[(daily.date >= start) & (daily.date <= as_of)]
    daily.to_parquet(out / "daily.parquet", index=False)
    st = pd.DataFrame(sites)
    span = daily.groupby(["site", "archive"]).date.agg(["min", "max", "count"])
    arch = st.archive.str.replace("-shared", "")
    for col, k in (("start", "min"), ("end", "max"), ("days", "count")):
        st[col] = [span[k].get((x, y)) for x, y in zip(st.site, arch, strict=True)]
    st.to_csv(out / "sites.csv", index=False)
    pd.DataFrame(steps).to_csv(out / "steps.csv", index=False)
    (out / "fetch.json").write_text(
        json.dumps(
            {
                "as_of": as_of.date().isoformat(),
                "last_day": daily.date.max().date().isoformat(),
                "run_utc": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
                "refresh": a.refresh,
            },
            indent=1,
        )
    )
    log.info(
        "wrote %s: %d site-days, %d series; manifest %s",
        out / "daily.parquet",
        len(daily),
        daily.groupby(["site", "archive"]).ngroups,
        man,
    )
    bad = A.verify_manifest(man)
    if bad:
        raise SystemExit(f"cached files differ from the manifest: {bad[:5]}")


if __name__ == "__main__":
    np.seterr(all="ignore")
    main()
