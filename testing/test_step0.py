"""
Step 0 validation: compare output against GISTEMP_rewrite reference data.

Run from repo root:
    pytest testing/test_step0.py -v
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from steps.step0 import step0
from parameters.data import GHCN_TEMP_URL, GHCN_META_URL
from parameters.constants import START_YEAR, END_YEAR

REFERENCE_PATH = "../GISTEMP_rewrite/results/step0_output.csv"


@pytest.fixture(scope="module")
def df0():
    return step0(GHCN_TEMP_URL, GHCN_META_URL, START_YEAR, END_YEAR)


def test_year_range(df0):
    """First and last data columns span exactly [START_YEAR, END_YEAR]."""
    data_cols = [c for c in df0.columns if c not in ("Latitude", "Longitude")]
    years = [int(c.split("_")[1]) for c in data_cols]
    assert min(years) == START_YEAR
    assert max(years) == END_YEAR


def test_column_count(df0):
    """Total columns = 12 months * years + 2 coordinate columns."""
    expected = 12 * (END_YEAR - START_YEAR + 1) + 2
    assert len(df0.columns) == expected


def test_no_all_nan_stations(df0):
    """Every station must have at least one valid temperature reading."""
    data_cols = [c for c in df0.columns if c not in ("Latitude", "Longitude")]
    all_nan = df0[data_cols].isna().all(axis=1)
    assert not all_nan.any(), f"{all_nan.sum()} stations have no valid data"


def test_temperature_range(df0):
    """All non-NaN temperatures should be physically plausible (−90 to 60 °C)."""
    data_cols = [c for c in df0.columns if c not in ("Latitude", "Longitude")]
    vals = df0[data_cols].values
    valid = vals[~np.isnan(vals)]
    assert valid.min() > -90
    assert valid.max() < 60


def test_coordinate_bounds(df0):
    assert df0["Latitude"].between(-90, 90).all()
    assert df0["Longitude"].between(-180, 180).all()


def test_matches_reference(df0):
    """Column count and station count should match GISTEMP_rewrite step0 output."""
    if not os.path.exists(REFERENCE_PATH):
        pytest.skip("Reference file not found — run GISTEMP_rewrite first")
    ref = pd.read_csv(REFERENCE_PATH, index_col="Station_ID")
    assert len(df0.columns) == len(ref.columns), "Column count mismatch"
    assert len(df0) == len(ref), "Station count mismatch"
