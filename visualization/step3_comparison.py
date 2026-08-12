"""
Compare gistemp5 vs gistemp4.0 step 3 output.

Requires cached outputs. Run from repo root:
    python main/run.py                  # generates cache/step3_1880_2026.parquet
    python testing/compare_step3.py     # generates gistemp4.0/tmp/step3_cache.parquet
Then:
    python visualization/step3_comparison.py
"""

import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from parameters.constants import START_YEAR, END_YEAR
from utils import cache as step_cache

V4_CACHE = os.path.join(REPO_ROOT, '..', 'gistemp4.0', 'tmp', 'step3_cache.parquet')
OUT_PATH  = os.path.join(REPO_ROOT, 'visualization', 'step3_comparison.png')

_META = {'lat_s', 'lat_n', 'lon_w', 'lon_e', 'n_stations', 'station_months', 'd'}


def time_cols(df):
    return [c for c in df.columns if c not in _META]


def load_data():
    if not os.path.exists(V4_CACHE):
        raise FileNotFoundError(
            f"gistemp4.0 step3 cache missing: {V4_CACHE}\n"
            "Run: python testing/compare_step3.py"
        )
    df4 = pd.read_parquet(V4_CACHE)

    df5 = step_cache.load('step3', START_YEAR, END_YEAR)
    if df5 is None:
        raise FileNotFoundError(
            f"gistemp5 step3 cache missing for {START_YEAR}–{END_YEAR}.\n"
            "Run: python main/run.py"
        )
    return df4, df5


def annual_global_mean(df):
    tc = time_cols(df)
    years = sorted({int(c.split('_')[1]) for c in tc})
    means, active = [], []
    for yr in years:
        cols = [f'{m}_{yr}' for m in range(1, 13) if f'{m}_{yr}' in df.columns]
        vals = df[cols].values
        means.append(np.nanmean(vals))
        active.append(int(np.any(~np.isnan(vals), axis=1).sum()))
    return pd.Series(means, index=years), pd.Series(active, index=years)


def annual_max_diff(df4, df5):
    tc4 = set(time_cols(df4))
    tc5 = set(time_cols(df5))
    shared = sorted(tc4 & tc5, key=lambda c: (int(c.split('_')[1]), int(c.split('_')[0])))
    years = sorted({int(c.split('_')[1]) for c in shared})
    max_diffs, mean_diffs = [], []
    for yr in years:
        cols = [f'{m}_{yr}' for m in range(1, 13) if f'{m}_{yr}' in shared]
        a = df5[cols].values.astype(float)
        b = df4[cols].values.astype(float)
        both = ~np.isnan(a) & ~np.isnan(b)
        d = np.abs(a - b)
        max_diffs.append(float(d[both].max()) if both.any() else 0.0)
        mean_diffs.append(float(d[both].mean()) if both.any() else 0.0)
    return pd.Series(max_diffs, index=years), pd.Series(mean_diffs, index=years)


def validate(df4, df5):
    tc4 = set(time_cols(df4))
    tc5 = set(time_cols(df5))
    shared = sorted(tc4 & tc5, key=lambda c: (int(c.split('_')[1]), int(c.split('_')[0])))
    a = df5[shared].astype(float).values
    b = df4[shared].astype(float).values
    both = ~np.isnan(a) & ~np.isnan(b)
    d = np.abs(a - b)
    n_differ = int((d[both] > 1e-4).sum())
    max_diff  = float(d[both].max()) if both.any() else 0.0
    mean_diff = float(d[both].mean()) if both.any() else 0.0
    nan_mis   = int(np.sum(np.isnan(a) != np.isnan(b)))
    agreement = "✓ Numerically equivalent" if n_differ == 0 and nan_mis == 0 else f"✗ {n_differ:,} cells differ"
    return {
        'cells_compared': int(both.sum()),
        'nan_mismatch':   nan_mis,
        'cells_differ':   n_differ,
        'max_diff':       max_diff,
        'mean_diff':      mean_diff,
        'agreement':      agreement,
        'empty4':         int((df4['n_stations'] == 0).sum()),
        'empty5':         int((df5['n_stations'] == 0).sum()),
    }


