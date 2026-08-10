"""
Step-output caching. Saves/loads DataFrames as parquet files keyed by
step name and year range. Cache lives in cache/ at the repo root.

Usage:
    df = step_cache.load('step0', start_year, end_year)
    if df is None:
        df = run_step0(...)
        step_cache.save(df, 'step0', start_year, end_year)
"""

import os
import pandas as pd

_CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'cache')


def _path(name: str, start_year: int, end_year: int) -> str:
    return os.path.join(_CACHE_DIR, f'{name}_{start_year}_{end_year}.parquet')


def load(name: str, start_year: int, end_year: int):
    path = _path(name, start_year, end_year)
    if os.path.exists(path):
        return pd.read_parquet(path)
    return None


def save(df: pd.DataFrame, name: str, start_year: int, end_year: int) -> str:
    os.makedirs(_CACHE_DIR, exist_ok=True)
    path = _path(name, start_year, end_year)
    df.to_parquet(path)
    return path


def clear(name: str, start_year: int, end_year: int) -> bool:
    path = _path(name, start_year, end_year)
    if os.path.exists(path):
        os.remove(path)
        return True
    return False
