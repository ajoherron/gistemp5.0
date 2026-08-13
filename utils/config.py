"""
Configuration for gistemp5: year range and data source URLs/paths.
"""

import os as _os

# Pipeline year range
START_YEAR = 1880
END_YEAR   = 2026

# Local input cache (downloaded files, gitignored)
_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
INPUT_DIR  = _os.path.join(_REPO_ROOT, 'input')

# Data source URLs
GHCN_TEMP_URL  = "https://data.giss.nasa.gov/pub/gistemp/ghcnm.tavg.qcf.dat"
GHCN_META_URL  = "https://data.giss.nasa.gov/pub/gistemp/v4.inv"
STRANGE_URL    = "https://data.giss.nasa.gov/pub/gistemp/Ts.strange.v4.list.IN_full"
BRIGHTNESS_URL = "https://data.giss.nasa.gov/pub/gistemp/wrld-rad.data.txt"
SBBX_URL       = "https://data.giss.nasa.gov/pub/gistemp/SBBX.ERSSTv5.gz"

# Local paths for downloaded inputs
SBBX_PATH      = _os.path.join(INPUT_DIR, 'SBBX.ERSSTv5')
SBBX_INPUT_DIR = INPUT_DIR
