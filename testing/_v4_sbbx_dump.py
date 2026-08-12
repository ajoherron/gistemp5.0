"""
Internal helper — run from within the gistemp4.0 directory.
Reads SBBX.ERSSTv5 via v4's SubboxReader and writes a parquet.

    python testing/_v4_sbbx_dump.py <start_year> <end_year> <output_path>
"""

import os
import sys

sys.path.insert(0, '.')
sys.path.insert(0, 'tool')

os.makedirs('tmp/log', exist_ok=True)
os.makedirs('tmp/work', exist_ok=True)
os.makedirs('tmp', exist_ok=True)

START_YEAR  = int(sys.argv[1]) if len(sys.argv) > 1 else 1880
END_YEAR    = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
OUTPUT_PATH = sys.argv[3] if len(sys.argv) > 3 else 'tmp/step4_cache.parquet'

_MISSING = 9999.0

# Silence prints from gistemp4.0 internals
_real_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w')

from tool import gio

sys.stdout = _real_stdout

import pandas as pd

SBBX_PATH = os.path.join('tmp', 'input', 'SBBX.ERSSTv5')

reader  = gio.SubboxReader(open(SBBX_PATH, 'rb'))
it      = iter(reader)
meta    = next(it)
yrbeg   = meta.yrbeg

rows = []
for box in it:
    lat_s, lat_n, lon_w, lon_e = box.box
    d = float('nan') if box.d == _MISSING else box.d
    row = {
        'lat_s': lat_s, 'lat_n': lat_n,
        'lon_w': lon_w, 'lon_e': lon_e,
        'n_stations':     box.stations,
        'station_months': box.station_months,
        'd':              d,
    }
    for fi, val in enumerate(box.series):
        yr = yrbeg + fi // 12
        mo = fi % 12 + 1
        if START_YEAR <= yr <= END_YEAR:
            row[f'{mo}_{yr}'] = float('nan') if val == _MISSING else val
    rows.append(row)

df = pd.DataFrame(rows)
df.to_parquet(OUTPUT_PATH)
print(f"Saved {len(df)} ocean subboxes to {OUTPUT_PATH}")
