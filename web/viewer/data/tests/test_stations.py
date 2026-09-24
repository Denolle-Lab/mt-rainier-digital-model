import pytest

from rainier import stations as S

HEAD = "#Network | Station | Location | Channel | Latitude | Longitude | Elevation | Depth | Azimuth | Dip | SensorDescription | Scale | ScaleFreq | ScaleUnits | SampleRate | StartTime | EndTime\n"


def ch(net, sta, cha, lat, lon, start, end="", rate=100.0, elev=853.0, depth=0.0):
    return f"{net}|{sta}||{cha}|{lat}|{lon}|{elev}|{depth}|0|0|sensor|1|1|m/s|{rate}|{start}T00:00:00.0000|{end}\n"


CHANNELS = HEAD + "".join([
    ch("UW", "LON", "HHZ", 46.750608, -121.809586, "2019-06-19"),
    ch("UW", "LON", "HHN", 46.750608, -121.809586, "2019-06-19"),
    ch("UW", "LON", "ENZ", 46.750608, -121.809586, "2019-06-19"),
    ch("UW", "LON", "VM1", 46.750608, -121.809586, "2019-06-19", rate=0.1),
    ch("UW", "LO2", "EHZ", 46.750608, -121.809586, "2009-01-28"),
    ch("UW", "LON9", "HAE", 46.750608, -121.809586, "2024-08-20"),
    ch("UW", "LON9", "HAN", 46.750608, -121.809586, "2024-08-20"),
    ch("CC", "PALI", "BHZ", 47.07748, -121.71046, "2025-09-17"),
    ch("C0", "PALI", "BHZ", 47.07748, -121.71046, "2025-09-17"),
    ch("SY", "FAKE", "BHZ", 46.8, -121.7, "2020-01-01"),
    ch("UW", "RCM", "HHZ", 46.83557, -121.73317, "2024-09-09"),
    ch("UW", "OLD", "HHZ", 46.84, -121.74, "2001-01-01", end="2010-01-01T00:00:00.0000"),
    ch("UW", "FAR", "HHZ", 46.95, -122.30, "2020-01-01"),
    ch("UW", "SOH", "VM1", 46.86, -121.76, "2020-01-01"),   # only state-of-health channels open
])
STA_HEAD = "#Network | Station | Latitude | Longitude | Elevation | SiteName | StartTime | EndTime\n"
SITES = STA_HEAD + "".join(f"{n}|{s}|0|0|0|{name}|2000-01-01T00:00:00|\n" for n, s, name in [
    ("UW", "LON", "Longmire, WA, USA"), ("UW", "LO2", "Longmire, WA"), ("UW", "LON9", "Longmire tilt vault"),
    ("CC", "PALI", "Palisades"), ("UW", "RCM", "Camp Muir, Mount Rainier, WA, USA"), ("UW", "FAR", "Faraway, WA, USA")])


def build():
    def get(url, path):
        return (SITES if "level=station" in url else CHANNELS).encode()
    return S.build_stations("unused", get=get, as_of="2026-09-23", majors={"UW.LON": "Longmire, broadband"})


def test_kind_of_maps_instruments_and_ignores_state_of_health():
    assert S.kind_of("HHZ") == ("seismometer", "broadband")
    assert S.kind_of("EHZ") == ("seismometer", "short period")
    assert S.kind_of("ELZ") == ("seismometer", "short period")
    assert S.kind_of("BDF") == ("infrasound", None)
    assert S.kind_of("VM1") is None and S.kind_of("LNZ") is None
    with pytest.raises(KeyError):
        S.kind_of("XYZ")


def test_colocated_codes_merge_into_one_named_site():
    out = build()
    lon = next(s for s in out["sites"] if "UW.LON" in s["codes"])
    assert lon["id"] == "UW.LON" and lon["name"] == "Longmire"   # the major code names the site
    assert sorted(lon["codes"]) == ["UW.LO2", "UW.LON", "UW.LON9"]
    assert lon["kinds"] == ["seismometer", "accelerometer", "tiltmeter"]   # KINDS order
    assert lon["major"] == "Longmire, broadband" and lon["since"] == "2009-01-28"
    st = next(x for x in lon["stations"] if x["code"] == "UW.LON")
    assert st["instruments"][0] == {"kind": "seismometer", "band": "broadband", "channels": ["HHN", "HHZ"], "rate": 100.0}
    assert st["operator"] == "Pacific Northwest Seismic Network"


def test_exclusions_and_closed_channels():
    out = build()
    codes = [c for s in out["sites"] for c in s["codes"]]
    assert "C0.PALI" not in codes and "SY.FAKE" not in codes and "UW.OLD" not in codes
    assert {e["code"] for e in out["excluded"]} >= {"C0.PALI", "SY.*"}
    assert codes.count("CC.PALI") == 1


def test_site_names_drop_state_and_mountain_suffixes():
    assert S.clean_name("Camp Muir, Mount Rainier, WA, USA") == "Camp Muir"
    assert S.clean_name("Mt. Rainier, Camp Schurman, WA, USA") == "Camp Schurman"
    assert S.clean_name("St. Andrews Rock, Mt. Rainier, WA") == "St. Andrews Rock"
    assert S.clean_name("Paradise Precip Tower") == "Paradise Precip Tower"


def test_on_map_and_counts():
    out = build()
    far = next(s for s in out["sites"] if s["id"] == "UW.FAR")
    assert far["onMap"] is False
    assert out["counts"] == {"returned": 9, "excluded": 3, "stations": 6, "sites": 4, "sitesOnMap": 3, "stationsOnMap": 5}


def test_a_station_with_only_state_of_health_channels_is_recorded_not_lost():
    out = build()
    assert {"code": "UW.SOH", "reason": "only state-of-health channels are open"} in out["excluded"]
    c = out["counts"]
    assert c["returned"] - c["excluded"] == c["stations"]
