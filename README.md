# gistemp5.0

A modern Python port of [NASA GISTEMP 4.0](https://data.giss.nasa.gov/gistemp/) — the surface temperature analysis that produces the canonical global mean temperature record used in climate science and IPCC reports.

## Motivation

GISTEMP 4.0 is written in legacy CPython: scalar loops, custom array objects, fixed-width text files, and no use of pandas or numpy. It works, but it is hard to read, hard to modify, and slower than it needs to be.

This project re-implements the full GISTEMP 4.0 pipeline in modern Python (pandas, numpy) with three goals:

1. **Numerical equivalence** — every step produces output that matches v4 to floating-point precision on identical input data
2. **Speed** — vectorised operations where possible; ~2× faster end-to-end
3. **Readability** — each step is a single, self-contained module with clear data flow

## Algorithm Overview

GISTEMP turns raw weather-station records into a global surface temperature anomaly through six steps:

| Step | What it does |
|------|-------------|
| 0 | Download and parse GHCN-Monthly temperature records; apply quality flags |
| 1 | Merge duplicate stations; apply the strange-station exclusion list |
| 2 | Drop short records; apply urban heat-island adjustment using rural neighbours |
| 3 | Grid 23 K stations onto 8,000 equal-area subboxes; combine overlapping records |
| 4 | Load ERSSTv5 ocean temperature subboxes (pre-gridded by NOAA) |
| 5 | Merge land and ocean subboxes; average up to 80 large boxes → 16 zones → global mean |

The final output is a monthly and annual time series for 16 zones (8 latitude bands, plus hemispheric and global composites) from 1880 to the present.

## Improvements over v4

### Vectorisation
Steps 0–2 and 4 are fully vectorised using pandas and numpy. The wide-format station DataFrame (`stations × time columns`) lets pandas handle filtering, merging, and anomaly computation in bulk rather than station-by-station loops.

### Step 2 performance fix
The urban heat-island adjustment in v4 processes ~9,000 urban stations one at a time. The v5 port initially had a correctness-preserving but catastrophically slow reconstruction step (22,526 individual `DataFrame.loc` lookups + `pd.concat` of 22,526 single-row frames — 696 s). Replacing this with a bulk `drop` + `loc` assignment reduced step 2 from **696 s → 50 s** (14×).

### Intentional scalar loops (steps 3 and 5)
The `combine` and `anomalize` routines in steps 3 and 5 use Python's sequential `sum()` rather than `numpy.sum()`. This is deliberate: numpy uses pairwise summation which accumulates floating-point error differently, producing differences of ~1e-12 °C relative to v4. The scalar loops preserve exact agreement. This is the main remaining performance opportunity — relaxing the constraint would be physically inconsequential and would likely bring step 3 from ~140 s to single digits.

### Modern data formats
- All intermediate outputs cached as Parquet (fast columnar I/O, ~10× smaller than CSV)
- Downloads validated against live GHCN data on every run
- Per-step cache means a re-run skips already-computed steps

## Performance

Both pipelines timed from a fully cold start (all inputs downloaded fresh):

| | v4 | v5 | Speedup |
|---|---|---|---|
| Wall time | ~12m 15s | ~6m 0s | **~2×** |
| CPU time | ~494 s | ~249 s | **~2×** |

Per-step breakdown (inputs already on disk):

| Step | Time | Bottleneck |
|------|------|-----------|
| 0 | 93 s | GHCN parse (~170 MB flat file) |
| 1 | 0.5 s | — |
| 2 | 50 s | UHI rural-neighbour search |
| 3 | 140 s | scalar combine/anomalize loops |
| 4 | 1.5 s | — |
| 5 | 11 s | scalar combine/anomalize |

## Validation

Every step is compared against v4 output using scripts in `testing/`. Validation runs v4's full pipeline with the same 2026 GHCN file, same station metadata, and same strange-station list, then diffs the outputs cell by cell.

| Step | Max \|diff\| | Result |
|------|-------------|--------|
| 0 | 0 | ✓ Identical |
| 1 | 1.4e-14 °C | ✓ Floating-point noise |
| 2 | 1.4e-14 °C | ✓ Floating-point noise |
| 3 | 1.3e-12 °C | ✓ SIMD/FMA accumulation (see PROGRESS.md) |
| 4 | 0 | ✓ Identical |
| 5 | ~1e-14 °C | ✓ Floating-point noise |

## Repository Structure

```
steps/          # One module per pipeline step (step0.py … step5.py)
utils/          # Shared utilities: cache, eqarea grid, series combine/anomalize, SBBX reader
parameters/     # Constants and data source URLs
main/run.py     # Pipeline entry point
testing/        # Cell-by-cell comparison scripts vs gistemp4.0
visualization/  # Matplotlib comparison figures for each step
cache/          # Parquet cache of step outputs (git-ignored)
```

## Running

```bash
# Install dependencies
uv sync   # or: pip install -e .

# Run the full pipeline (downloads inputs on first run, ~6 min)
python main/run.py

# Skip already-computed steps
python main/run.py          # uses cache by default
python main/run.py --no-cache   # force re-run all steps

# Regenerate all comparison figures
python visualization/run_all.py

# Validate against gistemp4.0 (requires ../gistemp4.0 to exist and have been run)
python testing/compare_step2.py
python testing/compare_step5.py
```

## Data Sources

| Dataset | Source |
|---------|--------|
| GHCN-Monthly v4 (QC'd) | NOAA / NASA GISS |
| Station metadata (v4.inv) | NASA GISS |
| Strange-station exclusion list | NASA GISS |
| ERSSTv5 ocean temperatures | NOAA (pre-gridded SBBX binary) |
| Brightness grid (urban classification) | NASA GISS |

All inputs are downloaded automatically on first run and cached locally.
