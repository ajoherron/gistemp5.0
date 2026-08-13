"""
Step 4: Load ERSSTv5 ocean subbox anomalies.

Reads the pre-computed SBBX.ERSSTv5 binary file and returns a wide
DataFrame in the same format as step3 (8000 equal-area subboxes).

Matches gistemp4.0 step4 exactly:
  - Same Fortran big-endian binary reader logic
  - MISSING (9999.0) → NaN
  - Subbox ordering identical to step3 land output (zip-compatible)
  - Monthlies (oiv2mon.YYYYMM) extended if present in input_dir
"""

import math
import os
import re
import struct

import numpy as np
import pandas as pd

from utils import sbbx
from utils.logger import logger
from utils.config import SBBX_URL, INPUT_DIR

_BOS               = '>'
_MISSING           = 9999.0
_SEA_CUTOFF        = -1.77   # matches gistemp4.0 parameters.sea_surface_cutoff_temp
_MONTHLY_RE        = re.compile(r'^oiv2mon\.(\d{4})(\d{2})(\.gz)?$')


def _find_monthlies(input_dir, end_year, end_month):
    """Return sorted list of (year, month, path) for oiv2mon files newer than end_year/end_month."""
    entries = []
    if not os.path.isdir(input_dir):
        return entries
    for name in os.listdir(input_dir):
        m = _MONTHLY_RE.match(name)
        if not m:
            continue
        yr, mo = int(m.group(1)), int(m.group(2))
        if (yr, mo) > (end_year, end_month):
            path = os.path.join(input_dir, name if not m.group(3) else name[:-3])
            entries.append((yr, mo, path))
    entries.sort()
    return entries


def _load_monthlies(entries):
    """Load oiv2mon Fortran binary files into a 3-D array sst[lon][lat][month].

    sst array shape: [360][180][n_months] where n_months covers the range of
    files found.  Indexed by: lon in [0,359], lat in [0,179].
    """
    if not entries:
        return None
    first_yr = entries[0][0]
    last_yr  = entries[-1][0]
    n_months = (last_yr - first_yr + 1) * 12

    # Build 3-D list (matches gistemp4.0's make_3d_array(360, 180, n_months))
    sst = [[([_MISSING] * n_months) for _ in range(180)] for _ in range(360)]

    dates = []
    for yr, mo, path in entries:
        dates.append((yr, mo))
        with open(path, 'rb') as f:
            # Two Fortran records; data is in the second
            r1_len = struct.unpack(_BOS + 'i', f.read(4))[0]
            f.read(r1_len); f.read(4)
            r2_len = struct.unpack(_BOS + 'i', f.read(4))[0]
            data   = f.read(r2_len); f.read(4)

        mi = 12 * (yr - first_yr) + mo - 1
        p  = 0
        for lat in range(180):
            for lon in range(360):
                v, = struct.unpack('>f', data[p:p + 4])
                p += 4
                sst[lon][lat][mi] = v

    return sst, dates, first_yr


def _merge_monthlies(df_ocean, sst, dates, first_yr, start_year):
    """Extend ocean DataFrame with values from oiv2mon monthlies.

    Matches gistemp4.0 step4.merge_ocean():
      - Averages 1°×1° cells within each subbox
      - Excludes values below sea_surface_cutoff_temp (-1.77°C)
    """
    df = df_ocean.copy()
    for yr, mo in dates:
        col = f'{mo}_{yr}'
        if col not in df.columns:
            continue
        mi = 12 * (yr - first_yr) + mo - 1
        vals_col = []
        for _, row in df[['lat_s', 'lat_n', 'lon_w', 'lon_e']].iterrows():
            js = int(row['lat_s'] + 90.01)
            jn = int(row['lat_n'] + 89.99)
            iw = int(row['lon_w'] + 360.01)
            ie = int(row['lon_e'] + 359.99)
            if ie >= 360:
                iw -= 360
                ie -= 360
            total, count = 0.0, 0
            for j in range(js, jn + 1):
                for i in range(iw, ie + 1):
                    v = sst[i][j][mi]
                    if v >= _SEA_CUTOFF:
                        total += v
                        count += 1
            vals_col.append(total / count if count > 0 else math.nan)
        df[col] = vals_col
    return df


def _sbbx_end_date(path):
    """Parse end year/month from SBBX title string."""
    with open(path, 'rb') as f:
        length = struct.unpack(_BOS + 'i', f.read(4))[0]
        hdr    = f.read(length)
    title = hdr[32:112].decode('utf-8')
    m = re.search(r'(\d+)/(\d{4})\s*$', title.strip())
    if m:
        return int(m.group(2)), int(m.group(1))
    return None, None


def step4(sbbx_path, start_year, end_year, input_dir=None):
    """Load ERSSTv5 ocean subboxes, optionally extended with monthlies.

    Parameters
    ----------
    sbbx_path  : path to SBBX.ERSSTv5 (or equivalent)
    start_year : first year of output time columns
    end_year   : last year of output time columns
    input_dir  : directory to search for oiv2mon.YYYYMM files (optional)

    Returns
    -------
    DataFrame with 8000 rows in the same format as step3 output.
    """
    if not os.path.exists(sbbx_path):
        import gzip, shutil, urllib.request
        gz_path = sbbx_path + '.gz'
        logger.info(f"  Downloading SBBX.ERSSTv5 …")
        os.makedirs(INPUT_DIR, exist_ok=True)
        urllib.request.urlretrieve(SBBX_URL, gz_path)
        with gzip.open(gz_path, 'rb') as f_in, open(sbbx_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        os.remove(gz_path)

    logger.info(f"  Reading SBBX ocean file: {os.path.basename(sbbx_path)}")
    df_ocean = sbbx.read(sbbx_path, start_year, end_year)

    # Check for monthlies that extend beyond the SBBX file's last record
    if input_dir is not None:
        sbbx_ey, sbbx_em = _sbbx_end_date(sbbx_path)
        if sbbx_ey is not None:
            entries = _find_monthlies(input_dir, sbbx_ey, sbbx_em)
            if entries:
                logger.info(f"  Merging {len(entries)} monthly SST file(s)…")
                sst, dates, first_yr = _load_monthlies(entries)
                df_ocean = _merge_monthlies(df_ocean, sst, dates, first_yr, start_year)
            else:
                logger.info("  No additional monthly SST files found.")

    meta_cols = {'lat_s', 'lat_n', 'lon_w', 'lon_e', 'n_stations', 'station_months', 'd'}
    tc = [c for c in df_ocean.columns if c not in meta_cols]
    n_ocean = int((~df_ocean[tc].isna().all(axis=1)).sum())
    logger.info(f"  Step 4 complete: {len(df_ocean):,} subboxes, {n_ocean:,} with ocean data")
    return df_ocean
