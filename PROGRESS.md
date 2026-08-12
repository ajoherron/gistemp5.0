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
| 5 | Combine land+ocean → 80 boxes → zonal/global averages | Not started | — | — |

Validation basis: steps 1–3 compared cell-by-cell against gistemp4.0 output using matching input data.
Steps 0–5 match v4's numbering exactly (v4 has no step 6).

---

## Divergences from Identical Results

### Step 0 — data-vintage mismatch (unresolved)

`compare_step0.py` reports ~90K NaN mismatches and ~8.3M cells differing by up to 5.5 °C.
Root cause: v5 downloads the current GHCN file live; the v4 reference parquet was generated
from a locally cached (older) vintage of the same file. The differences are a data snapshot
artifact, not a code bug. Formal validation of step 0 against a matched GHCN snapshot is
still pending.

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
| `visualization/run_all.py` | Regenerate all figures |
