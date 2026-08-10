"""
Internal helper — run from within the gistemp4.0 directory.
Parses step0 using gistemp4.0's own GHCNV4Reader and writes CSV to stdout.

    python testing/_v4_dump.py <start_year> <end_year>

Called as a subprocess by compare_step0.py.
"""

import csv
import sys
import os

# Must be invoked with cwd = gistemp4.0 root
sys.path.insert(0, '.')
sys.path.insert(0, 'tool')

from settings import INPUT_DIR
from tool.gio import GHCNV4Reader, augmented_station_metadata
from steps.giss_data import MISSING, BASE_YEAR

START_YEAR = int(sys.argv[1]) if len(sys.argv) > 1 else BASE_YEAR
END_YEAR   = int(sys.argv[2]) if len(sys.argv) > 2 else 2023

meta = augmented_station_metadata(
    os.path.join(INPUT_DIR, 'v4.inv'),
    format='giss_v4',
)

rows = []
with open(os.path.join(INPUT_DIR, 'ghcnm.tavg.qcf.dat')) as f:
    for record in GHCNV4Reader(file=f, meta=meta, year_min=BASE_YEAR):
        uid = record.uid
        try:
            lat = record.station.lat
            lon = record.station.lon
        except AttributeError:
            lat = lon = ''

        row = {'Station_ID': uid, 'Latitude': lat, 'Longitude': lon}

        # asdict() returns {YYYYMM: value} for all non-MISSING values
        for yyyymm, val in record.asdict().items():
            year  = yyyymm // 100
            month = yyyymm % 100
            if START_YEAR <= year <= END_YEAR:
                row[f'{month}_{year}'] = val

        rows.append(row)

# Collect all time columns then write CSV
time_cols = sorted(
    {k for r in rows for k in r if k not in ('Station_ID', 'Latitude', 'Longitude')},
    key=lambda c: int(c.split('_')[1]),
)
fieldnames = ['Station_ID', 'Latitude', 'Longitude'] + time_cols

writer = csv.DictWriter(sys.stdout, fieldnames=fieldnames, extrasaction='ignore')
writer.writeheader()
for row in rows:
    writer.writerow(row)
