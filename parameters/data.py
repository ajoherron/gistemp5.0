"""
Data source URLs and local paths for gistemp5.
"""

import os as _os

GHCN_TEMP_URL  = "https://data.giss.nasa.gov/pub/gistemp/ghcnm.tavg.qcf.dat"
GHCN_META_URL  = "https://data.giss.nasa.gov/pub/gistemp/v4.inv"
STRANGE_URL    = "https://data.giss.nasa.gov/pub/gistemp/Ts.strange.v4.list.IN_full"
ERSST_URL      = "https://downloads.psl.noaa.gov/Datasets/noaa.ersst.v5/sst.mnmean.nc"
BRIGHTNESS_URL = "https://data.giss.nasa.gov/pub/gistemp/wrld-rad.data.txt"

# Pre-processed ERSSTv5 ocean subbox file (Fortran big-endian binary).
# Shared with the gistemp4.0 reference installation.
_REPO_ROOT     = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
_PROJECTS_DIR  = _os.path.dirname(_REPO_ROOT)   # gistemp5.0's parent (Projects/)
SBBX_PATH      = _os.path.join(_PROJECTS_DIR, 'gistemp4.0', 'tmp', 'input', 'SBBX.ERSSTv5')
SBBX_INPUT_DIR = _os.path.join(_PROJECTS_DIR, 'gistemp4.0', 'tmp', 'input')
