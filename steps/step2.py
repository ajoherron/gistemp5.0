"""
Step 2: Drop short records and apply urban heat-island adjustment.

Matches gistemp4.0 step2 exactly:
  - drop_short_records: stations with max monthly valid count < 20 are dropped
  - urban_adjustments: urban stations are adjusted using nearby rural station
    anomalies or dropped if no suitable rural neighbourhood can be found
"""

import math
import os

import numpy as np
import pandas as pd

from utils.logger import logger
from utils.config import INPUT_DIR

# ── Constants (matching gistemp4.0/parameters/standard.py) ───────────────────
BASE_YEAR = 1880
EARTH_RADIUS = 6375.0                        # km (gistemp4.0 earth.radius)

STATION_DROP_MIN_MONTHS = 20
RURAL_LIGHT_THRESHOLD = 10                   # global_light <= 10 → rural
URBAN_FULL_RADIUS = 1000.0                   # km; half tried first
URBAN_MIN_YEARS = 20
URBAN_PROPORTION_GOOD = 2.0 / 3.0
URBAN_MIN_RURAL_STATIONS = 3
URBAN_MIN_LEG = 5
URBAN_SHORT_LEG = 7
URBAN_STEEP_LEG = 0.1
URBAN_REVERSE_GRADIENT = 0.02
RURAL_MIN_OVERLAP = 20

_INF_RMS = 1e20


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _read_global_light_from_augmented_inv(path: str) -> pd.Series:
    """Parse global_light from a GISTEMP-augmented v4.inv file.

    The augmented file has the brightness value appended at col 69-73
    (added by gistemp4.0's generate_brightness.run()).
    """
    rows = []
    with open(path) as f:
        for line in f:
            if len(line) < 11:
                continue
            uid = line[0:11].strip()
            raw = line[69:74].strip() if len(line) > 69 else ''
            gl = int(raw) if raw.lstrip('-').isdigit() else None
            rows.append({'Station_ID': uid, 'global_light': gl})
    return pd.DataFrame(rows).set_index('Station_ID')['global_light']


def _compute_global_light_from_brightness(meta_url: str,
                                           brightness_path: str) -> pd.Series:
    """Compute global_light by replicating gistemp4.0's generate_brightness.

    Reads station lat/lon from *meta_url* and the pre-downloaded brightness
    grid from *brightness_path* (wrld-rad.data.txt).

    Matches generate_brightness.run() exactly.
    """
    # Load station lat/lon from v4.inv (cached in input/ by step0)
    local_inv = os.path.join(INPUT_DIR, 'v4.inv')
    if os.path.exists(local_inv):
        with open(local_inv) as f:
            inv_text = f.read()
    else:
        import urllib.request
        logger.info("  Downloading v4.inv …")
        os.makedirs(INPUT_DIR, exist_ok=True)
        urllib.request.urlretrieve(meta_url, local_inv)
        with open(local_inv) as f:
            inv_text = f.read()
    stations = {}
    for line in inv_text.splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        uid = line[0:11].strip()
        try:
            lat = float(parts[1])
            lon = float(parts[2])
        except (ValueError, IndexError):
            continue
        stations[uid] = (lat, lon)

    # Load brightness grid
    logger.info(f"  Loading brightness grid from {brightness_path} …")
    i_j_dict = {}
    with open(brightness_path) as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 3:
                i_j_dict[(parts[0], parts[1])] = parts[2]

    # Compute global_light per station (matches generate_brightness formula)
    rows = []
    for uid, (lat, lon) in stations.items():
        si = round((lon + 180.0) * 120 + 1)
        sj = round(21600 + 0.5 - (lat + 90.0) * 120)
        if sj >= 21600:
            sj = 21600
        if si >= 43200:
            si = 1
        gl_str = i_j_dict.get((str(si), str(sj)), '0')
        try:
            gl = int(gl_str)
        except ValueError:
            gl = 0
        rows.append({'Station_ID': uid, 'global_light': gl})

    return pd.DataFrame(rows).set_index('Station_ID')['global_light']


def _get_global_light(meta_url: str, brightness_url: str) -> pd.Series:
    """Return {Station_ID: global_light} for all stations.

    Downloads wrld-rad.data.txt to input/ on first run and caches it there.
    """
    import urllib.request
    local_bright = os.path.join(INPUT_DIR, 'wrld-rad.data.txt')
    if not os.path.exists(local_bright):
        logger.info(f"  Downloading wrld-rad.data.txt …")
        os.makedirs(INPUT_DIR, exist_ok=True)
        urllib.request.urlretrieve(brightness_url, local_bright)

    return _compute_global_light_from_brightness(meta_url, local_bright)


