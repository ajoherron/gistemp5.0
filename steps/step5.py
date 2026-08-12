"""
Step 5: Combine land+ocean subboxes into 80 boxes, then into 16 zonal/global averages.

Two separate analyses are produced:
  land  — uses only step 3 land subbox data
  mixed — uses land or ocean per subbox based on a coverage/distance mask

Port of gistemp4.0/steps/step5.py.  All series arithmetic uses scalar Python
(utils/series.py) to match v4's sequential summation exactly.
"""

import math

import numpy as np
import pandas as pd

from utils import eqarea
from utils.series import MISSING, valid, combine, anomalize

# ── Parameters (matching gistemp4.0/parameters/standard.py) ──────────────────
_SUBBOX_MIN_VALID       = 240
_SUBBOX_LAND_RANGE      = 100        # km: prefer land when d < this
_SUBBOX_REF_PERIOD      = (1961, 1990)
_BOX_MIN_OVERLAP        = 20
_BOX_REF_PERIOD         = (1951, 1980)
_ZONE_ANNUAL_MIN_MONTHS = 6

# 80 large boxes in eqarea.grid() order
_BOXES = list(eqarea.grid())

# Boxes per latitudinal band (sums to 80)
_BOXES_IN_BAND = [4, 8, 12, 16, 16, 12, 8, 4]

# Which primary bands (0-7) compose each compound zone (8-15)
_N = frozenset(range(4))
_G = frozenset(range(8))
_S = _G - _N
_T = frozenset({3, 4})
_BAND_IN_ZONE = [_N - _T, _T, _S - _T, {1, 2}, {5, 6}, _N, _S, _G]

_META = {'lat_s', 'lat_n', 'lon_w', 'lon_e', 'n_stations', 'station_months', 'd'}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _time_cols(df):
    return [c for c in df.columns if c not in _META]


def _col_index_map(tc, yrbeg, monm):
    """Pre-compute {col: flat_index} for all time columns in range."""
    mapping = {}
    for c in tc:
        mo_str, yr_str = c.split('_')
        idx = (int(yr_str) - yrbeg) * 12 + (int(mo_str) - 1)
        if 0 <= idx < monm:
            mapping[c] = idx
    return mapping


def _extract_all_series(df, tc, col_map, monm):
    """Extract every row as a MISSING-padded list[float] of length monm.

    Uses numpy for the read pass (no arithmetic), then converts to Python lists
    for the downstream scalar combine/anomalize calls.
    """
    vals    = df[tc].values          # (n_rows, n_tc), float64, NaN for missing
    col_ids = [col_map.get(c, -1) for c in tc]
    n_rows  = len(vals)
    result  = [[MISSING] * monm for _ in range(n_rows)]
    for ci, idx in enumerate(col_ids):
        if idx < 0:
            continue
        col_vals = vals[:, ci]
        for ri in range(n_rows):
            v = col_vals[ri]
            if not math.isnan(v):
                result[ri][idx] = v
    return result


def _whichbox(cell):
    """Index into _BOXES for the large-box that contains the centre of *cell*."""
    lat, lon = eqarea.centre(cell)
    for idx, (s, n, w, e) in enumerate(_BOXES):
        if s <= lat < n and w <= lon < e:
            return idx
    return None


def _sort_perm(a):
    """Descending sort; returns (sorted_values, original_indices).
    Key is (index - value), matching gistemp4.0/steps/step5.py::sort_perm exactly.
    """
    z = sorted(zip(a, range(len(a))), key=lambda x: x[1] - x[0])
    data, indexes = zip(*z)
    return list(data), list(indexes)


# ── Stage 1: land/ocean mask ──────────────────────────────────────────────────

def _ensure_weight(df_land, df_ocean, tc_ocean):
    """Boolean array (len 8000): True = use land, False = use ocean.

    Use land when: ocean_good_count < _SUBBOX_MIN_VALID  OR  land.d < _SUBBOX_LAND_RANGE.
    Port of gistemp4.0/steps/step5.py::ensure_weight.
    """
    ocean_good = (~df_ocean[tc_ocean].isna()).sum(axis=1).values
    land_d     = df_land['d'].values
    # NaN d means no nearby station — don't force land preference (NaN < 100 is False)
    use_land   = (ocean_good < _SUBBOX_MIN_VALID) | (land_d < _SUBBOX_LAND_RANGE)
    return use_land


# ── Stage 2: 8000 subboxes → 80 boxes ────────────────────────────────────────

