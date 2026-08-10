"""
Visualize step 0 output: raw GHCN station network.

Requires cached step 0 output. Run from repo root:
    python main/run.py
Then:
    python visualization/step0_summary.py
"""

import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from parameters.constants import START_YEAR, END_YEAR
from tools import cache as step_cache

OUT_PATH = os.path.join(REPO_ROOT, 'visualization', 'step0_summary.png')


def load_data():
    df = step_cache.load('step0', START_YEAR, END_YEAR)
    if df is None:
        raise FileNotFoundError(
            f"step0 cache missing for {START_YEAR}–{END_YEAR}.\n"
            "Run: python main/run.py"
        )
    return df


def time_cols(df):
    return [c for c in df.columns if c not in ('Latitude', 'Longitude', '__LastGHCNYear__')]


def station_count_per_year(df, tc):
    years = range(START_YEAR, END_YEAR + 1)
    counts = []
    for yr in years:
        cols = [f'{m}_{yr}' for m in range(1, 13) if f'{m}_{yr}' in tc]
        if cols:
            counts.append(int(np.any(~df[cols].isna().values, axis=1).sum()))
        else:
            counts.append(0)
    return pd.Series(counts, index=list(years))


def valid_months_per_station(df, tc):
    return df[tc].notna().sum(axis=1)


def plot(df):
    tc = set(time_cols(df))
    counts = station_count_per_year(df, tc)
    valid_months = valid_months_per_station(df, list(tc))

    fig = plt.figure(figsize=(16, 12))
    fig.suptitle(f'Step 0: Raw GHCN Station Network ({START_YEAR}–{END_YEAR})',
                 fontsize=14, fontweight='bold')

    gs = fig.add_gridspec(2, 2, hspace=0.38, wspace=0.3)

    # ── Station count per year ──────────────────────────────────
    ax = fig.add_subplot(gs[0, :])
    ax.fill_between(counts.index, counts.values, color='#1565C0', alpha=0.5)
    ax.plot(counts.index, counts.values, color='#1565C0', lw=1.5)
    ax.set_title('Active Stations per Year', fontsize=12)
    ax.set_ylabel('Stations with ≥1 valid month')
    ax.set_xlabel('Year')
    ax.set_xlim(START_YEAR, END_YEAR)
    ax.grid(alpha=0.25)
    ax.annotate(f'Peak: {counts.max():,} ({counts.idxmax()})',
                xy=(counts.idxmax(), counts.max()),
                xytext=(counts.idxmax() - 30, counts.max() - 800),
                arrowprops=dict(arrowstyle='->', color='black'),
                fontsize=9)

    # ── Geographic distribution ─────────────────────────────────
    ax = fig.add_subplot(gs[1, 0])
    lat = df['Latitude'].astype(float)
    lon = df['Longitude'].astype(float)
    record_len = valid_months.values
    sc = ax.scatter(lon, lat, c=record_len, cmap='YlOrRd', s=1.5, alpha=0.6,
                    vmin=0, vmax=record_len.max())
    plt.colorbar(sc, ax=ax, label='Valid months in record', shrink=0.85)
    ax.set_title('Station Locations (colored by record length)', fontsize=12)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.axhline(0, color='gray', lw=0.5, ls='--')
    ax.grid(alpha=0.2)

    # ── Record length distribution ──────────────────────────────
    ax = fig.add_subplot(gs[1, 1])
    max_months = (END_YEAR - START_YEAR + 1) * 12
    pct_complete = (record_len / max_months) * 100
    ax.hist(pct_complete, bins=40, color='#1565C0', alpha=0.7, edgecolor='white', lw=0.4)
    ax.axvline(pct_complete.mean(), color='#E53935', lw=1.5, ls='--',
               label=f'Mean: {pct_complete.mean():.1f}%')
    ax.set_title('Station Record Completeness', fontsize=12)
    ax.set_xlabel(f'% of {START_YEAR}–{END_YEAR} months with valid data')
    ax.set_ylabel('Number of stations')
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25, axis='y')

    plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight')
    print(f"  Saved → {OUT_PATH}")


if __name__ == '__main__':
    print("Loading step 0 data...")
    df = load_data()
    print(f"  {len(df):,} stations loaded")
    print("Plotting...")
    plot(df)