def _time_cols(df: pd.DataFrame):
    return [c for c in df.columns if c not in ('Latitude', 'Longitude', '__LastGHCNYear__')]


# ── Annual-anomaly computation ────────────────────────────────────────────────

def _build_matrix(df: pd.DataFrame, start_year: int, end_year: int) -> np.ndarray:
    """
    Build a (n_stations, n_years, 12) float64 array from the wide DataFrame.

    axis 0: stations (same order as df.index)
    axis 1: year index (0 = start_year)
    axis 2: month index (0 = January … 11 = December)
    """
    n_stations = len(df)
    n_years = end_year - start_year + 1
    mat = np.full((n_stations, n_years, 12), np.nan, dtype=np.float64)
    for mi, month in enumerate(range(1, 13)):
        cols = [f'{month}_{y}'
                for y in range(start_year, end_year + 1)
                if f'{month}_{y}' in df.columns]
        if not cols:
            continue
        yi = [int(c.split('_')[1]) - start_year for c in cols]
        mat[:, yi, mi] = df[cols].values
    return mat


def _compute_annual_anomalies(mat: np.ndarray) -> np.ndarray:
    """
    Vectorised annual-anomaly computation over all stations.

    mat: (n_stations, n_years, 12), NaN for missing values
    Returns: (n_stations, n_years) array, NaN for missing annual anomalies

    Algorithm matches gistemp4.0's annual_anomaly() exactly:
      - Monthly means over all valid values; December mean excludes the last
        December of each station's GHCN series.
      - Seasons: DJF=0, MAM=1, JJA=2, SON=3.
      - Seasonal anomaly valid when >= 2 months are valid.
      - Annual anomaly valid when >= 3 seasons are valid.
    """
    n_stations, n_years, _ = mat.shape

    any_valid_yr = ~np.all(np.isnan(mat), axis=2)           # (ns, ny)
    has_any = np.any(any_valid_yr, axis=1)                   # (ns,)

    rev = any_valid_yr[:, ::-1]
    last_yi_arr = (n_years - 1 - np.argmax(rev, axis=1)).astype(int)

    # Monthly means (nan-safe); axis=1 averages over years
    monthly_means = np.nanmean(mat, axis=1)                  # (ns, 12)

    # Re-compute December mean excluding each station's last GHCN December
    dec = mat[:, :, 11].copy()                               # (ns, ny)
    valid_rows = np.where(has_any)[0]
    dec[valid_rows, last_yi_arr[valid_rows]] = np.nan
    with np.errstate(all='ignore'):
        monthly_means[:, 11] = np.nanmean(dec, axis=1)

    # Monthly anomalies
    anom = mat - monthly_means[:, np.newaxis, :]             # (ns, ny, 12)

    # Season 0 (DJF): Dec of previous year, Jan, Feb
    dec_prev = np.full((n_stations, n_years), np.nan)
    dec_prev[:, 1:] = anom[:, :-1, 11]

    def _season_mean(months3d):
        count = np.sum(~np.isnan(months3d), axis=2)
        total = np.nansum(months3d, axis=2)
        return np.where(count >= 2, total / np.maximum(count, 1), np.nan)

    s0 = _season_mean(np.stack([dec_prev, anom[:, :, 0], anom[:, :, 1]], axis=2))
    s1 = _season_mean(anom[:, :, 2:5])
    s2 = _season_mean(anom[:, :, 5:8])
    s3 = _season_mean(anom[:, :, 8:11])

    all_s = np.stack([s0, s1, s2, s3], axis=2)              # (ns, ny, 4)
    n_valid_s = np.sum(~np.isnan(all_s), axis=2)            # (ns, ny)
    with np.errstate(all='ignore'):
        annual = np.where(n_valid_s >= 3,
                          np.nansum(all_s, axis=2) / n_valid_s,
                          np.nan)
    return annual


# ── Station annotation container ──────────────────────────────────────────────

