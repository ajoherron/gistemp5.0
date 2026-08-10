"""
Internal helper — run from within the gistemp4.0 directory.
Runs gistemp4.0 step0 → step1 and writes parquet to <output_path>.

    python testing/_v4_step1_dump.py <start_year> <end_year> <output_path>

Called as a subprocess by compare_step1.py.
Requires ghcnm.tavg.qcf.dat, v4.inv, and Ts.strange.v4.list.IN_full
to already be present in tmp/input/.
"""

import csv
import io
import os
import sys

sys.path.insert(0, '.')
sys.path.insert(0, 'tool')

from steps.giss_data import BASE_YEAR

START_YEAR  = int(sys.argv[1]) if len(sys.argv) > 1 else BASE_YEAR
END_YEAR    = int(sys.argv[2]) if len(sys.argv) > 2 else 2023
OUTPUT_PATH = sys.argv[3] if len(sys.argv) > 3 else None

# Silence prints from gistemp4.0 internals
_real_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w')

from tool import gio
from steps import step0 as v4_step0, step1 as v4_step1

sys.stdout = _real_stdout

# Run step0 → step1 using gistemp4.0's own I/O
sys.stdout = open(os.devnull, 'w')
step0_records = v4_step0.step0(gio.step0_input())
step1_records = list(v4_step1.step1(step0_records))
sys.stdout = _real_stdout

# Serialize to wide DataFrame
rows = []
for record in step1_records:
    uid = record.uid
    try:
        lat = record.station.lat
        lon = record.station.lon
    except AttributeError:
        lat = lon = ''

    row = {'Station_ID': uid, 'Latitude': lat, 'Longitude': lon}

    for yyyymm, val in record.asdict().items():
        year  = yyyymm // 100
        month = yyyymm % 100
        if START_YEAR <= year <= END_YEAR:
            row[f'{month}_{year}'] = val

    rows.append(row)

time_cols = sorted(
    {k for r in rows for k in r if k not in ('Station_ID', 'Latitude', 'Longitude')},
    key=lambda c: int(c.split('_')[1]),
)
fieldnames = ['Station_ID', 'Latitude', 'Longitude'] + time_cols

buf = io.StringIO()
writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore')
writer.writeheader()
for row in rows:
    writer.writerow(row)
buf.seek(0)

import pandas as pd
df = pd.read_csv(buf, index_col='Station_ID', low_memory=False)

if OUTPUT_PATH:
    df.to_parquet(OUTPUT_PATH)
    print(f"Saved {len(df)} stations to {OUTPUT_PATH}")
else:
    print(df.to_csv())
