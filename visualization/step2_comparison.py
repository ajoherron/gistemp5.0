"""
Plot global mean temperature and station count from step 2 outputs.

Requires cached step outputs. Run from repo root:
    python main/run.py                  # generates cache/step2_1880_2026.parquet
    python testing/compare_step2.py     # generates gistemp4.0/tmp/step2_cache.parquet
Then:
    python visualization/step2_comparison.py
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
from tools import cache as step_cache

V4_CACHE = os.path.join(REPO_ROOT, 'gistemp4.0', 'tmp', 'step2_cache.parquet')
OUT_PATH  = os.path.join(REPO_ROOT, 'visualization', 'step2_comparison.png')


def load_data():
    if not os.path.exists(V4_CACHE):
        raise FileNotFoundError(
            f"gistemp4.0 cache missing: {V4_CACHE}\n"
            "Run: python testing/compare_step2.py"
        )
    df4 = pd.read_parquet(V4_CACHE)

    df5 = step_cache.load('step2', START_YEAR, END_YEAR)
    if df5 is None:
        raise FileNotFoundError(
            f"gistemp5 step2 cache missing for {START_YEAR}–{END_YEAR}.\n"
            "Run: python main/run.py"
        )
    return df4, df5


def annual_global_mean(df, start_year, end_year):
    years = range(start_year, end_year + 1)
    means, counts = [], []
    for yr in years:
        cols = [f'{m}_{yr}' for m in range(1, 13) if f'{m}_{yr}' in df.columns]
        if cols:
            vals = df[cols].values
            means.append(np.nanmean(vals))
            counts.append(int(np.any(~np.isnan(vals), axis=1).sum()))
        else:
            means.append(np.nan)
            counts.append(0)
    idx = list(years)
    return pd.Series(means, index=idx), pd.Series(counts, index=idx)


def validate(df5, df4):
    meta = {'Latitude', 'Longitude', '__LastGHCNYear__'}
    tc4 = [c for c in df4.columns if c not in meta]
    tc5 = [c for c in df5.columns if c not in meta]
    shared_cols = sorted(set(tc4) & set(tc5), key=lambda c: (int(c.split('_')[1]), int(c.split('_')[0])))
    shared_sids = sorted(set(df4.index) & set(df5.index))

    a = df5.loc[shared_sids, shared_cols].astype(float)
    b = df4.loc[shared_sids, shared_cols].astype(float)
    diff = (a - b).abs()
    both = ~a.isna() & ~b.isna()

    print(f"  Shared stations       : {len(shared_sids):,}")
    print(f"  Monthly cells compared: {int(both.sum().sum()):,}")
    print(f"  NaN mismatches        : {int((a.isna() != b.isna()).sum().sum()):,}")
    print(f"  Cells differing >1e-4 : {int((diff[both] > 1e-4).sum().sum()):,}")
    print(f"  Max |diff| (°C)       : {float(diff.max().max()):.2e}")


def plot(df4, df5):
    mean4, cnt4 = annual_global_mean(df4, START_YEAR, END_YEAR)
    mean5, cnt5 = annual_global_mean(df5, START_YEAR, END_YEAR)

    BLUE, RED, GREEN = '#1565C0', '#E53935', '#2E7D32'

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
    fig.suptitle(f'Step 2 Output: gistemp5 vs gistemp4.0  ({START_YEAR}–{END_YEAR})',
                 fontsize=14, fontweight='bold')

    ax = axes[0]
    ax.plot(mean4.index, mean4.values, color=BLUE, lw=2.5, label='gistemp4.0', zorder=3)
    ax.plot(mean5.index, mean5.values, color=RED, lw=1.5, ls='--',
            label='gistemp5 (identical)', zorder=4)
    ax.set_ylabel('Mean Temperature (°C)', fontsize=11)
    ax.set_title('Global Mean Station Temperature (unweighted)', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.25)

    ax = axes[1]
    ax.plot((mean5 - mean4).abs().index, (mean5 - mean4).abs().values, color=GREEN, lw=1.5)
    ax.axhline(0, color='black', lw=0.8, ls='--', alpha=0.5)
    ax.set_ylabel('|Δ| (°C)', fontsize=11)
    ax.set_title('Absolute Difference: |gistemp5 − gistemp4.0|', fontsize=12)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2e'))
    ax.grid(alpha=0.25)

    ax = axes[2]
    ax.fill_between(cnt4.index, cnt4.values, color=BLUE, alpha=0.4, label='gistemp4.0')
    ax.fill_between(cnt5.index, cnt5.values, color=RED, alpha=0.35, label='gistemp5')
    ax.set_ylabel('Active Stations', fontsize=11)
    ax.set_xlabel('Year', fontsize=11)
    ax.set_title('Active Station Count per Year', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.25)
    ax.set_xlim(START_YEAR, END_YEAR)

    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight')
    print(f"  Saved → {OUT_PATH}")


if __name__ == '__main__':
    print("Loading data...")
    df4, df5 = load_data()
    print("\nValidation:")
    validate(df5, df4)
    print("\nPlotting...")
    plot(df4, df5)