class _Ann:
    """Lightweight struct holding a station's precomputed annotation data."""
    __slots__ = ('uid', 'anomalies', 'cslat', 'snlat', 'cslon', 'snlon', 'weight')

    def __init__(self, uid, anomalies, lat_deg, lon_deg):
        self.uid = uid
        self.anomalies = anomalies          # 1-D np.ndarray, length n_years
        pi180 = math.pi / 180.0
        self.cslat = math.cos(lat_deg * pi180)
        self.snlat = math.sin(lat_deg * pi180)
        self.cslon = math.cos(lon_deg * pi180)
        self.snlon = math.sin(lon_deg * pi180)
        self.weight = 0.0


# ── Rural-neighbour finding ───────────────────────────────────────────────────

def _get_neighbours(us: _Ann,
                    rural: list,
                    r_snlat: np.ndarray,
                    r_cslat: np.ndarray,
                    r_cslon: np.ndarray,
                    r_snlon: np.ndarray,
                    radius: float) -> list:
    """Return rural stations within *radius* km of *us*, with .weight set.

    Vectorised over the rural-station array; matches gistemp4.0's
    get_neighbours() formula exactly.
    """
    cos_crit = math.cos(radius / EARTH_RADIUS)
    rbyrc = EARTH_RADIUS / radius

    csdbyr = (r_snlat * us.snlat
              + r_cslat * us.cslat * (r_cslon * us.cslon + r_snlon * us.snlon))

    idx = np.where(csdbyr > cos_crit)[0]
    neighbours = []
    for i in idx:
        c = float(csdbyr[i])
        dbyrc = 0.0
        if c < 1.0:
            dbyrc = rbyrc * math.sqrt(2.0 * (1.0 - c))
        rural[i].weight = 1.0 - dbyrc
        neighbours.append(rural[i])
    return neighbours


# ── Rural-series combination ──────────────────────────────────────────────────

def _cmbine(combined: np.ndarray,
            weights: np.ndarray,
            counts: np.ndarray,
            data: np.ndarray,
            weight: float):
    """Bias-correct *data* and fold it into the weighted average *combined*.

    Matches gistemp4.0's cmbine() exactly.

    NOTE: gistemp4.0 initialises combined with MISSING=9999.0, so the
    product  old_wt * 9999.0  vanishes when old_wt=0 (regular float maths).
    We use NaN for missing, so we must handle that case explicitly:
    when combined[n] is NaN, treat it as 0 (the weight is also 0).
    """
    both_valid = ~np.isnan(combined) & ~np.isnan(data)
    ncom = int(both_valid.sum())
    if ncom < RURAL_MIN_OVERLAP:
        return

    bias = (float(combined[both_valid].sum()) - float(data[both_valid].sum())) / ncom

    # Only update positions where the incoming data is valid
    valid_new = ~np.isnan(data)
    if not valid_new.any():
        return

    old_wt = weights[valid_new]
    new_wt = old_wt + weight
    # When combined is NaN, old_wt is 0 and we treat old combined as 0
    old_combined = np.where(np.isnan(combined[valid_new]), 0.0, combined[valid_new])
    combined[valid_new] = (old_wt * old_combined + weight * (data[valid_new] + bias)) / new_wt
    weights[valid_new] = new_wt
    counts[valid_new] += 1


def _combine_neighbours(n_years: int, neighbours: list):
    """Combine neighbours' annual-anomaly series into one weighted series.

    Matches gistemp4.0's combine_neighbours().
    Returns (counts, combined), both numpy arrays of length n_years.
    """
    weights = np.zeros(n_years)
    counts = np.zeros(n_years, dtype=int)
    combined = np.full(n_years, np.nan)

    rs = neighbours[0]
    an = rs.anomalies
    end = len(an)
    combined[:end] = an
    for i, anom in enumerate(an):
        if not np.isnan(anom):
            weights[i] = rs.weight
            counts[i] = 1

    for rs in neighbours[1:]:
        _cmbine(combined, weights, counts, rs.anomalies, rs.weight)

    return counts, combined


# ── Fit-preparation helpers ───────────────────────────────────────────────────

def _prepare_series(from_year: int,
                    combined: np.ndarray,
                    urban_anoms: np.ndarray,
                    counts: np.ndarray):
    """Build the (year, difference) point list for the linear fit.

    Matches gistemp4.0's prepare_series() exactly.
    Returns (points, quorate_count).
    """
    quorate_count = 0
    length = 0
    points = []

    assert len(combined) >= len(urban_anoms)

    for iy in range(from_year - BASE_YEAR, len(urban_anoms)):
        if np.isnan(combined[iy]) or np.isnan(urban_anoms[iy]):
            continue
        quorate = counts[iy] >= URBAN_MIN_RURAL_STATIONS
        if quorate:
            quorate_count += 1
        if quorate_count == 0:
            continue
        points.append((iy + BASE_YEAR, float(combined[iy]) - float(urban_anoms[iy])))
        if quorate:
            length = len(points)

    return points[:length], quorate_count


