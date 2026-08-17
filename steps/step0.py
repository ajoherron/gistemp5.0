"""
Step 0: Download and format GHCN temperature data and metadata.

Output: DataFrame indexed by Station_ID with columns {month}_{year}
(e.g. "1_1880") for every month/year in [start_year, end_year],
plus Latitude and Longitude columns.
"""

import io
import os
import urllib.request

import numpy as np
import pandas as pd

from utils.logger import logger
from utils.config import INPUT_DIR


def _fetch_ghcn_temps(url: str, start_year: int, end_year: int):
    """
    Download and parse the GHCN temperature file.

    GHCN fixed-width format per line:
      cols  0-10  : Station_ID (11 chars)
      cols 11-14  : Year       (4 chars)
      cols 15-18  : Element    (4 chars, always TAVG for this file)
      then 12 groups of 8 chars each:
        cols 19+8k .. 23+8k : monthly value in 0.01 °C (-9999 = missing)
        cols 24+8k .. 26+8k : flags (ignored)

    Returns (df_temps, last_ghcn_year) where last_ghcn_year is a Series
    {Station_ID → last year with any GHCN file entry in [start_year, end_year]}.
    This matches gistemp4.0's station-record length for the December exclusion.
    """
    local_path = os.path.join(INPUT_DIR, 'ghcnm.tavg.qcf.dat')
    if not os.path.exists(local_path):
        logger.info("Downloading GHCN temperature data...")
        os.makedirs(INPUT_DIR, exist_ok=True)
        urllib.request.urlretrieve(url, local_path)
    else:
        logger.info("  GHCN temperature data: using cached file.")

    colspecs = [(0, 11), (11, 15)] + [(19 + 8 * i, 24 + 8 * i) for i in range(12)]
    names = ["Station_ID", "Year"] + [str(m) for m in range(1, 13)]

    df = pd.read_fwf(
        local_path,
        colspecs=colspecs,
        names=names,
        dtype={"Station_ID": str},
    )

    df = df[(df["Year"] >= start_year) & (df["Year"] <= end_year)].copy()

    # Record the last GHCN year per station BEFORE converting -9999 → NaN.
    # gistemp4.0's station series ends at this year (even if all values are
    # missing), and the December mean excludes that last December.
    last_ghcn_year = df.groupby("Station_ID")["Year"].max()

    month_cols = [str(m) for m in range(1, 13)]
    df[month_cols] = df[month_cols].replace(-9999, np.nan) / 100.0

    return df, last_ghcn_year


def _fetch_ghcn_meta(url: str) -> pd.DataFrame:
    """Download and parse GHCN station inventory (lat, lon only)."""
    local_path = os.path.join(INPUT_DIR, 'v4.inv')
    if not os.path.exists(local_path):
        logger.info("Downloading GHCN metadata...")
        os.makedirs(INPUT_DIR, exist_ok=True)
        urllib.request.urlretrieve(url, local_path)
    else:
        logger.info("  GHCN metadata: using cached file.")
    df = pd.read_fwf(
        local_path,
        widths=[11, 9, 10, 7, 3, 31],
        names=["Station_ID", "Latitude", "Longitude", "Elevation", "State", "Name"],
        dtype={"Station_ID": str},
    )
    return df[["Station_ID", "Latitude", "Longitude"]]


def step0(ghcn_temp_url: str, ghcn_meta_url: str, start_year: int, end_year: int) -> pd.DataFrame:
    """
    Download and format GHCN land temperature data.

    Returns a DataFrame indexed by Station_ID. Columns are {month}_{year}
    (e.g. "1_1880") sorted by year, followed by Latitude, Longitude, and
    __LastGHCNYear__ (last year with any GHCN file entry, used by step2 to
    correctly exclude the last December from the monthly mean calculation).
    Temperature values are in degrees Celsius; missing values are NaN.
    """
    df_temps, last_ghcn_year = _fetch_ghcn_temps(ghcn_temp_url, start_year, end_year)
    df_meta = _fetch_ghcn_meta(ghcn_meta_url)

    # Pivot to wide format: rows=Station_ID, multi-level cols=(month, year)
    df_wide = df_temps.pivot(index="Station_ID", columns="Year")

    # Flatten multi-level columns from ("1", 1880) → "1_1880"
    df_wide.columns = [f"{month}_{year}" for month, year in df_wide.columns]

    # Drop stations where every value is missing (matches gistemp4.0 behaviour)
    df_wide = df_wide.dropna(how="all")

    # Sort columns by year (stable sort preserves month order within each year)
    sorted_cols = sorted(df_wide.columns, key=lambda c: int(c.split("_")[1]))
    df_wide = df_wide[sorted_cols]

    # Merge in lat/lon
    df = df_wide.merge(
        df_meta.set_index("Station_ID"),
        left_index=True,
        right_index=True,
        how="left",
    )

    # Store last GHCN year per station; step2 uses this for the December exclusion.
    df['__LastGHCNYear__'] = last_ghcn_year

    logger.info(f"Step 0 complete: {len(df)} stations loaded ({start_year}–{end_year})")
    return df
