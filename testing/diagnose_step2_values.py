"""
Find where the remaining 25k cell differences come from.
Run from repo root:
    python testing/diagnose_step2_values.py
"""

import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from parameters.constants import START_YEAR, END_YEAR
from parameters.data import GHCN_TEMP_URL, GHCN_META_URL, STRANGE_URL, BRIGHTNESS_URL
from steps.step0 import step0
from steps.step1 import step1
from steps.step2 import step2, drop_short_records

V4_CACHE = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'step2_cache.parquet')
LOG_FILE  = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'log', 'step2.log')

def load_v4_actions():
    """Parse step2.log → {uid: action}"""
    import re
    actions = {}
    with open(LOG_FILE) as f:
        for line in f:
            m = re.match(r'(\S+)\s+step2-action\s+"(\S+)"', line)
            if m:
                actions[m.group(1)] = m.group(2)
    return actions


def main():
    print("Loading cached gistemp4.0 step2 output …")
    df4 = pd.read_parquet(V4_CACHE)

    print("Running gistemp5 step0 + step1 + step2 …")
    df0 = step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)
    df1 = step1(df0, STRANGE_URL, START_YEAR, END_YEAR)
    df5 = step2(df1, GHCN_META_URL, BRIGHTNESS_URL, START_YEAR, END_YEAR)

    tc5 = [c for c in df5.columns if c not in ('Latitude', 'Longitude')]
    tc4 = [c for c in df4.columns if c not in ('Latitude', 'Longitude')]
    shared_cols = sorted(set(tc5) & set(tc4), key=lambda c: int(c.split('_')[1]))
    shared_st = sorted(set(df5.index) & set(df4.index))

    a = df5.loc[shared_st, shared_cols].astype(float)
    b = df4.loc[shared_st, shared_cols].astype(float)

    diff = (a - b).abs()
    exceeds = diff > 1e-4

    # Per-station max difference
    per_station_max = diff[exceeds].max(axis=1).dropna()
    n_stations_differ = len(per_station_max)
    print(f"\nStations with at least one cell differing > 1e-4: {n_stations_differ}")

    print("\nTop 10 stations by max difference:")
    for sid in per_station_max.nlargest(10).index:
        mx = per_station_max[sid]
        # How many cells for this station differ?
        n = int(exceeds.loc[sid].sum())
        print(f"  {sid}: max_diff={mx:.6f}°C, n_cells={n}")

    # Are differences in rural or urban stations?
    actions = load_v4_actions()
    rural_diffs = []
    urban_diffs = []
    for sid in per_station_max.index:
        act = actions.get(sid, 'unknown')
        if act == 'rural':
            rural_diffs.append((sid, per_station_max[sid]))
        elif act in ('adjusted',):
            urban_diffs.append((sid, per_station_max[sid]))
        else:
            print(f"  NOTE: {sid} action={act}")

    print(f"\nRural stations with differences: {len(rural_diffs)}")
    if rural_diffs:
        print("  Sample:", rural_diffs[:5])

    print(f"Urban (adjusted) stations with differences: {len(urban_diffs)}")
    if urban_diffs:
        vals = [v for _, v in urban_diffs]
        print(f"  Max={max(vals):.6f}, Mean={sum(vals)/len(vals):.6f}")
        print("  Sample:", urban_diffs[:5])

    # Pick one differing adjusted station and show the anomaly vs log
    if urban_diffs:
        sid, _ = urban_diffs[0]
        print(f"\nDeep dive on {sid}:")
        row5 = df5.loc[sid, shared_cols]
        row4 = b.loc[sid]
        diff_cols = [c for c in shared_cols if abs(float(row5[c]) - float(row4[c])) > 1e-4
                     if not pd.isna(row5[c]) and not pd.isna(row4[c])]
        print(f"  Differing cols ({len(diff_cols)}):", diff_cols[:5])
        for c in diff_cols[:3]:
            print(f"    {c}: ours={float(row5[c]):.8f}, v4={float(row4[c]):.8f}, diff={abs(float(row5[c])-float(row4[c])):.8f}")


if __name__ == '__main__':
    main()