def _rural_difference(urban: _Ann,
                      rural: list,
                      r_snlat: np.ndarray, r_cslat: np.ndarray,
                      r_cslon: np.ndarray, r_snlon: np.ndarray,
                      n_years: int):
    """Find a combined rural record for *urban* and return
    (points, quorate_count) or (None, None).

    Matches gistemp4.0's rural_difference().
    """
    R = URBAN_FULL_RADIUS
    for radius in [R / 2, R]:
        neighbours = _get_neighbours(urban, rural, r_snlat, r_cslat,
                                     r_cslon, r_snlon, radius)
        if not neighbours:
            continue

        counts, combined = _combine_neighbours(n_years, neighbours)
        start_year = BASE_YEAR

        while True:
            points, quorate_count = _prepare_series(
                start_year, combined, urban.anomalies, counts)

            if quorate_count < URBAN_MIN_YEARS:
                break

            first = min(points)[0]
            last = max(points)[0]

            if quorate_count >= URBAN_PROPORTION_GOOD * (last - first + 0.9):
                return points, quorate_count

            start_year = int(last - (quorate_count - 1) / URBAN_PROPORTION_GOOD)
            start_year = max(start_year, first + 1)

    return None, None


# ── Linear-fit helpers ────────────────────────────────────────────────────────

def _trend2(points, xmid, min_pts):
    """Two-part linear regression at knee *xmid*.

    Returns (sl1, sl2, rms, sl) or (None, None, None, None) on failure.
    Matches gistemp4.0's trend2() (using MISSING=9999 sentinel there).
    """
    count0 = count1 = 0
    sx0 = sx1 = sxx0 = sxx1 = sxa0 = sxa1 = 0.0
    sa = saa = 0.0

    for (x, v) in points:
        x -= xmid
        sa += v
        saa += v * v
        if x > 0.0:
            count1 += 1; sx1 += x; sxx1 += x * x; sxa1 += x * v
        else:
            count0 += 1; sx0 += x; sxx0 += x * x; sxa0 += x * v

    if count0 < min_pts or count1 < min_pts:
        return None, None, None, None

    count = count0 + count1
    denom = count * sxx0 * sxx1 - sxx0 * sx1 * sx1 - sxx1 * sx0 * sx0
    sl1 = (sx0 * (sx1 * sxa1 - sxx1 * sa) + sxa0 * (count * sxx1 - sx1 * sx1)) / denom
    sl2 = (sx1 * (sx0 * sxa0 - sxx0 * sa) + sxa1 * (count * sxx0 - sx0 * sx0)) / denom

    ymid = (sa - sl1 * sx0 - sl2 * sx1) / count
    rms = (count * ymid * ymid + saa
           - 2 * ymid * (sa - sl1 * sx0 - sl2 * sx1)
           + sl1 * sl1 * sxx0 + sl2 * sl2 * sxx1
           - 2 * sl1 * sxa0 - 2 * sl2 * sxa1)

    sx = sx0 + sx1
    sxx = sxx0 + sxx1
    sxa = sxa0 + sxa1
    sl = (count * sxa - sa * sx) / (count * sxx - sx * sx)

    return sl1, sl2, rms, sl


def _getfit(points):
    """Find the best two-part linear fit over all candidate knee positions.

    Returns a dict with keys slope1, slope2, slope, knee, first, last.
    Matches gistemp4.0's getfit().
    """
    first = min(points)[0]
    last = max(points)[0]
    rmsmin = _INF_RMS
    slope1 = slope2 = slope = knee = None

    for n in range(URBAN_MIN_LEG, len(points) - URBAN_MIN_LEG):
        k = points[n][0]
        sl1, sl2, rms, sl = _trend2(points, k, 2)
        if rms is not None and rms < rmsmin:
            rmsmin = rms
            slope1, slope2, slope, knee = sl1, sl2, sl, k

    return dict(slope1=slope1, slope2=slope2, slope=slope,
                knee=knee, first=first, last=last)


