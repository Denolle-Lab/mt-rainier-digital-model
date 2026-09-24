# Eikonal solver benchmark

**Result.** pykonal's `PointSourceSolver` is the most accurate of the CPU solvers tested. At the S6 grid spacing of 0.5 km, its error is 2–3 times smaller than fteikpy's and it runs 1.2–1.3 times slower. S6 now uses it by default (`pixi run s6 -- --solver fteikpy` restores the previous solver). scikit-fmm is the fastest, about twice as fast as the others. Seeded the way denopick's CPU path seeds it, however, it biases every travel time early, and it biases S−P times as well.

- **Script:** `scripts/bench_eikonal.py` (`pixi run python scripts/bench_eikonal.py 0.5`).
- **Run:** 24 September 2026 on an Apple M-series laptop, using pykonal 0.4.1, fteikpy 2.4, and scikit-fmm under Python 3.12.
- **Timing:** each time is the wall time of one solve for one source, measured on a second call after a warm-up call (so fteikpy's numba compilation is excluded).

## Set-up

| | |
|---|---|
| Grid | 70 × 75 × 24 km, the size of the S6 grid; spacing *dx* = 0.5 km (1.04 M nodes) and 0.25 km (8.3 M nodes) |
| Source | Off-grid, at (41.37, 36.52, 11.23) km |
| Receivers | 300 random points inside the box and 60 at the surface |
| Reference | Analytic travel times: *r*/*v* for the homogeneous case; for *v*(*z*) = *v*₀ + *g z*, *T* = arccosh(1 + *g*² *r*² / (2 *v*ₛ *v*ᵣ)) / *g* |
| Error | Solver time minus analytic time, sampled at the receivers by trilinear interpolation (fteikpy uses its own interpolator) |

## Results at dx = 0.5 km

Errors are in ms. "Event-demeaned RMS" removes the mean error over the receivers; it is what remains after the origin time absorbs a common offset.

**Homogeneous, 6 km/s:**

| Solver | Time (s) | Mean | RMS | Max \|e\| | Event-demeaned RMS |
|---|---|---|---|---|---|
| fteikpy, 2nd-order fast sweeping | 0.95 | +19.1 | 21.7 | 48.5 | 10.5 |
| pykonal fast marching, seeded ball | 0.83 | +38.5 | 43.5 | 66.1 | 20.2 |
| **pykonal PointSourceSolver** | 1.17 | −6.7 | **8.1** | 20.4 | **4.6** |
| scikit-fmm, denopick CPU seeding | 0.45 | −53.4 | 54.3 | 90.3 | 9.7 |
| scikit-fmm, sphere time added back | 0.45 | +30.8 | 32.2 | 46.6 | 9.7 |

**Gradient, 4 + 0.1 z km/s:**

| Solver | Time (s) | Mean | RMS | Max \|e\| | Event-demeaned RMS |
|---|---|---|---|---|---|
| fteikpy | 0.89 | +43.6 | 46.0 | 93.5 | 14.8 |
| pykonal fast marching, seeded ball | 0.84 | +39.1 | 46.0 | 73.8 | 24.2 |
| **pykonal PointSourceSolver** | 1.15 | −8.9 | **10.5** | 30.8 | **5.5** |
| scikit-fmm, denopick CPU seeding | 0.48 | −66.2 | 67.2 | 105.8 | 11.5 |
| scikit-fmm, sphere time added back | 0.45 | +32.4 | 34.4 | 55.1 | 11.5 |

## Results at dx = 0.25 km

Halving the spacing multiplies the node count by 8. The cost grows about ninefold for every solver, and the errors roughly halve. The ranking does not change: pykonal PointSourceSolver has an RMS of 4.7 ms (homogeneous) and 5.7 ms (gradient), against 9.0 and 21.2 ms for fteikpy. Each of these solves takes 8.3–10.7 s (4.6–5.1 s for scikit-fmm).

## denopick_dasbb_2026

arose1234/denopick_dasbb_2026 is a private repository with no licence, read at commit `656ee3f`. It has two eikonal back ends.

- **`dasbb/forward.py` (CPU).** It calls scikit-fmm with the zero level set on a sphere of radius 1.01·*dx* around the source. It does not add the travel time from the source to that sphere. Every time is therefore early by about 1.01·*dx*/*v* at the source. A single phase absorbs this into the origin time; S−P does not.

  | *dx* | Measured S−P bias (Vp = 6 km/s, Vp/Vs = √3) |
  |---|---|
  | 0.5 km | −39 ms |
  | 0.25 km | −23 ms |

  The bias scales roughly with *dx*. Extrapolated linearly, it would be about −0.3 s at the 4 km spacing mentioned in the repository's documentation; this was not run. The fix is to add the source-to-sphere time (the "sphere time added back" rows), or to seed analytic times as the GPU path does.
- **`dasbb/forward_eiko.py` (GPU).** CUDA fast sweeping through `eiko3d`, with analytic times seeded inside the 1.01·*dx* ball. That seeding is correct. It could not be timed here, because it needs an NVIDIA GPU.

Its speed comes from running on the GPU and from caching travel-time fields between iterations of its inversion (least-recently-used cache, 16 fields). Both ideas could be added to S6/S12 if calibration runs grow. At the 1 M-node size here, one CPU solve takes about 1 s per source.
