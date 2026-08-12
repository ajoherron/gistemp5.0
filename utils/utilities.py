"""
Shared utility functions used across multiple steps.
"""

import numpy as np
import pandas as pd


def normalize_dict_values(d: dict) -> dict:
    """Normalize dict values to sum to 1. Returns d unchanged if sum is zero."""
    total = sum(d.values())
    if total != 0:
        return {k: v / total for k, v in d.items()}
    return d


def calculate_distances(df_1: pd.DataFrame, df_2: pd.DataFrame, earth_radius: float) -> np.ndarray:
    """
    Compute the full pairwise Haversine distance matrix between two sets of stations.

    Returns an (n1 x n2) array of distances in the same units as earth_radius.
    Both DataFrames must have 'Latitude' and 'Longitude' columns in degrees.
    """
    lat1 = np.radians(df_1["Latitude"].values[:, np.newaxis])
    lon1 = np.radians(df_1["Longitude"].values[:, np.newaxis])
    lat2 = np.radians(df_2["Latitude"].values)
    lon2 = np.radians(df_2["Longitude"].values)

    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    np.clip(a, 0, 1, out=a)
    return earth_radius * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))