def _good_two_part_fit(fit) -> bool:
    """True when the two-part fit passes all quality criteria.

    Matches gistemp4.0's good_two_part_fit().
    """
    sl1, sl2 = fit['slope1'], fit['slope2']
    return (
        (fit['knee'] - fit['first'] >= URBAN_SHORT_LEG) and
        (fit['last'] - fit['knee'] >= URBAN_SHORT_LEG) and
        (abs(sl1) <= URBAN_STEEP_LEG) and
        (abs(sl2) <= URBAN_STEEP_LEG) and
        (abs(sl2 - sl1) <= URBAN_STEEP_LEG) and
        ((sl1 * sl2 >= 0)
         or (abs(sl1) <= URBAN_REVERSE_GRADIENT)
         or (abs(sl2) <= URBAN_REVERSE_GRADIENT))
    )


def _extend_range(urban_anoms: np.ndarray,
                  quorate_count: int,
                  first: int, last: int):
    """Extend the adjustment range beyond the quorate window if possible.

    Matches gistemp4.0's extend_range().
    Returns (adjust_first, adjust_last) as calendar years.
    """
    iyxtnd = int(round(quorate_count / URBAN_PROPORTION_GOOD) - (last - first + 1))
    if iyxtnd == 0:
        return first, last

    valid_idx = np.where(~np.isnan(urban_anoms))[0]
    urban_first = int(valid_idx.min()) + BASE_YEAR - 1
    urban_last = int(valid_idx.max()) + BASE_YEAR + 1

    lxend = urban_last - last
    if iyxtnd > lxend:
        first -= (iyxtnd - lxend)
        first = max(first, urban_first)
    last = urban_last
    return first, last


# ── Record adjustment ─────────────────────────────────────────────────────────

def _adjust_station(row_vals: dict,
                    start_year: int, end_year: int,
                    fit: dict,
                    adjust_first: int, adjust_last: int,
                    use_two_part: bool,
                    all_temp_cols: set) -> dict:
    """
    Apply the urban heat-island adjustment to one station's monthly data.

    Returns {col: value} with NaN for months outside the adjustment range.
    Matches gistemp4.0's adjust_record() — output is MISSING for unadjusted
    months.

    The anomaly year for calendar year *iy* covers Dec(iy-1) through Nov(iy),
    exactly as in gistemp4.0's adjust_record loop.
    """
    sl1 = fit['slope1']
    sl2 = fit['slope2']
    if not use_two_part:
        sl1 = sl2 = fit['slope']
    knee = fit['knee']
    fit_first = fit['first']
    fit_last = fit['last']

    result = {col: np.nan for col in all_temp_cols}

    for iy in range(adjust_first, adjust_last + 1):
        sl = sl1 if iy <= knee else sl2
        iya = max(fit_first, min(iy, fit_last))
        adj = (iya - knee) * sl - (fit_last - knee) * sl2

        # Dec of (iy-1) then Jan..Nov of iy  (mirrors gistemp4.0's flat-index loop)
        if iy > start_year:
            col = f'12_{iy - 1}'
            if col in result:
                orig = row_vals.get(col, np.nan)
                if not pd.isna(orig):
                    result[col] = orig + adj

        for mo in range(1, 12):
            yr = iy
            if yr < start_year or yr > end_year:
                continue
            col = f'{mo}_{yr}'
            if col in result:
                orig = row_vals.get(col, np.nan)
                if not pd.isna(orig):
                    result[col] = orig + adj

    return result


# ── Public step functions ─────────────────────────────────────────────────────

