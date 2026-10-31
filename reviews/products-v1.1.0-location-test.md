# products-v1.1.0: request to test the model with earthquake locations

Sent to Sangwoo Han, for the test release
[products-v1.1.0](https://github.com/Denolle-Lab/mt-rainier-digital-model/releases/tag/products-v1.1.0). Results go
in a GitHub issue.

---

Hi Sangwoo,

The rebuilt Mount Rainier velocity model is out as a test release, `products-v1.1.0`:
https://github.com/Denolle-Lab/mt-rainier-digital-model/releases/tag/products-v1.1.0

Could you try it with your location work before we make a v2 release? Getting it:

```bash
pip install "git+https://github.com/Denolle-Lab/mt-rainier-digital-model"   # or clone and `pixi install`
rainier3d fetch grids       # NonLinLoc P/S grids, 500 m: grids/nll/rainier3d.{P,S}.mod.{hdr,buf}
rainier3d fetch model_let   # the model after our local-earthquake tomography
rainier3d export model --model ~/.cache/rainier3d/model_let/extracted/model_let.zarr \
    --format nll --dx 500 --dz 500 --out nll_let/rainier3d_let
```

## Which model is which

- **`grids`** holds the calibrated model (`model`). It comes ready to use.
- **`model_let`** is that model after our local-earthquake tomography. It differs by about ±5% in ln V.

## NonLinLoc setup

- Set `GTFILES` to `grids/nll/rainier3d`, with `TRANS NONE`.
- Stations and search grids use UTM 10N in km, with depth positive down.
- The grid is 140 × 150 × 49 cells of 500 m. Its corner is at 553.25 E, 5149.25 N (km), and depth runs from
  −4.25 km (4.25 km above sea level) to 19.75 km. Events deeper than about 20 km are off the grid.

## Our own numbers so far

- 88 PNSN events relocated: P / S RMS 0.132 / 0.268 s in the PNSN 1D model, 0.093 / 0.191 s in `model`.
- 2023–2025 catalogue: median RMS 0.119 s (1D) → 0.106 s (3D).
- Tomography, on held-out events: 0.090 → 0.072 s (P) and 0.180 → 0.121 s (S).

## What would help most

1. Your relocations in your usual 1D model, in `model` and in `model_let`, with the same picks. RMS, and how the
   depths and epicentres move.
2. Residuals by station, especially stations on the edifice: is there a pattern?
3. Events that end up above the ground or pile up at a depth. Before, rays ran flat at about −9.5 km where the
   regional models met; that should be gone now.
4. S picks and Vp/Vs. At 4–8 km below the ground beneath Rainier, our Vp/Vs is 0.06–0.07 lower than iMUSH.

## Known limits

- The cells are coarse (L1 250 m, L3 1 km).
- The top 300 m are the geology model alone, so the arrivals hardly constrain them.
- The full list is in the release notes (`reviews/products-v1.1.0-release-notes.md`).

Please send what you find as a GitHub issue or by email.

Thanks!
Marine
