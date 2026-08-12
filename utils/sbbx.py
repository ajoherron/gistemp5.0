"""
Reader for GISTEMP SBBX (Fortran big-endian binary) subbox files.

File layout
-----------
Header record  : 8 big-endian int32  (mo1, kq, mavg, monm, monm4, yrbeg,
                                       missing_flag, precipitation_flag)
                 + 80 bytes title string
Subbox records : each record uses the mo1 from the *previous* record
                 (or the header mo1 for the first record) to determine
                 how many float32 series values it contains.
  Fields (big-endian): mo1_next(i), lat_S*100(i), lat_N*100(i),
                        lon_W*100(i), lon_E*100(i), stations(i),
                        station_months(i), d(f), series[cur_mo1](f)

Ocean subboxes have cur_mo1 = monm (full series).
Land placeholder subboxes have cur_mo1 = 1 (single MISSING value).

MISSING sentinel: 9999.0 → NaN on read.
"""

import math
import struct

import numpy as np
import pandas as pd

_BOS     = '>'       # big-endian (all SBBX files)
_MISSING = 9999.0


def _read_record(f):
    raw = f.read(4)
    if not raw or len(raw) < 4:
        return None
    length = struct.unpack(_BOS + 'i', raw)[0]
    data   = f.read(length)
    suffix = struct.unpack(_BOS + 'i', f.read(4))[0]
    assert suffix == length, f"Fortran record length mismatch: {length} vs {suffix}"
    return data


def read(path, start_year, end_year):
    """Read an SBBX file and return a wide subbox DataFrame.

    Output format matches step3:
      columns: lat_s, lat_n, lon_w, lon_e, n_stations, station_months, d,
               then {month}_{year} for every month in [start_year, end_year].
    MISSING (9999.0) becomes NaN.
    """
    time_cols = [f'{m}_{y}'
                 for y in range(start_year, end_year + 1)
                 for m in range(1, 13)]
    n_out = len(time_cols)

    with open(path, 'rb') as f:
        # ── Header ──────────────────────────────────────────────────
        hdr = _read_record(f)
        (mo1, kq, mavg, monm, monm4, yrbeg,
         missing_flag, precip_flag) = struct.unpack(_BOS + '8i', hdr[:32])

        meta_rows = []
        data_mat  = []
        cur_mo1   = mo1   # series length for the NEXT record to read

        # ── Subbox records ───────────────────────────────────────────
        while True:
            rec = _read_record(f)
            if rec is None:
                break

            fmt    = _BOS + f'iiiiiiif{cur_mo1}f'
            fields = struct.unpack(fmt, rec)

            # Update series length for the next record
            cur_mo1 = fields[0]

            lat_s   = fields[1] / 100.0
            lat_n   = fields[2] / 100.0
            lon_w   = fields[3] / 100.0
            lon_e   = fields[4] / 100.0
            n_sta   = fields[5]
            sta_mon = fields[6]
            d_raw   = fields[7]
            series  = fields[8:]

            meta_rows.append({
                'lat_s':          lat_s,
                'lat_n':          lat_n,
                'lon_w':          lon_w,
                'lon_e':          lon_e,
                'n_stations':     n_sta,
                'station_months': sta_mon,
                'd':              math.nan if d_raw == _MISSING else d_raw,
            })

            # Map series values to output time columns
            out = [math.nan] * n_out
            for fi, val in enumerate(series):
                if val == _MISSING:
                    continue
                yr = yrbeg + fi // 12
                mo = fi % 12 + 1
                if start_year <= yr <= end_year:
                    out[(yr - start_year) * 12 + (mo - 1)] = val
            data_mat.append(out)

    df_meta = pd.DataFrame(meta_rows)
    df_time = pd.DataFrame(data_mat, columns=time_cols, dtype=np.float64)
    df_out  = pd.concat([df_meta, df_time], axis=1)
    df_out.index.name = 'subbox_id'
    return df_out