def drop_short_records(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop stations where no month has >= 20 valid readings across all years.

    Matches gistemp4.0's drop_short_records() with station_drop_minimum_months=20.
    """
    tc = _time_cols(df)

    valid_per_month = pd.DataFrame({
        m: df[[c for c in tc if c.startswith(f'{m}_')]].notna().sum(axis=1)
        for m in range(1, 13)
    }, index=df.index)

    keep = valid_per_month.max(axis=1) >= STATION_DROP_MIN_MONTHS
    n_dropped = int((~keep).sum())
    logger.info(f"  drop_short_records: dropped {n_dropped}, kept {int(keep.sum())}")
    return df[keep].copy()


def urban_adjustments(df: pd.DataFrame,
                      meta_url: str,
                      brightness_url: str,
                      start_year: int,
                      end_year: int) -> pd.DataFrame:
    """
    Apply urban heat-island adjustment.

    Rural stations pass through unchanged.  Urban stations that cannot be
    adjusted (no sufficient nearby rural data) are dropped.  Adjusted urban
    stations have data outside the adjustment window set to NaN.

    Matches gistemp4.0's urban_adjustments() exactly.
    """
    n_years = end_year - start_year + 1

    logger.info("  Fetching station metadata (global_light)…")
    gl = _get_global_light(meta_url, brightness_url)

    logger.info("  Building monthly matrix and computing annual anomalies…")
    mat = _build_matrix(df, start_year, end_year)          # (ns, ny, 12)
    station_ids = list(df.index)

    annual_all = _compute_annual_anomalies(mat)             # (ns, ny)

    # Annotate stations
    rural = []
    urban_idx = {}   # df-position → _Ann

    for i, sid in enumerate(station_ids):
        annual = annual_all[i]
        if np.all(np.isnan(annual)):
            continue                                        # no anomalies → pass-through

        lat = float(df.at[sid, 'Latitude'])
        lon = float(df.at[sid, 'Longitude'])
        ann = _Ann(sid, annual, lat, lon)

        light = gl.get(sid, None)
        is_rural = (light is None) or (light <= RURAL_LIGHT_THRESHOLD)

        if is_rural:
            rural.append(ann)
        else:
            urban_idx[i] = ann

    # Sort rural stations by record length descending (stable, matching v4.0)
    # Note: sort() + reverse() differs from sort(reverse=True) in tie-breaking
    def reclen(s):
        return int(np.sum(~np.isnan(s.anomalies)))

    rural.sort(key=reclen)
    rural.reverse()

    logger.info(f"  Rural: {len(rural)}, Urban: {len(urban_idx)}")

    # Pre-build rural trig arrays for vectorised distance computation
    r_snlat = np.array([r.snlat for r in rural])
    r_cslat = np.array([r.cslat for r in rural])
    r_cslon = np.array([r.cslon for r in rural])
    r_snlon = np.array([r.snlon for r in rural])

    # All temperature column names (used to initialise adjusted rows)
    tc = _time_cols(df)
    all_temp_cols = set(tc)

    # Process each urban station
    adjusted_rows = {}    # sid → {col: value}
    n_adjusted = n_dropped_urban = 0

    for i, us in urban_idx.items():
        sid = station_ids[i]
        points, quorate_count = _rural_difference(
            us, rural, r_snlat, r_cslat, r_cslon, r_snlon, n_years)

        if points is None:
            n_dropped_urban += 1
            continue

        fit = _getfit(points)
        adjust_first, adjust_last = _extend_range(
            us.anomalies, quorate_count, fit['first'], fit['last'])
        use_two_part = _good_two_part_fit(fit)

        row_vals = df.loc[sid, tc].to_dict()
        adjusted_rows[sid] = _adjust_station(
            row_vals, start_year, end_year,
            fit, adjust_first, adjust_last, use_two_part, all_temp_cols)
        n_adjusted += 1

    logger.info(
        f"  Urban adjusted: {n_adjusted}, dropped (no rural): {n_dropped_urban}")

    # Drop urban stations that had no rural neighbourhood.
    dropped_urban = {station_ids[i] for i in urban_idx if station_ids[i] not in adjusted_rows}
    df_out = df.drop(list(dropped_urban)).copy()

    # Apply all adjustments in one bulk assignment instead of per-row concat.
    if adjusted_rows:
        adj_df = pd.DataFrame.from_dict(adjusted_rows, orient='index')
        shared_cols = [c for c in adj_df.columns if c in df_out.columns]
        df_out.loc[adj_df.index, shared_cols] = adj_df[shared_cols].values

    df_out.index.name = 'Station_ID'
    return df_out


def step2(df: pd.DataFrame,
          meta_url: str,
          brightness_url: str,
          start_year: int,
          end_year: int) -> pd.DataFrame:
    """
    Step 2: drop short records then apply urban heat-island adjustment.

    Returns a DataFrame in the same format as the input.
    """
    logger.info("Step 2: drop short records")
    df = drop_short_records(df)

    logger.info("Step 2: urban heat-island adjustment")
    df = urban_adjustments(df, meta_url, brightness_url, start_year, end_year)

    logger.info(f"Step 2 complete: {len(df)} stations remain")
    return df
