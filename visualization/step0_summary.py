"""
Compare gistemp5 vs gistemp4.0 step 0 output.

Requires cached outputs. Run from repo root:
    python main/run.py                  # generates cache/step0_1880_2026.parquet
    python testing/compare_step2.py     # generates gistemp4.0/tmp/step0_cache.parquet
Then:
    python visualization/step0_summary.py
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

V4_CACHE = os.path.join(REPO_ROOT, '..', 'gistemp4.0', 'tmp', 'step0_cache.parquet')
OUT_PATH  = os.path.join(REPO_ROOT, 'visualization', 'step0_summary.png')

META_COLS = {'Latitude', 'Longitude', '__LastGHCNYear__'}


def load_data():
    if not os.path.exists(V4_CACHE):
        raise FileNotFoundError(
            f"gistemp4.0 step0 cache missing: {V4_CACHE}\n"
            "Run: python testing/compare_step2.py"
        )
    df4 = pd.read_parquet(V4_CACHE)

    df5 = step_cache.load('step0', START_YEAR, END_YEAR)
    if df5 is None:
        raise FileNotFoundError(
            f"gistemp5 step0 cache missing for {START_YEAR}–{END_YEAR}.\n"
            "Run: python main/run.py"
        )
    return df4, df5


def annual_global_mean(df):
    tc = [c for c in df.columns if c not in META_COLS]
    years = sorted({int(c.split('_')[1]) for c in tc})
    means, counts = [], []
    for yr in years:
        cols = [f'{m}_{yr}' for m in range(1, 13) if f'{m}_{yr}' in df.columns]
        vals = df[cols].values
        means.append(np.nanmean(vals))
        counts.append(int(np.any(~np.isnan(vals), axis=1).sum()))
    return pd.Series(means, index=years), pd.Series(counts, index=years)


def validate(df4, df5):
    tc4 = [c for c in df4.columns if c not in META_COLS]
    tc5 = [c for c in df5.columns if c not in META_COLS]
    shared_cols = sorted(set(tc4) & set(tc5), key=lambda c: (int(c.split('_')[1]), int(c.split('_')[0])))
    shared_sids = sorted(set(df4.index) & set(df5.index))

    a = df5.loc[shared_sids, shared_cols].astype(float)
    b = df4.loc[shared_sids, shared_cols].astype(float)
    diff = (a - b).abs()
    both = ~a.isna() & ~b.isna()

    n_differ  = int((diff[both] > 1e-4).sum().sum())
    max_diff  = float(diff.max().max())
    agreement = "✓ Numerically equivalent" if n_differ == 0 else f"✗ {n_differ:,} cells differ"

    return {
        'shared_sids': shared_sids,
        'cells_compared': int(both.sum().sum()),
        'nan_mismatch': int((a.isna() != b.isna()).sum().sum()),
        'cells_differ': n_differ,
        'max_diff': max_diff,
        'agreement': agreement,
    }


def plot(df4, df5, stats):
    mean4, cnt4 = annual_global_mean(df4)
    mean5, cnt5 = annual_global_mean(df5)

    BLUE, RED, GREEN = '#1565C0', '#E53935', '#2E7D32'

    fig, axes = plt.subplots(3, 1, figsize=(14, 11), sharex=True)
    fig.suptitle(
        f'Step 0 Output: gistemp5 vs gistemp4.0  ({START_YEAR}–{END_YEAR})\n'
        f'{stats["agreement"]}  |  {stats["shared_sids"].__len__():,} shared stations  |  '
        f'Max |diff|: {stats["max_diff"]:.2e} °C',
        fontsize=13, fontweight='bold'
    )

    # ── Global mean temperature ──────────────────────────────────
    ax = axes[0]
    ax.plot(mean4.index, mean4.values, color=BLUE, lw=2.5, label='gistemp4.0', zorder=3)
    ax.plot(mean5.index, mean5.values, color=RED, lw=1.5, ls='--', label='gistemp5', zorder=4)
    ax.set_ylabel('Mean Temperature (°C)', fontsize=11)
    ax.set_title('Global Mean Station Temperature (unweighted)', fontsize=12)
    ax.legend(fontsize=10)
    ax.grid(alpha=0.25)

    # ── Absolute difference ──────────────────────────────────────
    ax = axes[1]
    abs_diff = (mean5 - mean4).abs()
    ax.plot(abs_diff.index, abs_diff.values, color=GREEN, lw=1.5)
    ax.axhline(0, color='black', lw=0.8, ls='--', alpha=0.5)
    ax.set_ylabel('|Δ| (°C)', fontsize=11)
    ax.set_title('Absolute Difference: |gistemp5 − gistemp4.0|', fontsize=12)
    ax.yaxis.set_major_formatter(mticker.FormatStrFormatter('%.2e'))
    ax.grid(alpha=0.25)

    # ── Station count ────────────────────────────────────────────
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
    print("Validating...")
    stats = validate(df4, df5)
    print(f"  {stats['agreement']}")
    print(f"  Shared stations       : {len(stats['shared_sids']):,}")
    print(f"  Monthly cells compared: {stats['cells_compared']:,}")
    print(f"  NaN mismatches        : {stats['nan_mismatch']:,}")
    print(f"  Cells differing >1e-4 : {stats['cells_differ']:,}")
    print(f"  Max |diff| (°C)       : {stats['max_diff']:.2e}")
    print("Plotting...")
    plot(df4, df5, stats)
