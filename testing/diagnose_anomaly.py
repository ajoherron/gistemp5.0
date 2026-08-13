"""
Diagnose why 69 urban stations differ after step2.

For each differing station, compare:
  1. Our annual anomaly vs gistemp4.0's exact algorithm applied to same data
  2. Look for any mismatch in the anomaly series

Run from repo root:
    python testing/diagnose_anomaly.py
"""

import os
import sys
import io
import math
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO_ROOT, 'gistemp4.0'))
sys.path.insert(0, REPO_ROOT)  # must come first so our 'parameters' wins over gistemp4.0's

from utils.config import START_YEAR, END_YEAR
from utils.config import GHCN_TEMP_URL, GHCN_META_URL, STRANGE_URL, BRIGHTNESS_URL
from steps.step0 import step0
from steps.step1 import step1
from steps.step2 import step2, _compute_annual_anomalies, _build_matrix

V4_CACHE = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'step2_cache.parquet')

MISSING = 9999.0


def valid(v):
    return int(v) != 9999


def annual_anomaly_v4(series):
    """Exact copy of gistemp4.0's annual_anomaly()."""
    good = False
    monthly_means = []
    for m in range(12):
        month_data = series[m::12]
        if m == 11:
            month_data = month_data[:-1]
        month_data = [x for x in month_data if int(x) != 9999]
        if not month_data:
            monthly_means.append(MISSING)
            continue
        monthly_means.append(float(sum(month_data)) / len(month_data))

    annual_anoms = []
    for y in range(int(len(series) / 12)):
        total = [0.0] * 4
        count = [0] * 4
        for m in range(-1, 11):
            index = y * 12 + m
            if index >= 0:
                datum = series[index]
                if valid(datum) and int(monthly_means[m % 12]) != 9999:
                    season = (m + 1) // 3
                    total[season] += datum - monthly_means[m % 12]
                    count[season] += 1
        season_anomalies = []
        for s in range(4):
            if count[s] >= 2:
                season_anomalies.append(total[s] / count[s])
        if len(season_anomalies) > 2:
            good = True
            annual_anoms.append(sum(season_anomalies) / len(season_anomalies))
        else:
            annual_anoms.append(MISSING)

    if good:
        BASE_YEAR = 1880
        pad = [MISSING] * (series.first_year - BASE_YEAR)
        return pad + annual_anoms
    else:
        return None


def df_row_to_v4_series(row, start_year, end_year):
    """Convert a DataFrame row to a gistemp4.0-style series list."""

    class FakeSeries:
        pass

    obj = FakeSeries()
    obj.first_year = start_year
    series = []
    for yr in range(start_year, end_year + 1):
        for mo in range(1, 13):
            col = f'{mo}_{yr}'
            v = row.get(col, np.nan)
            if pd.isna(v):
                series.append(MISSING)
            else:
                series.append(float(v))
    obj.series = series
    obj.first_year = start_year
    return obj


def main():
    print("Loading gistemp4.0 step2 cache...")
    df4 = pd.read_parquet(V4_CACHE)

    print("Running step0/step1/step2...")
    df0 = step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)
    df1 = step1(df0, STRANGE_URL, START_YEAR, END_YEAR)
    df5 = step2(df1, GHCN_META_URL, BRIGHTNESS_URL, START_YEAR, END_YEAR)

    tc5 = [c for c in df5.columns if c not in ('Latitude', 'Longitude', '__LastGHCNYear__')]
    tc4 = [c for c in df4.columns if c not in ('Latitude', 'Longitude')]
    shared_cols = sorted(set(tc5) & set(tc4), key=lambda c: int(c.split('_')[1]))
    shared_st = sorted(set(df5.index) & set(df4.index))
    a = df5.loc[shared_st, shared_cols].astype(float)
    b = df4.loc[shared_st, shared_cols].astype(float)
    diff = (a - b).abs()
    per_station_max = diff[diff > 1e-4].max(axis=1).dropna()
    differ_sids = list(per_station_max.nlargest(20).index)

    print(f"\nTop 20 differing stations: {differ_sids}")

    # Build matrix for anomaly computation
    n_years = END_YEAR - START_YEAR + 1
    tc1 = [c for c in df1.columns if c not in ('Latitude', 'Longitude', '__LastGHCNYear__')]

    print("\n=== Annual anomaly comparison for differing stations ===\n")

    for sid in differ_sids[:5]:
        if sid not in df1.index:
            print(f"{sid}: not in step1 output")
            continue

        row = df1.loc[sid, tc1].to_dict()

        # Build the (1, n_years, 12) sub-matrix for this station
        mat_1 = _build_matrix(df1.loc[[sid], tc1], START_YEAR, END_YEAR)

        # Our vectorized anomaly
        our_anoms = _compute_annual_anomalies(mat_1)[0]  # shape (n_years,)

        # gistemp4.0 exact algorithm on our step1 data
        fake = df_row_to_v4_series(row, START_YEAR, END_YEAR)
        v4_anoms_raw = annual_anomaly_v4(fake)
        if v4_anoms_raw is None:
            print(f"{sid}: v4 algorithm returned None")
            continue
        v4_anoms = np.array([np.nan if int(x) == 9999 else x for x in v4_anoms_raw])

        # Compare
        diff_anoms = np.abs(our_anoms - v4_anoms)
        # NaN handling
        both_valid = ~np.isnan(our_anoms) & ~np.isnan(v4_anoms)
        n_diff_anoms = int(np.sum(diff_anoms[both_valid] > 1e-6))

        print(f"{sid}:")
        print(f"  Anomaly cells differing > 1e-6: {n_diff_anoms}")
        if n_diff_anoms > 0:
            worst_yi = int(np.argmax(np.where(both_valid, diff_anoms, 0)))
            print(f"  Max anomaly diff: {diff_anoms[both_valid].max():.8f} at year {START_YEAR + worst_yi}")
            print(f"    ours={our_anoms[worst_yi]:.8f}, v4={v4_anoms[worst_yi]:.8f}")

        # Also show the last valid year and last GHCN year
        any_valid_yr = ~np.all(np.isnan(mat_1[0]), axis=1)
        rev = any_valid_yr[::-1]
        last_valid_yi = n_years - 1 - int(np.argmax(rev))
        lgy = df1.loc[sid, '__LastGHCNYear__'] if '__LastGHCNYear__' in df1.columns else float('nan')
        print(f"  last_valid_year={START_YEAR + last_valid_yi}, last_ghcn_year={lgy}")

        # Check December of last years
        dec_col_2023 = f'12_2023'
        dec_col_lvy = f'12_{START_YEAR + last_valid_yi}'
        print(f"  Dec 2023 in step1: {df1.loc[sid, dec_col_2023] if dec_col_2023 in df1.columns else 'N/A'}")
        print(f"  Dec {START_YEAR + last_valid_yi} in step1: {df1.loc[sid, dec_col_lvy] if dec_col_lvy in df1.columns else 'N/A'}")

        # Final output difference
        mx = per_station_max.get(sid, 0)
        print(f"  Final step2 output max diff: {mx:.6f}°C")
        print()


if __name__ == '__main__':
    main()
