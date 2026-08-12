"""
Read gistemp4.0 step 5 ZON.npz outputs and save as parquet.

Run from repo root (no pipeline re-run needed — v4 result files already exist):
    python testing/_v4_step5_dump.py

Writes:
    ../gistemp4.0/tmp/step5_land_monthly.parquet
    ../gistemp4.0/tmp/step5_mixed_monthly.parquet
"""

import os
import sys

import numpy as np
import pandas as pd

REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V4_RESULT  = os.path.join(REPO_ROOT, '..', 'gistemp4.0', 'tmp', 'result')
V4_TMP     = os.path.join(REPO_ROOT, '..', 'gistemp4.0', 'tmp')

_MISSING = 9999.0

_ZON_FILES = {
    'land':  'landZON.Ts.GHCN.CL.PA.1200.npz',
    'mixed': 'mixedZON.Ts.ERSSTV5.GHCN.CL.PA.1200.npz',
}


def zon_to_df(path):
    """Load a ZON.npz file and return a monthly DataFrame.

    Columns: zone_0 … zone_15.
    Index: MultiIndex (year, month), year starting at meta.yrbeg.
    Missing (9999.0) → NaN.
    """
    d = np.load(path, allow_pickle=True)

    meta   = d['meta']
    yrbeg  = int(meta[5])
    monm   = int(meta[3])          # total months (1752 for 1880-2025)
    iyrs   = monm // 12

    n_zones = len([k for k in d.keys() if k != 'meta'])  # 16

    monthly = np.full((monm, n_zones), np.nan)
    for zi in range(n_zones):
        arr  = d[f'arr_{zi}']
        data = np.asarray(arr[1], dtype=float)  # flat 1752-element series
        data[data == _MISSING] = np.nan
        monthly[:, zi] = data

    # Build MultiIndex (year, month)
    idx = pd.MultiIndex.from_tuples(
        [(yrbeg + iy, m + 1) for iy in range(iyrs) for m in range(12)],
        names=['year', 'month'],
    )
    cols = [f'zone_{i}' for i in range(n_zones)]
    return pd.DataFrame(monthly, index=idx, columns=cols)


def main():
    for mode, fname in _ZON_FILES.items():
        src  = os.path.join(V4_RESULT, fname)
        dest = os.path.join(V4_TMP, f'step5_{mode}_monthly.parquet')
        if not os.path.exists(src):
            print(f"Missing: {src}")
            sys.exit(1)
        df = zon_to_df(src)
        df.to_parquet(dest)
        print(f"Saved {mode}: {len(df)} rows → {dest}")


if __name__ == '__main__':
    main()
