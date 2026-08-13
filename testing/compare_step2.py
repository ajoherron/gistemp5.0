"""
Compare gistemp5 step2 output against gistemp4.0 step2.

Run from repo root:
    python testing/compare_step2.py
"""

import os
import subprocess
import sys
import urllib.request

import numpy as np
import pandas as pd

REPO_ROOT   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4_DIR      = os.path.join(REPO_ROOT, '..', 'gistemp4.0')
V4_INPUT    = os.path.join(V4_DIR, 'tmp', 'input')
V4_CACHE    = os.path.join(V4_DIR, 'tmp', 'step2_cache.parquet')
DUMP_SCRIPT = os.path.join(REPO_ROOT, 'testing', '_v4_step2_dump.py')

sys.path.insert(0, REPO_ROOT)

from utils.config import START_YEAR, END_YEAR
from utils.config import GHCN_TEMP_URL, GHCN_META_URL, STRANGE_URL, BRIGHTNESS_URL
from steps.step0 import step0
from steps.step1 import step1
from steps.step2 import step2
from utils import cache as step_cache

EXTRA_INPUT_FILES = {
    'Ts.strange.v4.list.IN_full': STRANGE_URL,
    'wrld-rad.data.txt': BRIGHTNESS_URL,
}


def fetch_v4_inputs():
    os.makedirs(V4_INPUT, exist_ok=True)
    for name, url in EXTRA_INPUT_FILES.items():
        path = os.path.join(V4_INPUT, name)
        if not os.path.exists(path):
            print(f"  Downloading {name} …")
            urllib.request.urlretrieve(url, path)
        else:
            print(f"  {name} already present.")


def run_v4_step2(force: bool = False) -> pd.DataFrame:
    strange_mtime = os.path.getmtime(
        os.path.join(V4_INPUT, 'Ts.strange.v4.list.IN_full')
    )
    cache_fresh = (
        not force
        and os.path.exists(V4_CACHE)
        and os.path.getmtime(V4_CACHE) >= strange_mtime
    )

    if cache_fresh:
        print("  Loading cached gistemp4.0 step2 output …")
        return pd.read_parquet(V4_CACHE)

    print("  Running gistemp4.0 step0 → step1 → step2 (this takes several minutes) …")
    result = subprocess.run(
        [sys.executable, DUMP_SCRIPT, str(START_YEAR), str(END_YEAR), V4_CACHE],
        cwd=V4_DIR,
        capture_output=True,
        text=True,
        timeout=1200,
    )
    if result.returncode != 0:
        print("STDERR from v4 dump:\n", result.stderr[:2000])
        raise RuntimeError("gistemp4.0 step2 dump failed")

    print(f"  Cached to {V4_CACHE}")
    return pd.read_parquet(V4_CACHE)


def time_cols(df: pd.DataFrame):
    return [c for c in df.columns if c not in ('Latitude', 'Longitude')]


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
    if only_in_5 and len(only_in_5) <= 20:
        print("    ", sorted(only_in_5))
    if only_in_4 and len(only_in_4) <= 20:
        print("    ", sorted(only_in_4))

    print("\n── Value comparison (shared stations × shared columns) ─────")
    a = df5.loc[sorted(shared_stations), shared_cols].astype(float)
    b = df4.loc[sorted(shared_stations), shared_cols].astype(float)

    a_nan = a.isna()
    b_nan = b.isna()
    nan_mismatch = (a_nan != b_nan).sum().sum()
    print(f"  NaN mismatches (one side missing, other not): {nan_mismatch:,}")

    both_valid = ~a_nan & ~b_nan
    abs_diff = (a - b).abs()

    n_cells  = both_valid.sum().sum()
    n_differ = (abs_diff[both_valid] > 1e-4).sum().sum()

    print(f"  Cells with values in both  : {n_cells:,}")
    print(f"  Cells differing by > 1e-4°C: {n_differ:,}")

    if n_cells > 0 and n_differ > 0:
        flat = abs_diff.values[abs_diff.values > 1e-4]
        print(f"  Max absolute difference    : {flat.max():.6f}°C")
        print(f"  Mean absolute difference   : {flat.mean():.6f}°C")

    if n_differ == 0 and nan_mismatch == 0 and not only_in_5 and not only_in_4:
        print("\n  ✓ Numerically equivalent (no differences above 1e-4°C; any residual is floating-point noise).")
    elif n_differ == 0 and nan_mismatch == 0:
        print("\n  ✓ Values equivalent — only station-set differences remain.")
    else:
        print("\n  ✗ Differences found — investigate above.")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--force', action='store_true', help='Ignore all caches and re-run everything')
    args = parser.parse_args()

    print("=== Step 2 comparison: gistemp5 vs gistemp4.0 ===\n")

    print("[1/5] Fetching additional gistemp4.0 input data")
    fetch_v4_inputs()

    print("\n[2/5] Running gistemp4.0 step0 → step1 → step2")
    df4 = run_v4_step2(force=args.force)

    print("\n[3/5] Running gistemp5 step0")
    df0 = None if args.force else step_cache.load('step0', START_YEAR, END_YEAR)
    if df0 is None:
        df0 = step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)
        step_cache.save(df0, 'step0', START_YEAR, END_YEAR)
    else:
        print("  Loaded from cache.")

    print("\n[4/5] Running gistemp5 step1")
    df1 = None if args.force else step_cache.load('step1', START_YEAR, END_YEAR)
    if df1 is None:
        df1 = step1(df0, STRANGE_URL, START_YEAR, END_YEAR)
        step_cache.save(df1, 'step1', START_YEAR, END_YEAR)
    else:
        print("  Loaded from cache.")

    print("\n[5/5] Running gistemp5 step2")
    df5 = None if args.force else step_cache.load('step2', START_YEAR, END_YEAR)
    if df5 is None:
        df5 = step2(df1, GHCN_META_URL, BRIGHTNESS_URL, START_YEAR, END_YEAR)
        step_cache.save(df5, 'step2', START_YEAR, END_YEAR)
    else:
        print("  Loaded from cache.")

    compare(df5, df4)


if __name__ == '__main__':
    main()
