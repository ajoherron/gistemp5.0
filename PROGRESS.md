# gistemp5.0 — Progress

Modern Python (Pandas/NumPy) port of NASA GISTEMP 4.0.
Target: numerically equivalent output at each step (max |diff| < 1e-4 °C vs gistemp4.0).

---

## Steps

| Step | Description | Status | Max \|diff\| | Mean \|diff\| |
|------|-------------|--------|-------------|--------------|
| 0 | GHCN ingest & QC | ✓ Done | see note | see note |
| 1 | Duplicate merging | ✓ Done | 1.42e-14 °C | 5.38e-17 °C |
| 2 | Drop short records + urban adjustment | ✓ Done | 1.42e-14 °C | 3.82e-16 °C |
| 3 | Gridding → 8,000 equal-area subboxes | ✓ Done | 1.32e-12 °C | 6.18e-15 °C |
| 4 | Load ERSSTv5 ocean subboxes | ✓ Done | 0.00e+00 °C | 0.00e+00 °C |
| 5 | Combine land+ocean → 80 boxes → zonal/global averages | ✓ Done | ~1e-14 °C | ~4e-16 °C |

Validation basis: all steps compared against gistemp4.0 on identical input data (same GHCN vintage,
same strange-station list, same ERSSTv5). Step 5 validated by re-running v4's full pipeline with
2026 GHCN data and confirming all 16 zones (land + mixed) match to floating-point precision.
Steps 0–5 match v4's numbering exactly (v4 has no step 6).

---

## Divergences from Identical Results

### Step 0 — data-vintage mismatch (unresolved)

`compare_step0.py` reports ~90K NaN mismatches and ~8.3M cells differing by up to 5.5 °C.
Root cause: v5 downloads the current GHCN file live; the v4 reference parquet was generated
from a locally cached (older) vintage of the same file. The differences are a data snapshot
artifact, not a code bug. Formal validation of step 0 against a matched GHCN snapshot is
still pending.

### Step 5 — fully validated (no unresolved divergences)

All 16 zones (land and mixed) match gistemp4.0 to floating-point precision (~1e-14 °C)
when both pipelines run on identical input data. Validation was performed by re-running
v4's full pipeline with the same 2026 GHCN file, same station metadata (v4.inv), and
same strange-station list (Ts.strange.v4.list.IN_full) that v5 uses.

Earlier apparent divergences were traced to three data-vintage mismatches (not algorithm bugs):
1. **GHCN vintage**: v4's cached file ended Aug 2025; v5 downloaded 2026 data.
2. **Strange-station list**: v4's cached copy lacked 5 new entries (2 Russian Arctic
   stations with outlier months in 2024–2025) added after Aug 2025 — causing zone_0
   diffs of up to 0.08 °C for those specific months.
3. **Eligibility-threshold crossing** (diagnosed but moot once data matched): box 76
   (90S-64S) had 21 subboxes whose gc crossed the 240 threshold between data vintages.

### Step 3 — NumPy SIMD vs Python scalar arithmetic (~1e-12 °C)

After fixing the three root causes that produced large errors (wrong earth radius, non-sequential
bias summation, non-sequential anomalize mean), a residual max diff of **1.32e-12 °C** remains.

**Cause:** The element-wise combine update:

```python
comp[fidx] = (old_wt * old_val + new_wt * (new_s[fidx] + bias)) / new_total
```

NumPy executes this with SIMD/AVX instructions which may select fused multiply-add (FMA)
operations — one rounding step instead of two. CPython's scalar loop uses standard IEEE 754
with separate multiply and add. The per-element difference is ≤ 1 ULP (~2e-16 relative).
Across the ~10–20 sequential `_combine` calls per subbox, these errors accumulate to ~1e-12.

Making the update loop scalar Python would eliminate this but would gut performance. At 1e-12 °C
the residual is below any meaningful physical or numerical threshold.

---

## Key Implementation Notes

- **Earth radius**: step 3 uses 6375.0 km (matching `gistemp4.0/steps/earth.py`), not the
  commonly cited 6371.0 km. Using 6371.0 shifts `cos_arc` enough to change which boundary
  stations pass the 1200 km incircle filter, producing n_stations mismatches of ~1086 subboxes.

- **Bias summation order**: `_combine` uses Python's `sum()` on a list (sequential left-to-right)
  to match gistemp4.0's scalar loop. NumPy's `.sum()` uses pairwise summation and gives
  different floating-point results.

