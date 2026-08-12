"""
Step 1: Apply drop rules from Ts.strange.v4.list.IN_full.

Certain station records, or portions of them, are set to NaN based on
the GISTEMP quality-control configuration file. Matches gistemp4.0
step1 / drop_strange logic exactly.
"""

import requests
import pandas as pd

from utils.logger import logger


def _fetch_changes(url: str) -> dict:
    """
    Parse Ts.strange.v4.list.IN_full into a changes dict.

    Each line's last whitespace-separated token is either:
      "YYYY/MM"  → ('month', year, month)
      "Y1-Y2"    → ('years', year1, year2)

    Returns {station_id: [entry, ...]}
    """
    response = requests.get(url)
    response.raise_for_status()

    changes = {}
    for line in response.text.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split()
        station_id = parts[0]
        token = parts[-1]

        if '/' in token:
            yr, mo = map(int, token.split('/'))
            entry = ('month', yr, mo)
        else:
            y1, y2 = map(int, token.split('-'))
            entry = ('years', y1, y2)

        changes.setdefault(station_id, []).append(entry)

    return changes


def step1(df: pd.DataFrame, strange_url: str, start_year: int, end_year: int) -> pd.DataFrame:
    """
    Apply drop rules from Ts.strange.v4.list.IN_full.

    Drops entire station rows or NaN-s specific month/year ranges,
    matching gistemp4.0 drop_strange() behaviour exactly.
    """
    logger.info("Downloading Ts.strange.v4.list.IN_full...")
    changes = _fetch_changes(strange_url)

    df = df.copy()
    to_drop = []

    for station_id, entries in changes.items():
        if station_id not in df.index:
            continue

        for (kind, val1, val2) in entries:
            if kind == 'years':
                year1, year2 = val1, val2

                # Drop entire station if range covers the full data span
                if year1 <= start_year and year2 >= end_year:
                    to_drop.append(station_id)
                    break

                # Clamp to data range (mirrors gistemp4.0's max/min logic)
                year1 = max(year1, start_year)
                year2 = min(year2, end_year)

                if year2 < year1:
                    continue

                cols = [
                    f'{mo}_{yr}'
                    for yr in range(year1, year2 + 1)
                    for mo in range(1, 13)
                    if f'{mo}_{yr}' in df.columns
                ]
                df.loc[station_id, cols] = float('nan')

            else:  # 'month'
                yr, mo = val1, val2
                col = f'{mo}_{yr}'
                if col in df.columns:
                    df.loc[station_id, col] = float('nan')

    df = df.drop(index=to_drop)

    logger.info(
        f"Step 1 complete: {len(to_drop)} stations dropped, "
        f"{len(changes) - len(to_drop)} partially nulled"
    )
    return df
