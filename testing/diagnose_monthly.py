"""
Trace monthly mean and seasonal computation for AGM00060353.
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

from parameters.constants import START_YEAR, END_YEAR
from parameters.data import GHCN_TEMP_URL, GHCN_META_URL, STRANGE_URL, BRIGHTNESS_URL
from steps.step0 import step0
from steps.step1 import step1
from steps.step2 import drop_short_records, _build_matrix, BASE_YEAR

LOG_FILE = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'log', 'step2.log')
TARGET = 'AGM00060353'
MISSING = 9999.0


def load_v4_anomaly_series(uid):
    with open(LOG_FILE) as f:
        for line in f:
            m = re.match(rf'{re.escape(uid)}\s+annual-anomaly\s+(.*)', line)
            if m:
                d = ast.literal_eval(m.group(1))
                return d['series']
    return None


def compute_annual_anomaly_gistemp4_style(series, first_year):
    """Replicate gistemp4.0's annual_anomaly() exactly (Python scalars)."""
    monthly_means = []
    for m in range(12):
        month_data = series[m::12]
        if m == 11:
            month_data = month_data[:-1]
        month_data = [x for x in month_data if int(x) != 9999]
        if len(month_data) == 0:
            monthly_means.append(float('nan'))
        else:
            monthly_means.append(float(sum(month_data)) / len(month_data))

    annual_anoms = []
    n_years_station = len(series) // 12
    for y in range(n_years_station):
        total = [0.0] * 4
        count = [0] * 4
        for m in range(-1, 11):
            index = y * 12 + m
            if index >= 0:
                datum = series[index]
                if int(datum) != 9999:
                    season = (m + 1) // 3
                    total[season] += datum - monthly_means[m % 12]
                    count[season] += 1
        season_anomalies = []
        for s in range(4):
            if count[s] >= 2:
                season_anomalies.append(total[s] / count[s])
        if len(season_anomalies) > 2:
            annual_anoms.append(sum(season_anomalies) / len(season_anomalies))
        else:
            annual_anoms.append(MISSING)

    pad = [MISSING] * (first_year - BASE_YEAR)
    return pad + annual_anoms


def compute_annual_anomaly_ours(mat_station, first_year, end_year):
    """Compute annual anomaly the same way as _compute_annual_anomalies for one station."""
    n_years = end_year - first_year + 1
    # Subset the matrix for this station
    s = mat_station  # shape (n_years_full, 12)

    # Last year with any valid data
    any_valid_yr = ~np.all(np.isnan(s), axis=1)
    if not any_valid_yr.any():
        return None

    rev = any_valid_yr[::-1]
    last_yi = len(any_valid_yr) - 1 - np.argmax(rev)

    # Monthly means
    monthly_means = np.nanmean(s, axis=0)  # (12,)

    # Recompute December mean excluding last December
    dec = s[:, 11].copy()
    dec[last_yi] = np.nan
    monthly_means[11] = np.nanmean(dec)

    # Monthly anomalies
    anom = s - monthly_means[np.newaxis, :]  # (n_years_full, 12)

    # Season 0 DJF
    dec_prev = np.full(len(s), np.nan)
    dec_prev[1:] = anom[:-1, 11]

    def season_mean(months2d):
        count = np.sum(~np.isnan(months2d), axis=1)
        total = np.nansum(months2d, axis=1)
        return np.where(count >= 2, total / np.maximum(count, 1), np.nan)

    s0 = season_mean(np.stack([dec_prev, anom[:, 0], anom[:, 1]], axis=1))
    s1 = season_mean(anom[:, 2:5])
    s2 = season_mean(anom[:, 5:8])
    s3 = season_mean(anom[:, 8:11])

    all_s = np.stack([s0, s1, s2, s3], axis=1)
    n_valid_s = np.sum(~np.isnan(all_s), axis=1)
    with np.errstate(all='ignore'):
        annual = np.where(n_valid_s >= 3,
                          np.nansum(all_s, axis=1) / n_valid_s,
                          np.nan)
    return annual, monthly_means