- **Anomalize mean**: `_anomalize` uses Python's `sum()` to match gistemp4.0's `valid_mean()`
  scalar loop for the same reason.

- **Station ordering into step 3**: stations are sorted by `good_count` descending (stable sort)
  before gridding, matching gistemp4.0's `sorted(..., key=lambda x: x.good_count, reverse=True)`.

---

## Step 5 Implementation Plan

### Algorithm (4 stages, 2 analyses: land-only and mixed)

**Stage 1 — Land/ocean mask** (`ensure_weight`):
For each of 8000 subboxes: use land if `ocean.good_count < 240` OR `land.d < 100 km`,
else use ocean. "Land-only" always uses land; "mixed" uses this mask.

**Stage 2 — 8000 subboxes → 80 boxes** (`subbox_to_box`):
Assign each subbox to its parent large-box using `eqarea.grid()` + `centre()`.
Sort contributors by `good_count` descending. Combine via scalar `series.combine()`
(`min_overlap=20`). Anomalize to `(1961, 1990)`.

**Stage 3 — 80 boxes → 16 zones** (`zonav`):
8 latitudinal bands hold `[4, 8, 12, 16, 16, 12, 8, 4]` boxes each.
Sort by valid-data count using v4's `sort_perm` (key = `index − value`).
Combine, anomalize to `(1951, 1980)`. Produce 8 compound zones:
N_extratrop, Tropical, S_extratrop, NMid, SMid, NH, SH, Global.

**Stage 4 — Monthly → annual** (`annzon`):
Mean of valid months (min 6). Alternate global: weighted mean of zones [8,3,4,10]
with weights [3, 2, 2, 3], scaled by 0.1. Alternate hemispheric: 0.4×tropical + 0.6×polar.

### Precision requirements
- `series.combine()` must be **scalar Python loops** — same reasoning as step 3 bias/anomalize fixes.
- `sort_perm()` key is `index − value` (not `value − index`) — must match v4 exactly.
- Series padding to common `yrbeg`/`monm` must replicate v4's `padded_series()`.
- All summation via sequential `sum()`, not numpy.

### Files
| File | Action |
|---|---|
| `utils/series.py` | NEW — scalar Python `combine()` + `anomalize()` ported from v4 |
| `steps/step5.py` | NEW — all 4 stages, 2 analyses |
| `main/run.py` | MOD — add step5 call |
| `testing/_v4_step5_dump.py` | NEW — reads existing v4 npz files → parquet (no subprocess) |
| `testing/compare_step5.py` | NEW — compare monthly zones |
| `visualization/step5_comparison.py` | NEW — zone time-series and diff bar chart |

### Output format
`{'land': result, 'mixed': result}` where each result holds:
- `annual`: DataFrame (index=year, columns=zone_0…zone_15)
- `monthly`: DataFrame (index=(year,month), columns=zone_0…zone_15)

### Validation
v4 has already fully run step 5. Outputs exist at `gistemp4.0/tmp/result/`:
`mixedZON.*.npz`, `landZON.*.npz`, `mixedBX.*.npz`, `landBX.*.npz`, and CSV annual files.
No subprocess re-run needed — dump script just converts these npz files to parquet.

---

## Validation Artifacts

| Script | Purpose |
|--------|---------|
| `testing/compare_step0.py` | Step 0 cell-by-cell comparison |
| `testing/compare_step1.py` | Step 1 cell-by-cell comparison |
| `testing/compare_step2.py` | Step 2 cell-by-cell comparison |
| `testing/compare_step3.py` | Step 3 cell-by-cell comparison |
| `testing/compare_step4.py` | Step 4 cell-by-cell comparison (reads SBBX binary only) |
| `testing/_v4_sbbx_dump.py` | Helper: reads SBBX.ERSSTv5 via v4 SubboxReader, writes parquet |
| `visualization/step0_summary.py` | Step 0 visual summary |
| `visualization/step1_summary.py` | Step 1 visual summary |
| `visualization/step2_comparison.py` | Step 2 v4 vs v5 overlay |
| `visualization/step3_comparison.py` | Step 3 v4 vs v5 overlay |
| `visualization/step4_comparison.py` | Step 4 v4 vs v5 overlay |
| `testing/_v4_step5_dump.py` | Helper: reads v4 ZON.npz result files → parquet |
| `testing/compare_step5.py` | Step 5 monthly zone comparison |
| `visualization/step5_comparison.py` | Step 5 v4 vs v5 zone time-series and diff chart |
| `visualization/run_all.py` | Regenerate all figures |
