"""
Internal helper — run from within the gistemp4.0 directory.
Runs gistemp4.0 step0 → step1 → step2 and writes parquet to <output_path>.

    python testing/_v4_step2_dump.py <start_year> <end_year> <output_path>

Called as a subprocess by compare_step2.py.
Requires ghcnm.tavg.qcf.dat, v4.inv, and Ts.strange.v4.list.IN_full
to already be present in tmp/input/.
"""

import csv
import io
import os
import sys

sys.path.insert(0, '.')
sys.path.insert(0, 'tool')

# Ensure log and work dirs exist (step2 opens a log file at import time)
os.makedirs('tmp/log', exist_ok=True)
os.makedirs('tmp/work', exist_ok=True)

from steps.giss_data import BASE_YEAR

START_YEAR  = int(sys.argv[1]) if len(sys.argv) > 1 else BASE_YEAR
END_YEAR    = int(sys.argv[2]) if len(sys.argv) > 2 else 2023
OUTPUT_PATH = sys.argv[3] if len(sys.argv) > 3 else None

# Silence prints from gistemp4.0 internals
_real_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w')

from tool import gio
from steps import step0 as v4_step0, step1 as v4_step1

# Patch get_last_year BEFORE importing step2, so MAX_YEARS matches END_YEAR.
# gistemp4.0 uses time.localtime().tm_year (current year) by default, but we
# need to match the exact year range we pass to gistemp5 for a fair comparison.
from steps import giss_data as _giss_data
_giss_data.get_last_year = lambda: END_YEAR

from steps import step2 as v4_step2

sys.stdout = _real_stdout

# Run step0 → step1 using gistemp4.0's own I/O
sys.stdout = open(os.devnull, 'w')
step0_records = v4_step0.step0(gio.step0_input())
step1_records = list(v4_step1.step1(step0_records))
sys.stdout = _real_stdout

# Truncate station records to END_YEAR so gistemp4.0 step2 processes the same
# year range as our pipeline.  Without this, stations with data in 2024-2025
# appear in the GHCN file (downloaded in 2026) and inflate valid-month counts.
def _truncate(records, end_year):
    out = []
    for record in records:
        max_len = (end_year - record.first_year + 1) * 12
        if len(record.series) > max_len:
            record.set_series(record.first_month, record.series[:max_len])
        out.append(record)
    return out

step1_records = _truncate(step1_records, END_YEAR)

# Run step2
sys.stdout = open(os.devnull, 'w')
step2_records = list(v4_step2.step2(iter(step1_records)))
sys.stdout = _real_stdout

# Serialize to wide DataFrame (same format as gistemp5 step2 output)
rows = []
for record in step2_records:
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