def _subbox_to_box(series_list, df_meta, yrbeg, monm):
    """Aggregate 8000 subbox series into 80 box time series.

    *series_list*: list of 8000 MISSING-padded Python lists (from _extract_all_series).
    *df_meta*: DataFrame with lat_s/n, lon_w/e, d columns (aligned with series_list).

    Returns list of 80 dicts: {series, weight, ngood, box}.
    """
    # Assign each subbox to its large-box and compute good_count
    box_contributors = [[] for _ in range(80)]
    for i, s in enumerate(series_list):
        gc = sum(1 for v in s if valid(v))
        row = df_meta.iloc[i]
        cell = (row['lat_s'], row['lat_n'], row['lon_w'], row['lon_e'])
        bidx = _whichbox(cell)
        if bidx is not None:
            box_contributors[bidx].append((gc, i))

    results = []
    for bidx, contributors in enumerate(box_contributors):
        contributors.sort(key=lambda x: x[0], reverse=True)

        box_series = [MISSING] * monm
        box_weight = [0.0]    * monm

        if contributors:
            # Seed with the best subbox
            best_gc, best_i = contributors[0]
            src = series_list[best_i]
            for j, v in enumerate(src):
                if valid(v):
                    box_series[j] = v
                    box_weight[j] = 1.0

            # Combine remaining contributors
            for gc, sub_i in contributors[1:]:
                if gc < _SUBBOX_MIN_VALID:
                    continue
                combine(box_series, box_weight, series_list[sub_i], 1.0, _BOX_MIN_OVERLAP)

        anomalize(box_series, _SUBBOX_REF_PERIOD, yrbeg)
        ngood = sum(1 for v in box_series if valid(v))
        results.append({'series': box_series, 'weight': box_weight,
                        'ngood': ngood, 'box': _BOXES[bidx]})

    return results


# ── Stage 3: 80 boxes → 16 zones ─────────────────────────────────────────────

def _zonav(boxes, yrbeg, monm):
    """16 zonal averages from 80 box records.

    First 8 zones are primary latitudinal bands; next 8 are compound zones.
    Returns list of 16 (avg_series, wt_series) pairs.
    Port of gistemp4.0/steps/step5.py::zonav.
    """
    band_avgs, band_wts = [], []
    box_iter = iter(boxes)

    for n_boxes in _BOXES_IN_BAND:
        band_data = [next(box_iter) for _ in range(n_boxes)]
        lengths   = [b['ngood'] for b in band_data]

        if sum(lengths) == 0:
            avg = [MISSING] * monm
            wt  = [0.0]     * monm
        else:
            lengths_s, iord = _sort_perm(lengths)
            avg = list(band_data[iord[0]]['series'])
            wt  = list(band_data[iord[0]]['weight'])
            for j in range(1, n_boxes):
                if lengths_s[j] == 0:
                    break
                b = band_data[iord[j]]
                combine(avg, wt, b['series'], b['weight'], _BOX_MIN_OVERLAP)

        anomalize(avg, _BOX_REF_PERIOD, yrbeg)
        band_avgs.append(avg)
        band_wts.append(wt)

    # Compound zones (8 additional zones)
    lenz = [sum(1 for v in a if valid(v)) for a in band_avgs]
    lenz_s, iord = _sort_perm(lenz)

    zone_results = list(zip(band_avgs, band_wts))  # zones 0-7

    for band_set in _BAND_IN_ZONE:
        j1 = next(j for j in range(8) if iord[j] in band_set)
        avgg = list(band_avgs[iord[j1]])
        wtg  = list(band_wts[iord[j1]])
        for j in range(j1 + 1, 8):
            band = iord[j]
            if band not in band_set:
                continue
            combine(avgg, wtg, band_avgs[band], band_wts[band], _BOX_MIN_OVERLAP)
        anomalize(avgg, _BOX_REF_PERIOD, yrbeg)
        zone_results.append((avgg, wtg))

    return zone_results  # 16 entries


# ── Stage 4: monthly → annual ─────────────────────────────────────────────────

