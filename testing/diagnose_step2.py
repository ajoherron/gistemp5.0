"""
Diagnostic script to identify differences between gistemp5 and gistemp4.0 step2.

Run from repo root:
    python testing/diagnose_step2.py
"""

import os
import sys
import re

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from utils.config import START_YEAR, END_YEAR
from utils.config import GHCN_TEMP_URL, GHCN_META_URL, STRANGE_URL, BRIGHTNESS_URL
from steps.step0 import step0
from steps.step1 import step1
from steps.step2 import drop_short_records, _time_cols

LOG_FILE = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'log', 'step2.log')
V4_CACHE = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'step2_cache.parquet')


def load_v4_short_stations():
    short = set()
    with open(LOG_FILE) as f:
        for line in f:
            m = re.match(r'(\S+)\s+step2-action "short"', line)
            if m:
                short.add(m.group(1))
    return short


def main():
    print("=== Step 2 Diagnosis ===\n")

    print("[1/3] Running gistemp5 step0 + step1")
    df0 = step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)
    df1 = step1(df0, STRANGE_URL, START_YEAR, END_YEAR)
    print(f"  step1 output: {len(df1)} stations")

    print("\n[2/3] Computing our drop_short_records")
    tc = _time_cols(df1)
    valid_per_month = pd.DataFrame({
        m: df1[[c for c in tc if c.startswith(f'{m}_')]].notna().sum(axis=1)
        for m in range(1, 13)
    }, index=df1.index)
    max_valid = valid_per_month.max(axis=1)
    our_short = set(df1.index[max_valid < 20])
    print(f"  We drop: {len(our_short)} stations as 'short'")

    print("\n[3/3] Comparing with gistemp4.0")
    v4_short = load_v4_short_stations()
    print(f"  gistemp4.0 drops: {len(v4_short)} stations as 'short'")

    extra_ours = our_short - v4_short   # we drop, v4 keeps
    missing_ours = v4_short - our_short  # v4 drops, we keep

    print(f"\n  We drop that v4 keeps: {len(extra_ours)}")
    print(f"  v4 drops that we keep: {len(missing_ours)}")

    if extra_ours:
        print("\n  Sample of stations we wrongly drop (our max_valid vs v4 action):")
        for sid in sorted(extra_ours)[:20]:
            mv = int(max_valid.get(sid, -1))
            print(f"    {sid}: our max_valid={mv}")

    if missing_ours:
        print("\n  Sample of stations v4 wrongly drops but we keep:")
        for sid in sorted(missing_ours)[:10]:
            mv = int(max_valid.get(sid, -1))
            print(f"    {sid}: our max_valid={mv}")

    # Also look at value differences for shared stations
    if os.path.exists(V4_CACHE):
        print("\n[4] Value difference analysis (sample station)")
        df4 = pd.read_parquet(V4_CACHE)
        df1_keep = drop_short_records(df1)

        stations5 = set(df1_keep.index)
        stations4 = set(df4.index)
        shared = stations5 & stations4

        # Find a station that has big differences
        tc5 = [c for c in df1_keep.columns if c not in ('Latitude', 'Longitude')]
        tc4 = [c for c in df4.columns if c not in ('Latitude', 'Longitude')]
        shared_cols = sorted(set(tc5) & set(tc4), key=lambda c: int(c.split('_')[1]))

        # Pick first 5 shared stations and show differences
        sample = sorted(shared)[:5]
        for sid in sample:
            a = df1_keep.loc[sid, shared_cols].astype(float)
            b = df4.loc[sid, shared_cols].astype(float)
            both = ~a.isna() & ~b.isna()
            diff = (a - b).abs()
            max_d = diff[both].max() if both.any() else 0
            print(f"  {sid}: max_diff={max_d:.6f}°C, n_both={both.sum()}")


if __name__ == '__main__':
    main()
