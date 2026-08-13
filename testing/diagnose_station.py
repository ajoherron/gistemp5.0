"""
Trace step2 computation for a specific station to find floating-point divergence.
Run from repo root:
    python testing/diagnose_station.py
"""

import ast
import math
import os
import re
import sys

import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from utils.config import START_YEAR, END_YEAR
from utils.config import GHCN_TEMP_URL, GHCN_META_URL, STRANGE_URL, BRIGHTNESS_URL
from steps.step0 import step0
from steps.step1 import step1
from steps.step2 import (
    drop_short_records, _build_matrix, _compute_annual_anomalies,
    _get_global_light, _Ann, _combine_neighbours, _cmbine, _prepare_series,
    _get_neighbours, BASE_YEAR, EARTH_RADIUS, RURAL_LIGHT_THRESHOLD,
    URBAN_FULL_RADIUS, URBAN_MIN_YEARS, URBAN_PROPORTION_GOOD,
    URBAN_MIN_RURAL_STATIONS, RURAL_MIN_OVERLAP
)

LOG_FILE = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'log', 'step2.log')
TARGET = 'AGM00060353'


def load_v4_anomalies(uid):
    with open(LOG_FILE) as f:
        for line in f:
            m = re.match(rf'{re.escape(uid)}\s+annual-anomaly\s+(.*)', line)
            if m:
                d = ast.literal_eval(m.group(1))
                series = d['series']
                year0 = d['year']
                return year0, series
    return None, None


def load_v4_adjustment(uid):
    with open(LOG_FILE) as f:
        content = f.read()
    m = re.search(rf'{re.escape(uid)}\s+adjustment\s+(.*)', content)
    if m:
        d = ast.literal_eval(m.group(1))
        return d
    return None


def load_v4_neighbours(uid):
    with open(LOG_FILE) as f:
        for line in f:
            m = re.match(rf'{re.escape(uid)}\s+neighbours\s+(.*)', line)
            if m:
                return ast.literal_eval(m.group(1))
    return []


