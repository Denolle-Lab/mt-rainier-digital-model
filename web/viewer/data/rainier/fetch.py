"""The only network code: GET with an on-disk cache, so builds rerun offline and never re-download."""
from __future__ import annotations

import urllib.request
from pathlib import Path


class FetchError(RuntimeError):
    pass


def get(url: str, cache_path: Path, opener=urllib.request.urlopen, timeout: int = 300, validate=None) -> bytes:
    """validate(body) → bool: a body that fails is neither returned nor cached (nor reused from the cache)."""
    cache_path = Path(cache_path)
    if cache_path.exists() and cache_path.stat().st_size:
        cached = cache_path.read_bytes()
        if validate is None or validate(cached):
            return cached
    req = urllib.request.Request(url, headers={"User-Agent": "rainier-seismic-atlas build (github.com/yaoderek/rainier-seismic-atlas)"})
    with opener(req, timeout=timeout) as resp:
        body = resp.read()
    if body[:1] == b"<":   # ArcGIS and FDSN services answer errors with an HTML page and status 200
        raise FetchError(f"{url} returned an HTML error page: {body[:200]!r}")
    if validate is not None and not validate(body):
        raise FetchError(f"{url} returned a response that failed validation ({len(body)} bytes)")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(body)
    return body
