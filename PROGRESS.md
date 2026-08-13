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

## Performance

| | v4 (cold start) | v5 (cold start) | v5 speedup |
|---|---|---|---|
| Wall time | ~12m 15s | ~6m 0s | **~2×** |
| CPU time | ~494s | ~249s | **~2×** |

Cold start includes all downloads (GHCN ~170 MB, v4.inv, strange-station list, ERSSTv5, brightness grid).

Per-step breakdown (inputs cached, no downloads):

| Step | v5 time | Notes |
|------|---------|-------|
| 0 | ~93s | GHCN parse + QC (~170 MB) |
| 1 | ~0.5s | vectorised pandas |
| 2 | ~50s | UHI algorithm; reconstruction fixed (was 696s due to per-row concat loop) |
| 3 | ~140s | scalar loops preserved for floating-point match; main remaining opportunity |
| 4 | ~1.5s | binary SBBX parse |
| 5 | ~11s | scalar combine/anomalize |

---

## Divergences from Identical Results

### All steps — fully validated on identical inputs

All 6 steps produce numerically equivalent output when both pipelines run on the same
input data (same GHCN vintage, same v4.inv, same strange-station list, same ERSSTv5).
Validation was performed by re-running v4's full pipeline with 2026 GHCN data and
confirming all outputs match to floating-point precision.

Earlier apparent divergences in `compare_step0.py` (~8 M cells differing by up to 5.5 °C)
were a data-vintage artifact: the v4 reference parquet had been cached from an older GHCN
snapshot (Aug 2025) while v5 downloaded the current 2026 file. On identical inputs, step 0
outputs are identical (✓ Outputs are IDENTICAL).

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

## Remaining Optimisation Opportunities

### 1. Step 3 — vectorise `combine` / `anomalize` (highest impact)

`steps/step3.py` and `utils/series.py` use scalar Python `sum()` loops to match v4's
sequential floating-point accumulation. Replacing these with numpy would cut step 3 from
~140 s to single digits. Cost: max diff moves from ~1e-12 °C to ~1e-10 °C — still far below
any physical or numerical threshold.

### 2. Step 2 — vectorise UHI rural-neighbour search

The urban heat-island core (`_rural_difference`, `_getfit`, `_cmbine`) runs ~9,000 scalar
Python loops over ~147 years of annual anomalies. `_getfit` is O(n²) per station. Step 2
currently takes ~50 s; vectorising the inner loops could bring this close to zero.

### 3. Step 0 — GHCN flat-file parse

~93 s to parse the ~170 MB GHCN fixed-width file. Most of this is I/O + string parsing.
Pandas `read_fwf` with explicit dtypes, or chunked reading, may help materially.

### 4. Step 2 — own input directory

`steps/step2.py` downloads `wrld-rad.data.txt` and reads `v4.inv` from
`../gistemp4.0/tmp/input/`, relying on the v4 sibling repo being present.
v5 should manage its own input cache directory.

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