def main():
    print(f"Tracing step2 for {TARGET}\n")

    # Load gistemp4.0 reference
    year0, v4_anom = load_v4_anomalies(TARGET)
    if v4_anom is None:
        print(f"Station {TARGET} not in log. Exiting.")
        return
    v4_adj = load_v4_adjustment(TARGET)
    v4_neighbours = load_v4_neighbours(TARGET)
    print(f"v4 neighbours: {v4_neighbours[:5]}...")

    # Run pipeline
    print("\nRunning step0 + step1 …")
    df0 = step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)
    df1 = step1(df0, STRANGE_URL, START_YEAR, END_YEAR)
    df1 = drop_short_records(df1)

    n_years = END_YEAR - START_YEAR + 1
    station_ids = list(df1.index)

    # Build matrix and compute annual anomalies
    print("Building matrix and computing annual anomalies …")
    mat = _build_matrix(df1, START_YEAR, END_YEAR)
    annual_all = _compute_annual_anomalies(mat)

    idx = station_ids.index(TARGET)
    our_anom = annual_all[idx]

    # Compare annual anomaly for TARGET
    print(f"\n── Annual anomaly for {TARGET} ──")
    v4_clean = [x for x in v4_anom if x != 9999.0]
    our_clean = [x for x in our_anom if not np.isnan(x)]
    print(f"  v4 has {sum(1 for x in v4_anom if x != 9999.0)} valid values")
    print(f"  ours has {sum(1 for x in our_anom if not np.isnan(x))} valid values")

    # Compare the first few valid values
    v4_valid = [(i, v) for i, v in enumerate(v4_anom) if v != 9999.0]
    our_valid = [(i, v) for i, v in enumerate(our_anom) if not np.isnan(v)]
    max_diff_anom = 0.0
    for (i4, v4_val), (i5, v5_val) in zip(v4_valid, our_valid):
        d = abs(v4_val - v5_val)
        if d > max_diff_anom:
            max_diff_anom = d
    print(f"  Max diff in annual anomaly: {max_diff_anom:.2e}")
    if max_diff_anom > 0:
        print("  First few diffs:")
        for (i4, v4_val), (i5, v5_val) in zip(v4_valid[:5], our_valid[:5]):
            year = START_YEAR + i4
            d = v4_val - v5_val
            print(f"    year {year}: v4={v4_val:.10f}, ours={v5_val:.10f}, diff={d:.2e}")

    # Get global_light and classify stations
    gl = _get_global_light(GHCN_META_URL, BRIGHTNESS_URL)

    pi180 = math.pi / 180.0
    rural = []
    urban_ann = {}

    for i, sid in enumerate(station_ids):
        annual = annual_all[i]
        if np.all(np.isnan(annual)):
            continue
        lat = float(df1.at[sid, 'Latitude'])
        lon = float(df1.at[sid, 'Longitude'])
        ann = _Ann(sid, annual, lat, lon)
        light = gl.get(sid, None)
        is_rural = (light is None) or (light <= RURAL_LIGHT_THRESHOLD)
        if is_rural:
            rural.append(ann)
        else:
            urban_ann[sid] = ann

    def reclen(s):
        return int(np.sum(~np.isnan(s.anomalies)))
    rural.sort(key=reclen)
    rural.reverse()

    r_snlat = np.array([r.snlat for r in rural])
    r_cslat = np.array([r.cslat for r in rural])
    r_cslon = np.array([r.cslon for r in rural])
    r_snlon = np.array([r.snlon for r in rural])

    # Get neighbours for TARGET
    us = urban_ann[TARGET]
    R = URBAN_FULL_RADIUS

    for radius in [R / 2, R]:
        neighbours = _get_neighbours(us, rural, r_snlat, r_cslat, r_cslon, r_snlon, radius)
        if neighbours:
            break

    our_nb_ids = [n.uid for n in neighbours]
    print(f"\n── Neighbours ──")
    print(f"  v4 first 5:  {v4_neighbours[:5]}")
    print(f"  ours first 5: {our_nb_ids[:5]}")
    same = (our_nb_ids == v4_neighbours)
    print(f"  Neighbour lists identical: {same}")

    # Compute combined rural series
    print("\n── Combined rural series ──")
    counts, combined = _combine_neighbours(n_years, neighbours)

    v4_combined = v4_adj['series']  # The combined from v4 log
    n_valid_v4 = sum(1 for v in v4_combined if v != 9999.0)
    n_valid_ours = sum(1 for v in combined if not np.isnan(v))
    print(f"  v4 valid entries: {n_valid_v4}")
    print(f"  ours valid entries: {n_valid_ours}")

    max_diff_comb = 0.0
    for i, (v4_v, our_v) in enumerate(zip(v4_combined, combined)):
        if v4_v == 9999.0 and np.isnan(our_v):
            continue
        if v4_v == 9999.0 or np.isnan(our_v):
            print(f"  Mismatch at i={i}: v4={v4_v}, ours={our_v}")
            continue
        d = abs(v4_v - our_v)
        if d > max_diff_comb:
            max_diff_comb = d
    print(f"  Max diff in combined series: {max_diff_comb:.2e}")

    # Compute difference series
    print("\n── Difference series (combined - urban_anomaly) ──")
    v4_diff_pts = v4_adj['difference']
    v4_diff_dict = dict(v4_diff_pts)

    from steps.step2 import _prepare_series
    points, quorate_count = _prepare_series(START_YEAR, combined, us.anomalies, counts)

    print(f"  v4 points: {len(v4_diff_pts)}, ours: {len(points)}")
    max_diff_pts = 0.0
    for year, our_val in points[:len(v4_diff_pts)]:
        v4_val = v4_diff_dict.get(year, None)
        if v4_val is None:
            continue
        d = abs(our_val - v4_val)
        if d > max_diff_pts:
            max_diff_pts = d
    print(f"  Max diff in difference points: {max_diff_pts:.2e}")
    if max_diff_pts > 0:
        print("  First few diffs:")
        for year, our_val in points[:5]:
            v4_val = v4_diff_dict.get(year, None)
            if v4_val is not None:
                d = our_val - v4_val
                print(f"    {year}: v4={v4_val:.10f}, ours={our_val:.10f}, diff={d:.2e}")


if __name__ == '__main__':
    main()