def plot(df4, df5, stats):
    mean4, active4 = annual_global_mean(df4)
    mean5, active5 = annual_global_mean(df5)
    max_d, mean_d  = annual_max_diff(df4, df5)

    BLUE, RED, GREEN, ORANGE = '#1565C0', '#E53935', '#2E7D32', '#E65100'

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
    fig.suptitle(
        f'Step 3 Output: gistemp5 vs gistemp4.0  ({START_YEAR}–{END_YEAR})\n'
        f'{stats["agreement"]}  |  {stats["cells_compared"]:,} cells compared  |  '
        f'Max |diff|: {stats["max_diff"]:.2e} °C  |  Mean |diff|: {stats["mean_diff"]:.2e} °C',
        fontsize=13, fontweight='bold'
    )

    # Panel 1: global mean subbox anomaly
    ax = axes[0]
    ax.plot(mean4.index, mean4.values, color=BLUE, lw=2.5, label='gistemp4.0', zorder=3)
    ax.plot(mean5.index, mean5.values, color=RED,  lw=1.5, ls='--', label='gistemp5', zorder=4)
    ax.axhline(0, color='black', lw=0.6, ls='--', alpha=0.4)
    ax.set_ylabel('Mean Anomaly (°C)', fontsize=11)
    ax.set_title('Global Mean Subbox Anomaly (unweighted mean of 8,000 subboxes)', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.25)

    # Panel 2: per-year max and mean absolute difference
    ax = axes[1]
    ax.plot(max_d.index,  max_d.values,  color=GREEN,  lw=1.5, label='Max |diff|')
    ax.plot(mean_d.index, mean_d.values, color=ORANGE, lw=1.5, label='Mean |diff|', ls='--')
    ax.axhline(0, color='black', lw=0.8, ls='--', alpha=0.5)
    ax.set_ylabel('|Δ| (°C)', fontsize=11)
    ax.set_title('Per-Year Absolute Difference: |gistemp5 − gistemp4.0|', fontsize=12)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2e'))
    ax.legend(fontsize=10)
    ax.grid(alpha=0.25)

    # Panel 3: active (non-empty) subbox count per year
    ax = axes[2]
    ax.fill_between(active4.index, active4.values, color=BLUE, alpha=0.4, label='gistemp4.0')
    ax.fill_between(active5.index, active5.values, color=RED,  alpha=0.35, label='gistemp5')
    ax.set_ylabel('Active Subboxes', fontsize=11)
    ax.set_xlabel('Year', fontsize=11)
    ax.set_title(
        f'Active (Non-Empty) Subbox Count per Year  '
        f'[empty: v4={stats["empty4"]}, v5={stats["empty5"]}]',
        fontsize=12
    )
    ax.legend(fontsize=10)
    ax.grid(alpha=0.25)
    ax.set_xlim(START_YEAR, END_YEAR)

    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight')
    print(f"  Saved → {OUT_PATH}")


if __name__ == '__main__':
    print("Loading data...")
    df4, df5 = load_data()
    print("Validating...")
    stats = validate(df4, df5)
    print(f"  {stats['agreement']}")
    print(f"  Monthly cells compared : {stats['cells_compared']:,}")
    print(f"  NaN mismatches         : {stats['nan_mismatch']:,}")
    print(f"  Cells differing >1e-4  : {stats['cells_differ']:,}")
    print(f"  Max  |diff| (°C)       : {stats['max_diff']:.2e}")
    print(f"  Mean |diff| (°C)       : {stats['mean_diff']:.2e}")
    print(f"  Empty subboxes v4/v5   : {stats['empty4']} / {stats['empty5']}")
    print("Plotting...")
    plot(df4, df5, stats)
