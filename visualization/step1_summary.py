"""
Visualize step 1 output: effect of quality-control filtering.

Requires cached step 0 and step 1 outputs. Run from repo root:
    python main/run.py
Then:
    python visualization/step1_summary.py
"""

import os
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from parameters.constants import START_YEAR, END_YEAR
from tools import cache as step_cache

OUT_PATH = os.path.join(REPO_ROOT, 'visualization', 'step1_summary.png')

META_COLS = {'Latitude', 'Longitude', '__LastGHCNYear__'}


def load_data():
    df0 = step_cache.load('step0', START_YEAR, END_YEAR)
    df1 = step_cache.load('step1', START_YEAR, END_YEAR)
    if df0 is None or df1 is None:
        raise FileNotFoundError(
            "step0/step1 cache missing. Run: python main/run.py"
        )
    return df0, df1


def time_cols(df):
    return [c for c in df.columns if c not in META_COLS]


def valid_cells_per_year(df, tc_set):
    years = list(range(START_YEAR, END_YEAR + 1))
    tc_list = sorted(tc_set)
    valid = df[tc_list].notna()
    # Group columns by year and sum
    year_of = pd.Series({c: int(c.split('_')[1]) for c in tc_list})
    counts = valid.sum(axis=0).groupby(year_of).sum()
    return counts.reindex(years, fill_value=0)


def plot(df0, df1):
    tc0 = set(time_cols(df0))
    tc1 = set(time_cols(df1))
    shared_tc = tc0 & tc1

    dropped_sids = sorted(set(df0.index) - set(df1.index))
    common_sids  = sorted(set(df0.index) & set(df1.index))
    shared_tc_l  = sorted(shared_tc)
    null0 = df0.loc[common_sids, shared_tc_l].isna().sum(axis=1)
    null1 = df1.loc[common_sids, shared_tc_l].isna().sum(axis=1)
    nulled_sids = sorted((null1 > null0)[null1 > null0].index)

    cells0 = valid_cells_per_year(df0, tc0)
    cells1 = valid_cells_per_year(df1, tc1)
    cells_removed = cells0 - cells1

    fig, axes = plt.subplots(2, 2, figsize=(16, 10))
    fig.suptitle(f'Step 1: Quality-Control Filtering ({START_YEAR}–{END_YEAR})',
                 fontsize=14, fontweight='bold')

    # ── Valid data cells before vs after ───────────────────────
    ax = axes[0, 0]
    ax.fill_between(cells0.index, cells0.values, color='#1565C0', alpha=0.4, label='After step 0')
    ax.fill_between(cells1.index, cells1.values, color='#2E7D32', alpha=0.5, label='After step 1')
    ax.set_title('Valid Station-Months per Year', fontsize=12)
    ax.set_ylabel('Valid monthly readings')
    ax.set_xlabel('Year')
    ax.set_xlim(START_YEAR, END_YEAR)
    ax.legend(fontsize=9)
    ax.grid(alpha=0.25)

    # ── Cells removed per year ──────────────────────────────────
    ax = axes[0, 1]
    ax.fill_between(cells_removed.index, cells_removed.values, color='#E53935', alpha=0.6)
    ax.plot(cells_removed.index, cells_removed.values, color='#E53935', lw=1)
    ax.set_title('Valid Station-Months Removed by Step 1', fontsize=12)
    ax.set_ylabel('Readings nulled')
    ax.set_xlabel('Year')
    ax.set_xlim(START_YEAR, END_YEAR)
    ax.grid(alpha=0.25)
    total_removed = int(cells_removed.sum())
    ax.text(0.98, 0.95, f'Total removed: {total_removed:,}',
            transform=ax.transAxes, ha='right', va='top', fontsize=9,
            bbox=dict(boxstyle='round', facecolor='white', alpha=0.7))

    # ── Dropped stations (map) ──────────────────────────────────
    ax = axes[1, 0]
    lat_all = df0['Latitude'].astype(float)
    lon_all = df0['Longitude'].astype(float)
    ax.scatter(lon_all, lat_all, color='#BDBDBD', s=1, alpha=0.3, label='All stations')

    if dropped_sids:
        lat_d = df0.loc[dropped_sids, 'Latitude'].astype(float)
        lon_d = df0.loc[dropped_sids, 'Longitude'].astype(float)
        ax.scatter(lon_d, lat_d, color='#E53935', s=60, zorder=5,
                   label=f'Dropped ({len(dropped_sids)})', marker='x', linewidths=2)

    if nulled_sids:
        lat_n = df0.loc[nulled_sids, 'Latitude'].astype(float)
        lon_n = df0.loc[nulled_sids, 'Longitude'].astype(float)
        ax.scatter(lon_n, lat_n, color='#FF6F00', s=40, zorder=4,
                   label=f'Partially nulled ({len(nulled_sids)})', marker='^')

    ax.set_title('Affected Stations', fontsize=12)
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_xlim(-180, 180)
    ax.set_ylim(-90, 90)
    ax.axhline(0, color='gray', lw=0.5, ls='--')
    ax.legend(fontsize=9, markerscale=1.5)
    ax.grid(alpha=0.2)

    # ── Summary table ───────────────────────────────────────────
    ax = axes[1, 1]
    ax.axis('off')
    rows = [
        ['Stations in step 0',       f'{len(df0):,}'],
        ['Stations in step 1',        f'{len(df1):,}'],
        ['Stations dropped',          f'{len(dropped_sids)}'],
        ['Stations partially nulled', f'{len(nulled_sids)}'],
        ['Total valid cells (step 0)', f'{int(cells0.sum()):,}'],
        ['Total valid cells (step 1)', f'{int(cells1.sum()):,}'],
        ['Valid cells removed',        f'{total_removed:,}'],
        ['% data removed',             f'{total_removed / cells0.sum() * 100:.4f}%'],
    ]
    table = ax.table(cellText=rows, colLabels=['Metric', 'Value'],
                     cellLoc='left', loc='center', colWidths=[0.65, 0.35])
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 1.6)
    for (r, c), cell in table.get_celld().items():
        if r == 0:
            cell.set_facecolor('#1565C0')
            cell.set_text_props(color='white', fontweight='bold')
        elif r % 2 == 0:
            cell.set_facecolor('#F5F5F5')
        cell.set_edgecolor('white')
    ax.set_title('Step 1 Summary', fontsize=12, pad=20)

    plt.tight_layout()
    plt.savefig(OUT_PATH, dpi=150, bbox_inches='tight')
    print(f"  Saved → {OUT_PATH}")


if __name__ == '__main__':
    print("Loading step 0 and step 1 data...")
    df0, df1 = load_data()
    print(f"  step 0: {len(df0):,} stations")
    print(f"  step 1: {len(df1):,} stations")
    print("Plotting...")
    plot(df0, df1)
