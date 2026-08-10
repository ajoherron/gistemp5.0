"""
Internal helper — run from within the gistemp4.0 directory.
Runs gistemp4.0 step0 → step1 → step2 and writes parquet files to tmp/.

    python testing/_v4_step2_dump.py <start_year> <end_year> <step2_output_path>

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
END_YEAR    = int(sys.argv[2]) if len(sys.argv) > 2 else 2026
OUTPUT_PATH = sys.argv[3] if len(sys.argv) > 3 else None

# Silence prints from gistemp4.0 internals
_real_stdout = sys.stdout
sys.stdout = open(os.devnull, 'w')

from tool import gio
from steps import step0 as v4_step0, step1 as v4_step1

# Patch get_last_year BEFORE importing step2, so MAX_YEARS matches END_YEAR.
from steps import giss_data as _giss_data
_giss_data.get_last_year = lambda: END_YEAR

from steps import step2 as v4_step2

sys.stdout = _real_stdout

import pandas as pd


def records_to_df(records, start_year, end_year):
    """Serialize gistemp4.0 Station records to wide DataFrame."""
    rows = []
    for record in records:
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
            if start_year <= year <= end_year:
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

    return pd.read_csv(buf, index_col='Station_ID', low_memory=False)


# Run step0 → step1 using gistemp4.0's own I/O
sys.stdout = open(os.devnull, 'w')
step0_records = list(v4_step0.step0(gio.step0_input()))
step1_records = list(v4_step1.step1(iter(step0_records)))
sys.stdout = _real_stdout

# Truncate records to END_YEAR
def _truncate(records, end_year):
    out = []
    for record in records:
        max_len = (end_year - record.first_year + 1) * 12
        if len(record.series) > max_len:
            record.set_series(record.first_month, record.series[:max_len])
        out.append(record)
    return out

step0_records = _truncate(step0_records, END_YEAR)
step1_records = _truncate(step1_records, END_YEAR)

# Save step0 and step1 in wide format
step0_path = os.path.join('tmp', 'step0_cache.parquet')
step1_path = os.path.join('tmp', 'step1_cache.parquet')

df0 = records_to_df(step0_records, START_YEAR, END_YEAR)
df0.to_parquet(step0_path)
print(f"Saved {len(df0)} step0 stations to {step0_path}")

df1 = records_to_df(step1_records, START_YEAR, END_YEAR)
df1.to_parquet(step1_path)
print(f"Saved {len(df1)} step1 stations to {step1_path}")

# Run step2
sys.stdout = open(os.devnull, 'w')
step2_records = list(v4_step2.step2(iter(step1_records)))
sys.stdout = _real_stdout

df2 = records_to_df(step2_records, START_YEAR, END_YEAR)

if OUTPUT_PATH:
    df2.to_parquet(OUTPUT_PATH)
    print(f"Saved {len(df2)} step2 stations to {OUTPUT_PATH}")
else:
    print(df2.to_csv())
