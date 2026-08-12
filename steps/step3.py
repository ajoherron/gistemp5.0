"""
Step 3: Combine station records into 8000 equal-area subbox anomaly grid.

Matches gistemp4.0 step3 exactly:
  - Stations sorted by good_count descending before gridding
  - Each subbox collects stations within gridding_radius (1200 km)
  - Distance weight: 1 - chord/arc (chord on unit sphere)
  - Series combined with bias-corrected weighted merge (min_overlap=20)
  - Anomalized relative to 1951–1980 reference period
"""

import math

import numpy as np
import pandas as pd

from utils import eqarea
from utils.logger import logger

EARTH_RADIUS     = 6375.0  # matches gistemp4.0/steps/earth.py
GRIDDING_RADIUS  = 1200.0
MIN_OVERLAP      = 20
REFERENCE_PERIOD = (1951, 1980)

_META_COLS = {'Latitude', 'Longitude', '__LastGHCNYear__'}


def _build_flat_matrix(df, start_year, end_year):
    """Convert wide DataFrame to (n_stations, n_months) float64.

    Flat index: (year - start_year) * 12 + (month - 1).
    """
    n_months = (end_year - start_year + 1) * 12
    mat = np.full((len(df), n_months), np.nan, dtype=np.float64)
    for m in range(1, 13):
        for y in range(start_year, end_year + 1):
            col = f'{m}_{y}'
            if col in df.columns:
                fi = (y - start_year) * 12 + (m - 1)
                mat[:, fi] = df[col].values
    return mat


def _combine(comp, comp_wt, new_s, new_wt, min_overlap):
    """Bias-corrected weighted merge of new_s into comp.

    Mutates comp and comp_wt in-place.
    Matches gistemp4.0 series.combine() with NaN instead of MISSING.
    Returns list of 12 per-month combined counts.
    """
    counts = [0] * 12
    for m in range(12):
        c_sl = comp[m::12]
        n_sl = new_s[m::12]
        both = ~np.isnan(c_sl) & ~np.isnan(n_sl)
        n = int(both.sum())
        if n < min_overlap:
            continue
        # Sequential sum to match v4's scalar loop order (series.combine)
        c_vals = c_sl[both].tolist()
        n_vals = n_sl[both].tolist()
        bias = (sum(c_vals) - sum(n_vals)) / n
        valid_n = np.where(~np.isnan(n_sl))[0]
        if len(valid_n) == 0:
            continue
        fidx    = m + valid_n * 12
        old_wt  = comp_wt[fidx]
        new_total = old_wt + new_wt
        old_val = np.where(np.isnan(comp[fidx]), 0.0, comp[fidx])
        comp[fidx]    = (old_wt * old_val + new_wt * (new_s[fidx] + bias)) / new_total
        comp_wt[fidx] = new_total
        counts[m]     = len(valid_n)
    return counts


def _anomalize(series, start_year, ref_period=REFERENCE_PERIOD):
    """Anomalize flat monthly array in-place.

    Matches gistemp4.0 series.anomalize() with NaN instead of MISSING.
    Falls back to whole-series mean if reference period has no data.
    """
    ref_base = ref_period[0] - start_year
    ref_lim  = ref_period[1] - start_year + 1
    for m in range(12):
        idx = np.arange(m, len(series), 12)
        row = series[idx]
        ref_vals = row[ref_base:ref_lim]
        # Sequential sum to match v4's valid_mean scalar loop (series.anomalize)
        ref_valids = [v for v in ref_vals.tolist() if not math.isnan(v)]
        if ref_valids:
            mean = sum(ref_valids) / len(ref_valids)
        else:
            all_valids = [v for v in row.tolist() if not math.isnan(v)]
            if not all_valids:
                continue
            mean = sum(all_valids) / len(all_valids)
        valid_i = idx[~np.isnan(series[idx])]
        series[valid_i] -= mean


