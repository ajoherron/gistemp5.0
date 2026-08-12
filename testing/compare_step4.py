"""
Compare gistemp5 step4 (ocean) output against gistemp4.0 SubboxReader.

Reads SBBX.ERSSTv5 via v4's SubboxReader (no pipeline re-run needed —
only the binary file is read).

Run from repo root:
    python main/run.py              # generates cache/step4_1880_2026.parquet
    python testing/compare_step4.py
"""

import argparse
import os
import subprocess
import sys

import numpy as np
import pandas as pd

REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4_DIR      = os.path.join(REPO_ROOT, '..', 'gistemp4.0')
V4_STEP4    = os.path.join(V4_DIR, 'tmp', 'step4_cache.parquet')
DUMP_SCRIPT = os.path.join(REPO_ROOT, 'testing', '_v4_sbbx_dump.py')

sys.path.insert(0, REPO_ROOT)

from parameters.constants import START_YEAR, END_YEAR
from utils import cache as step_cache

_META = {'lat_s', 'lat_n', 'lon_w', 'lon_e', 'n_stations', 'station_months', 'd'}


def run_v4_sbbx_dump(force: bool = False):
    """Run the SBBX-only dump (reads one binary file, ~seconds)."""
    sbbx_path = os.path.join(V4_DIR, 'tmp', 'input', 'SBBX.ERSSTv5')
    cache_ok  = (
        not force
        and os.path.exists(V4_STEP4)
        and os.path.getmtime(V4_STEP4) >= os.path.getmtime(sbbx_path)
    )
    if cache_ok:
        print("  Using cached gistemp4.0 step4 output.")
        return

    print("  Reading SBBX.ERSSTv5 via v4 SubboxReader…")
    result = subprocess.run(
        [sys.executable, DUMP_SCRIPT,
         str(START_YEAR), str(END_YEAR),
         os.path.join('tmp', 'step4_cache.parquet')],
        cwd=V4_DIR,
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        print("STDERR:\n", result.stderr[:2000])
        raise RuntimeError("v4 SBBX dump failed")
    for line in result.stdout.strip().splitlines():
        print(" ", line)


def time_cols(df):
    return [c for c in df.columns if c not in _META]


def compare(df4, df5):
    tc4 = set(time_cols(df4))
    tc5 = set(time_cols(df5))
    shared = sorted(tc4 & tc5, key=lambda c: (int(c.split('_')[1]), int(c.split('_')[0])))

    print(f"\n── Subbox counts ───────────────────────────────────────────")
    print(f"  gistemp4.0 : {len(df4):,} subboxes")
    print(f"  gistemp5   : {len(df5):,} subboxes")

    bounds_match = (
        np.allclose(df4['lat_s'].values, df5['lat_s'].values, atol=1e-6) and
        np.allclose(df4['lat_n'].values, df5['lat_n'].values, atol=1e-6) and
        np.allclose(df4['lon_w'].values, df5['lon_w'].values, atol=1e-6) and
        np.allclose(df4['lon_e'].values, df5['lon_e'].values, atol=1e-6)
    )
    print(f"  Subbox bounds match: {'✓' if bounds_match else '✗ MISMATCH'}")

    print(f"\n── Value comparison ({len(shared)} shared time columns) ─────────")
    a = df5[shared].astype(float).values
    b = df4[shared].astype(float).values

    nan_mismatch = int(np.sum(np.isnan(a) != np.isnan(b)))
    both_valid   = ~np.isnan(a) & ~np.isnan(b)
    abs_diff     = np.abs(a - b)

    n_cells  = int(both_valid.sum())
    n_differ = int((abs_diff[both_valid] > 1e-4).sum())

    print(f"  Cells with values in both   : {n_cells:,}")
    print(f"  NaN mismatches              : {nan_mismatch:,}")
    print(f"  Cells differing by > 1e-4°C : {n_differ:,}")

    if n_cells > 0:
        print(f"  Max  |diff|                 : {abs_diff[both_valid].max():.2e} °C")
        print(f"  Mean |diff|                 : {abs_diff[both_valid].mean():.2e} °C")

    ocean5 = int((~df5[time_cols(df5)].isna().all(axis=1)).sum())
    ocean4 = int((~df4[time_cols(df4)].isna().all(axis=1)).sum())
    print(f"\n── Ocean (non-empty) subboxes ──────────────────────────────")
    print(f"  gistemp4.0 : {ocean4:,}")
    print(f"  gistemp5   : {ocean5:,}")

    if n_differ == 0 and nan_mismatch == 0 and bounds_match:
        print("\n  ✓ Numerically equivalent")
    else:
        print("\n  ✗ Differences found — investigate above.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true')
    args = parser.parse_args()

    print("=== Step 4 comparison: gistemp5 vs gistemp4.0 ===\n")

    print("[1/3] Reading gistemp4.0 SBBX.ERSSTv5 via SubboxReader")
    run_v4_sbbx_dump(force=args.force)
    df4 = pd.read_parquet(V4_STEP4)
    print(f"  Loaded {len(df4):,} subboxes.")

    print("\n[2/3] Loading gistemp5 step4 cache")
    df5 = None if args.force else step_cache.load('step4', START_YEAR, END_YEAR)
    if df5 is None:
        print("  Cache missing — run: python main/run.py")
        sys.exit(1)
    print(f"  Loaded {len(df5):,} subboxes from cache.")

    print("\n[3/3] Comparing")
    compare(df4, df5)


if __name__ == '__main__':
    main()