def main():
    print(f"Detailed monthly trace for {TARGET}\n")

    print("Running step0 + step1 …")
    df0 = step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)
    df1 = step1(df0, STRANGE_URL, START_YEAR, END_YEAR)
    df1 = drop_short_records(df1)

    mat = _build_matrix(df1, START_YEAR, END_YEAR)
    station_ids = list(df1.index)
    idx = station_ids.index(TARGET)
    mat_station = mat[idx]  # (n_years, 12)

    # Find first and last year with data
    any_valid = ~np.all(np.isnan(mat_station), axis=1)
    first_yi = np.argmax(any_valid)
    last_yi = len(any_valid) - 1 - np.argmax(any_valid[::-1])
    first_year = START_YEAR + first_yi
    last_year = START_YEAR + last_yi

    print(f"Station data: {first_year} – {last_year}")

    # Build the station's series like gistemp4.0 would (for replication)
    # Our monthly values in chronological order starting from first_year
    n_station_years = last_year - first_year + 1
    series_ours = []
    for y in range(n_station_years):
        yr = first_year + y
        for m in range(12):
            v = mat_station[yr - START_YEAR, m]
            series_ours.append(float(v) if not np.isnan(v) else MISSING)

    # Load v4 anomaly from log
    v4_anom_full = load_v4_anomaly_series(TARGET)

    # Compute using gistemp4.0 style
    g4_anom_full = compute_annual_anomaly_gistemp4_style(series_ours, first_year)

    # Compute using our style
    our_result = compute_annual_anomaly_ours(mat_station, START_YEAR, END_YEAR)
    if our_result is None:
        print("No valid data!")
        return
    our_anom_full, our_monthly_means = our_result

    # Compute gistemp4-style monthly means for comparison
    g4_monthly = []
    for m in range(12):
        month_data = series_ours[m::12]
        if m == 11:
            month_data = month_data[:-1]
        month_data = [x for x in month_data if int(x) != 9999]
        g4_monthly.append(sum(month_data) / len(month_data) if month_data else float('nan'))

    print("\n── Monthly means ──")
    month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun',
                   'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    for m in range(12):
        diff = our_monthly_means[m] - g4_monthly[m]
        flag = ' *** DIFFER ***' if abs(diff) > 1e-10 else ''
        print(f"  {month_names[m]}: g4={g4_monthly[m]:.10f}, ours={our_monthly_means[m]:.10f}, diff={diff:.2e}{flag}")

    print("\n── Annual anomaly comparison ──")
    print(f"  {'Year':>4}  {'v4_log':>15}  {'g4_replicated':>15}  {'ours':>15}  {'g4-v4':>10}  {'ours-v4':>10}")
    for yi in range(len(our_anom_full)):
        yr = START_YEAR + yi
        v4_val = v4_anom_full[yi] if yi < len(v4_anom_full) else 9999.0
        g4_val = g4_anom_full[yi] if yi < len(g4_anom_full) else 9999.0
        our_val = float(our_anom_full[yi]) if not np.isnan(our_anom_full[yi]) else 9999.0

        v4_missing = (abs(v4_val - 9999.0) < 0.1)
        g4_missing = (abs(g4_val - 9999.0) < 0.1)
        our_missing = np.isnan(our_anom_full[yi])

        if v4_missing and g4_missing and our_missing:
            continue

        diff_g4 = (g4_val - v4_val) if (not v4_missing and not g4_missing) else float('nan')
        diff_ours = (our_val - v4_val) if (not v4_missing and not our_missing) else float('nan')

        flag = ' ***' if (not np.isnan(diff_ours) and abs(diff_ours) > 1e-6) else ''
        print(f"  {yr:>4}  {v4_val:>15.8f}  {g4_val:>15.8f}  {our_val:>15.8f}  {diff_g4:>10.2e}  {diff_ours:>10.2e}{flag}")


if __name__ == '__main__':
    main()
