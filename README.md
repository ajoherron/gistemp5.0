# gistemp5.0

A modern Python port of [NASA GISTEMP 4.0](https://data.giss.nasa.gov/gistemp/) — the surface temperature analysis that produces the canonical global mean temperature record used in climate science and IPCC reports.

## Quick Start

Requires Python 3.11+. Run these commands once to get up and running:

```bash
pip install uv                             # install the package manager (one-time)
git clone https://github.com/ajoherron/gistemp5.0
cd gistemp5.0
make install                               # install dependencies
make run                                   # run the full pipeline (~6 min, downloads data on first run)
```

Results land in `cache/` as Parquet files. The global mean temperature anomaly (1880–present) is `zone_15` in `cache/step5_mixed_annual_1880_2026.parquet`. See [Output](#output) for details.

```python
import pandas as pd
df = pd.read_parquet("cache/step5_mixed_annual_1880_2026.parquet")
print(df["zone_15"])  # global mean temperature anomaly by year
```

Run `make help` to see all available commands.

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

## Validation

Every step is compared against v4 output using scripts in `testing/`. Validation runs v4's full pipeline with the same 2026 GHCN file, same station metadata, and same strange-station list, then diffs the outputs cell by cell.

| Step | Max \|diff\| | Result |
|------|-------------|--------|
| 0 | 0 | ✓ Identical |
| 1 | 1.4e-14 °C | ✓ Floating-point noise |
| 2 | 1.4e-14 °C | ✓ Floating-point noise |
| 3 | 1.3e-12 °C | ✓ SIMD/FMA accumulation |
| 4 | 0 | ✓ Identical |
| 5 | ~1e-14 °C | ✓ Floating-point noise |

## Repository Structure

```
steps/          # One module per pipeline step (step0.py … step5.py)
utils/          # Shared utilities: cache, config, eqarea grid, series combine/anomalize, SBBX reader
main/run.py     # Pipeline entry point
testing/        # Cell-by-cell comparison scripts vs gistemp4.0
visualization/  # Matplotlib comparison figures for each step (PNGs saved here)
input/          # Downloaded input files — GHCN, SBBX, etc. (git-ignored, auto-populated)
cache/          # Parquet cache of step outputs (git-ignored)
```

## Running

```bash
make run           # run the pipeline (uses cached steps when available)
make run-fresh     # re-run all steps from scratch
make viz           # generate comparison figures (requires make run first)
make compare       # validate all steps against gistemp4.0
make help          # list all available commands
```

## Output

Running `make run` produces the following files in `cache/` (all git-ignored):

**Final results** — temperature anomalies in °C relative to the 1951–1980 baseline:

| File | Rows | Columns |
|------|------|---------|
| `step5_mixed_annual_1880_2026.parquet` | 1 per year (1880–2026) | 16 zones |
| `step5_mixed_monthly_1880_2026.parquet` | 1 per month | 16 zones |
| `step5_land_annual_1880_2026.parquet` | 1 per year | 16 zones (land only) |
| `step5_land_monthly_1880_2026.parquet` | 1 per month | 16 zones (land only) |

The 16 zones (`zone_0` … `zone_15`) correspond to:

| Columns | Zones |
|---------|-------|
| 0–7 | Latitude bands: 64N–90N, 44N–64N, 24N–44N, EQU–24N, 24S–EQU, 44S–24S, 64S–44S, 90S–64S |
| 8–10 | N-Extratropical, Tropical, S-Extratropical |
| 11–12 | N-Midlatitude, S-Midlatitude |
| 13–15 | Northern Hemisphere, Southern Hemisphere, **Global** |

The `mixed` files combine land and ocean data; `land` files use land stations only. The global mean anomaly is `zone_15` in the `mixed` files.

**Intermediate outputs** — one Parquet file per step (`step0` through `step4`) for fast re-runs.

To read results in Python:

```python
import pandas as pd
df = pd.read_parquet("cache/step5_mixed_annual_1880_2026.parquet")
print(df["zone_15"])  # global mean temperature anomaly, 1880–present
```

## Visualization

```bash
make viz
```

Generates one PNG per step and saves them to `visualization/`. Each figure overlays gistemp5 output against the gistemp4.0 reference:

| File | What it shows |
|------|--------------|
| `step0_summary.png` | Station count and coverage: v5 vs v4 |
| `step1_summary.png` | Effect of the strange-station exclusion list |
| `step2_comparison.png` | Urban heat-island adjusted anomalies: v5 vs v4 |
| `step3_comparison.png` | Equal-area subbox gridded anomalies: v5 vs v4 |
| `step4_comparison.png` | ERSSTv5 ocean subbox anomalies: v5 vs v4 |
| `step5_comparison.png` | Final zonal and global temperature anomalies: v5 vs v4 |

`make viz` requires that `make run` has been run first (step outputs must be cached).

## Data Sources

| Dataset | Source |
|---------|--------|
| GHCN-Monthly v4 (QC'd) | NOAA / NASA GISS |
| Station metadata (v4.inv) | NASA GISS |
| Strange-station exclusion list | NASA GISS |
| ERSSTv5 ocean temperatures | NOAA (pre-gridded SBBX binary) |
| Brightness grid (urban classification) | NASA GISS |

All inputs are downloaded automatically on first run and cached locally.