def _annzon(zones, yrbeg, monm):
    """Annual zonal means from 16 monthly zone series.

    Returns (monthly_data, annual_data):
      monthly_data[zone][year][month]
      annual_data[zone][year]

    Port of gistemp4.0/steps/step5.py::annzon with alternate global and hemi.
    """
    n_zones = 16
    iyrs    = monm // 12

    data = []
    for zone_idx in range(n_zones):
        tdata, _ = zones[zone_idx]
        data.append(list(zip(*[iter(tdata)] * 12)))  # reshape to [year][month]

    ann = [[MISSING] * iyrs for _ in range(n_zones)]

    for zone in range(n_zones):
        for iy in range(iyrs):
            total = 0.0
            mon   = 0
            for m in range(12):
                v = data[zone][iy][m]
                if v == MISSING:
                    continue
                mon   += 1
                total += v
            if mon >= _ZONE_ANNUAL_MIN_MONTHS:
                ann[zone][iy] = total / mon

    # Alternate global (method 2): zones [8,3,4,10], weights [3,2,2,3], scale 0.1
    alt_zones   = [8, 3, 4, 10]
    alt_weights = [3., 2., 2., 3.]
    for iy in range(iyrs):
        ann[-1][iy] = MISSING
        glob = 0.0
        for z, w in zip(alt_zones, alt_weights):
            if ann[z][iy] == MISSING:
                break
            glob += ann[z][iy] * w
        else:
            ann[-1][iy] = 0.1 * glob

    data[-1] = [[MISSING] * 12 for _ in range(iyrs)]
    for iy in range(iyrs):
        for m in range(12):
            glob = 0.0
            for z, w in zip(alt_zones, alt_weights):
                if data[z][iy][m] == MISSING:
                    break
                glob += data[z][iy][m] * w
            else:
                data[-1][iy][m] = 0.1 * glob

    # Alternate hemispheric: 0.4 * tropical + 0.6 * extratropical
    # NH (zone 11): trop=zone 3, polar=zone 8
    # SH (zone 12): trop=zone 4, polar=zone 10
    for ihem in range(2):
        trop  = ihem + 3
        polar = 2 * ihem + 8
        out   = ihem + 11
        for iy in range(iyrs):
            ann[out][iy] = MISSING
            if ann[trop][iy] != MISSING and ann[polar][iy] != MISSING:
                ann[out][iy] = 0.4 * ann[trop][iy] + 0.6 * ann[polar][iy]
        data[out] = [[MISSING] * 12 for _ in range(iyrs)]
        for iy in range(iyrs):
            for m in range(12):
                if data[trop][iy][m] != MISSING and data[polar][iy][m] != MISSING:
                    data[out][iy][m] = (0.4 * data[trop][iy][m]
                                        + 0.6 * data[polar][iy][m])

    return data, ann


# ── Output helpers ────────────────────────────────────────────────────────────

def _to_dataframes(data, ann, yrbeg, monm):
    """Convert annzon outputs to (annual_df, monthly_df)."""
    n_zones   = len(ann)
    iyrs      = monm // 12
    zone_cols = [f'zone_{i}' for i in range(n_zones)]
    years     = list(range(yrbeg, yrbeg + iyrs))

    annual_df = pd.DataFrame(
        [[float('nan') if ann[z][iy] == MISSING else ann[z][iy]
          for z in range(n_zones)]
         for iy in range(iyrs)],
        index=pd.Index(years, name='year'),
        columns=zone_cols,
    )

    rows, idx = [], []
    for iy in range(iyrs):
        yr = yrbeg + iy
        for m in range(12):
            rows.append([float('nan') if data[z][iy][m] == MISSING else data[z][iy][m]
                         for z in range(n_zones)])
            idx.append((yr, m + 1))

    monthly_df = pd.DataFrame(
        rows,
        index=pd.MultiIndex.from_tuples(idx, names=['year', 'month']),
        columns=zone_cols,
    )
    return annual_df, monthly_df


# ── Public entry point ────────────────────────────────────────────────────────

def step5(df_land, df_ocean, start_year, end_year):
    """Run step 5: produce land-only and mixed land+ocean zonal/global anomalies.

    Returns:
        {
          'land':  {'annual': DataFrame, 'monthly': DataFrame},
          'mixed': {'annual': DataFrame, 'monthly': DataFrame},
        }

    Columns zone_0…zone_15 match gistemp4.0's 16 zones (8 primary bands + 8 compound).
    Annual index: year.  Monthly index: (year, month).
    """
    tc_land  = _time_cols(df_land)
    tc_ocean = _time_cols(df_ocean)

    # Common time axis spanning both land and ocean data
    all_years = (sorted({int(c.split('_')[1]) for c in tc_land}) +
                 sorted({int(c.split('_')[1]) for c in tc_ocean}))
    yrbeg = min(all_years)
    yrend = max(all_years)
    monm  = (yrend - yrbeg + 1) * 12

    df_land  = df_land.reset_index(drop=True)
    df_ocean = df_ocean.reset_index(drop=True)

    # Stage 1: land/ocean mask
    use_land = _ensure_weight(df_land, df_ocean, tc_ocean)

    # Mixed DataFrame: swap ocean rows where use_land is False
    df_mixed = df_land.copy()
    ocean_mask = ~use_land
    if ocean_mask.any():
        df_mixed.loc[ocean_mask] = df_ocean.loc[ocean_mask].values

    df_meta = df_land[['lat_s', 'lat_n', 'lon_w', 'lon_e', 'd']]

    results = {}
    for mode, df_sub in [('land', df_land), ('mixed', df_mixed)]:
        tc      = _time_cols(df_sub)
        col_map = _col_index_map(tc, yrbeg, monm)
        series_list = _extract_all_series(df_sub, tc, col_map, monm)
        boxes   = _subbox_to_box(series_list, df_meta, yrbeg, monm)
        zones   = _zonav(boxes, yrbeg, monm)
        data, ann = _annzon(zones, yrbeg, monm)
        annual_df, monthly_df = _to_dataframes(data, ann, yrbeg, monm)
        results[mode] = {'annual': annual_df, 'monthly': monthly_df}

    return results