def step3(df, start_year, end_year, radius=GRIDDING_RADIUS):
    """Grid step2 station records into 8000 equal-area subboxes.

    Input:  wide station DataFrame (step2 output).
    Output: wide subbox DataFrame with columns:
              lat_s, lat_n, lon_w, lon_e, n_stations, station_months, d,
              {month}_{year} (monthly anomalies, NaN for empty/missing).
    """
    n_months = (end_year - start_year + 1) * 12

    logger.info("  Building flat series matrix…")
    mat = _build_flat_matrix(df, start_year, end_year)

    lats = df['Latitude'].astype(float).values
    lons = df['Longitude'].astype(float).values
    pi180  = math.pi / 180.0
    sn_lat = np.sin(lats * pi180)
    cs_lat = np.cos(lats * pi180)
    sn_lon = np.sin(lons * pi180)
    cs_lon = np.cos(lons * pi180)

    # Sort stations by good_count descending, stable to preserve original order on ties
    good_counts = np.sum(~np.isnan(mat), axis=1)
    order  = np.argsort(-good_counts, kind='stable')
    mat    = mat[order]
    sn_lat = sn_lat[order]
    cs_lat = cs_lat[order]
    sn_lon = sn_lon[order]
    cs_lon = cs_lon[order]

    arc     = radius / EARTH_RADIUS
    cos_arc = math.cos(arc)

    # Pre-allocate output: one row per subbox
    time_cols = [f'{m}_{y}'
                 for y in range(start_year, end_year + 1)
                 for m in range(1, 13)]
    n_subboxes = 8000
    data_mat   = np.full((n_subboxes, n_months), np.nan, dtype=np.float64)
    meta_rows  = []

    logger.info("  Gridding 8000 subboxes…")
    sb_i   = 0
    n_empty = 0

    for _box, subbox_gen in eqarea.gridsub():
        for subbox in subbox_gen:
            clat, clon = eqarea.centre(subbox)

            # Treat all polar subboxes as a single point (matches gistemp4.0)
            if round(clat) >= 84:
                clat, clon = 90.0, 0.0
            elif round(clat) <= -84:
                clat, clon = -90.0, 0.0

            c_sn     = math.sin(clat * pi180)
            c_cs     = math.cos(clat * pi180)
            c_sn_lon = math.sin(clon * pi180)
            c_cs_lon = math.cos(clon * pi180)

            cosd   = (sn_lat * c_sn +
                      cs_lat * c_cs * (cs_lon * c_cs_lon + sn_lon * c_sn_lon))
            in_idx = np.where(cosd > cos_arc)[0]

            meta = {'lat_s': subbox[0], 'lat_n': subbox[1],
                    'lon_w': subbox[2], 'lon_e': subbox[3]}

            if len(in_idx) == 0:
                n_empty += 1
                meta.update(n_stations=0, station_months=0, d=np.nan)
                meta_rows.append(meta)
                sb_i += 1
                continue

            # Distance weights: 1 - chord/arc
            c_cosd  = cosd[in_idx]
            chord   = np.sqrt(np.maximum(2.0 * (1.0 - c_cosd), 0.0))
            weights = 1.0 - chord / arc

            # Initialise composite with first contributor
            fi0   = in_idx[0]
            wt0   = float(weights[0])
            comp  = mat[fi0].copy()
            cwt   = np.where(~np.isnan(comp), wt0, 0.0)
            max_wt       = wt0
            tot_stations = 1
            tot_months   = int((~np.isnan(comp)).sum())

            # Merge remaining contributors
            for j in range(1, len(in_idx)):
                fi  = in_idx[j]
                wt  = float(weights[j])
                cnt = _combine(comp, cwt, mat[fi], wt, MIN_OVERLAP)
                n_merged = sum(cnt)
                if n_merged > 0:
                    tot_stations += 1
                    tot_months   += n_merged
                    max_wt        = max(max_wt, wt)

            _anomalize(comp, start_year)
            data_mat[sb_i] = comp

            meta.update(n_stations=tot_stations, station_months=tot_months,
                        d=radius * (1.0 - max_wt))
            meta_rows.append(meta)
            sb_i += 1

    logger.info(f"  Step 3 complete: {n_subboxes} subboxes, {n_empty} empty")

    df_meta = pd.DataFrame(meta_rows)
    df_time = pd.DataFrame(data_mat, columns=time_cols)
    df_out  = pd.concat([df_meta, df_time], axis=1)
    df_out.index.name = 'subbox_id'
    return df_out
