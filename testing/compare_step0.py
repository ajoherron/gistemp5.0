"""
Compare gistemp5 step0 output against gistemp4.0 step0.

Downloads input data if not already present in gistemp4.0/tmp/input/,
then runs both parsers and reports any differences.

Run from repo root:
    python testing/compare_step0.py
"""

import os
import subprocess
import sys
import urllib.request

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4_DIR    = os.path.join(REPO_ROOT, '..', 'gistemp4.0')
V4_INPUT  = os.path.join(V4_DIR, 'tmp', 'input')
V4_CACHE  = os.path.join(V4_DIR, 'tmp', 'step0_cache.parquet')
DUMP_SCRIPT = os.path.join(REPO_ROOT, 'testing', '_v4_dump.py')

sys.path.insert(0, REPO_ROOT)

from parameters.constants import START_YEAR, END_YEAR
from parameters.data import GHCN_TEMP_URL, GHCN_META_URL
from steps.step0 import step0

INPUT_FILES = {
    'ghcnm.tavg.qcf.dat': GHCN_TEMP_URL,
    'v4.inv': GHCN_META_URL,
}


# ── helpers ──────────────────────────────────────────────────────────────────

def fetch_v4_inputs():
    os.makedirs(V4_INPUT, exist_ok=True)
    for name, url in INPUT_FILES.items():
        path = os.path.join(V4_INPUT, name)
        if not os.path.exists(path):
            print(f"  Downloading {name} …")
            urllib.request.urlretrieve(url, path)
        else:
            print(f"  {name} already present.")


def run_v4_step0(force: bool = False) -> pd.DataFrame:
    """Run gistemp4.0's step0 and return a DataFrame, using a parquet cache."""
    dat_mtime = os.path.getmtime(os.path.join(V4_INPUT, 'ghcnm.tavg.qcf.dat'))
    cache_fresh = (
        not force
        and os.path.exists(V4_CACHE)
        and os.path.getmtime(V4_CACHE) >= dat_mtime
    )

    if cache_fresh:
        print("  Loading cached gistemp4.0 step0 output …")
        return pd.read_parquet(V4_CACHE)

    print("  Running gistemp4.0 step0 (this takes a few minutes) …")
    result = subprocess.run(
        [sys.executable, DUMP_SCRIPT, str(START_YEAR), str(END_YEAR), V4_CACHE],
        cwd=V4_DIR,
        capture_output=True,
        text=True,
        timeout=600,
    )
    if result.returncode != 0:
        print("STDERR from v4 dump:\n", result.stderr[:2000])
        raise RuntimeError("gistemp4.0 step0 dump failed")

    print(f"  Cached to {V4_CACHE}")
    return pd.read_parquet(V4_CACHE)


def time_cols(df: pd.DataFrame):
    return [c for c in df.columns if c not in ('Latitude', 'Longitude')]


# ── comparison ───────────────────────────────────────────────────────────────

def compare(df5: pd.DataFrame, df4: pd.DataFrame):
    tc5 = set(time_cols(df5))
    tc4 = set(time_cols(df4))
    shared_cols = sorted(tc5 & tc4, key=lambda c: int(c.split('_')[1]))

    stations5 = set(df5.index)
    stations4 = set(df4.index)
    shared_stations = stations5 & stations4

    print("\n── Station counts ──────────────────────────────────────────")
    print(f"  gistemp5  : {len(stations5):>6,} stations")
    print(f"  gistemp4.0: {len(stations4):>6,} stations")
    print(f"  Shared    : {len(shared_stations):>6,} stations")

    only_in_5 = stations5 - stations4
    only_in_4 = stations4 - stations5
    print(f"\n  Only in gistemp5  : {len(only_in_5):,}")
    print(f"  Only in gistemp4.0: {len(only_in_4):,}")
    if only_in_5 and len(only_in_5) <= 10:
        print("    ", sorted(only_in_5))
    if only_in_4 and len(only_in_4) <= 10:
        print("    ", sorted(only_in_4))

    print("\n── Column (time) coverage ──────────────────────────────────")
    print(f"  gistemp5   columns: {len(tc5):,}")
    print(f"  gistemp4.0 columns: {len(tc4):,}")
    print(f"  Shared             : {len(shared_cols):,}")

    print("\n── Value comparison (shared stations × shared columns) ─────")
    a = df5.loc[sorted(shared_stations), shared_cols].astype(float)
    b = df4.loc[sorted(shared_stations), shared_cols].astype(float)

    # Cells where one is NaN and other is not
    a_nan = a.isna()
    b_nan = b.isna()
    nan_mismatch = (a_nan != b_nan).sum().sum()
    print(f"  NaN mismatches (one side missing, other not): {nan_mismatch:,}")

    # Cells where both have values — check numeric difference
    both_valid = ~a_nan & ~b_nan
    diff = (a - b)[both_valid]
    abs_diff = diff.abs()

    n_cells = both_valid.sum().sum()
    n_differ = (abs_diff > 1e-6).sum().sum()

    print(f"  Cells with values in both  : {n_cells:,}")
    print(f"  Cells differing by > 1e-6°C: {n_differ:,}")

    if n_cells > 0 and n_differ > 0:
        flat = abs_diff.values[abs_diff.values > 1e-6]
        print(f"  Max absolute difference    : {flat.max():.6f}°C")
        print(f"  Mean absolute difference   : {flat.mean():.6f}°C")

    if n_differ == 0 and nan_mismatch == 0 and not only_in_5 and not only_in_4:
        print("\n  ✓ Outputs are IDENTICAL.")
    elif n_differ == 0 and nan_mismatch == 0:
        print("\n  ✓ Values identical — only station-set differences remain.")
    else:
        print("\n  ✗ Differences found — investigate above.")


# ── main ─────────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Ignore cache and re-run v4 step0')
    args = parser.parse_args()

    print("=== Step 0 comparison: gistemp5 vs gistemp4.0 ===\n")

    print("[1/3] Fetching gistemp4.0 input data")
    fetch_v4_inputs()

    print("\n[2/3] Running gistemp4.0 step0")
    df4 = run_v4_step0(force=args.force)

    print("\n[3/3] Running gistemp5 step0")
    df5 = step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)

    compare(df5, df4)


if __name__ == '__main__':
    main()
