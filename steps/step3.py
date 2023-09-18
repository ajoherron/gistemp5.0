'''
Step 3: Gridding of cells

There are 8000 cells across the globe.
Each cell's values are computed using station records within a 1200km radius.
    - Contributions are weighted according to distance to cell center
    (linearly decreasing to 0 at distance 1200km)
'''

import math
import pandas as pd
from typing import Tuple, List

def generate_80_cell_grid() -> pd.DataFrame:
    lat_bands: List[float] = [-90, -64.2, -44.4, -23.6, 0, 23.6, 44.4, 64.2, 90]
    n_bands: int = len(lat_bands) - 1  # Number of latitude bands
    n_boxes_per_band: int = 10  # Number of boxes per band

    data: List[Tuple[float, float, float, float, float, float]] = []

    for band in range(n_bands):
        lat_south: float = lat_bands[band]
        lat_north: float = lat_bands[band + 1]

        for i in range(n_boxes_per_band):
            lon_west: float = -180 + i * (360 / n_boxes_per_band)
            lon_east: float = -180 + (i + 1) * (360 / n_boxes_per_band)

            # Calculate the equal area center latitude and longitude
            sinc: float = 0.5 * (math.sin(lat_south * math.pi / 180) + math.sin(lat_north * math.pi / 180))
            center_latitude: float = math.asin(sinc) * 180 / math.pi
            center_longitude: float = 0.5 * (lon_west + lon_east)

            data.append((lat_south, lat_north, lon_west, lon_east, center_latitude, center_longitude))

    df: pd.DataFrame = pd.DataFrame(data, columns=['Southern', 'Northern', 'Western', 'Eastern', 'Center_Latitude', 'Center_Longitude'])

    return df

def interpolate(x: float, y: float, p: float) -> float:
    return y * p + (1 - p) * x

def generate_8000_cell_grid() -> pd.DataFrame:
    def subgen(lat_s: float, lat_n: float, lon_w: float, lon_e: float) -> Generator[Tuple[float, float, float, float], None, None]:
        alts: float = math.sin(lat_s * math.pi / 180)
        altn: float = math.sin(lat_n * math.pi / 180)
        for y in range(10):
            s: float = 180 * math.asin(interpolate(alts, altn, y * 0.1)) / math.pi
            n: float = 180 * math.asin(interpolate(alts, altn, (y + 1) * 0.1)) / math.pi
            for x in range(10):
                w: float = interpolate(lon_w, lon_e, x * 0.1)
                e: float = interpolate(lon_w, lon_e, (x + 1) * 0.1)
                yield (s, n, w, e)

    initial_regions_df: pd.DataFrame = generate_80_cell_grid()
    data: List[Tuple[float, float, float, float]] = []

    for index, row in initial_regions_df.iterrows():
        for subcell in subgen(row['Southern'], row['Northern'], row['Western'], row['Eastern']):
            data.append(subcell)

    grid_df: pd.DataFrame = pd.DataFrame(data, columns=['Southern', 'Northern', 'Western', 'Eastern'])
    
    # Calculate the center latitude and longitude
    grid_df['Center_Latitude'] = (grid_df['Southern'] + grid_df['Northern']) / 2
    grid_df['Center_Longitude'] = (grid_df['Western'] + grid_df['Eastern']) / 2
    
    return grid_df

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the spherical distance (in kilometers) between two pairs of
    latitude and longitude coordinates using the Haversine formula.

    Args:
        lat1 (float): Latitude of the first point in degrees.
        lon1 (float): Longitude of the first point in degrees.
        lat2 (float): Latitude of the second point in degrees.
        lon2 (float): Longitude of the second point in degrees.

    Returns:
        float: Spherical distance in kilometers.
    """
    # Convert latitude and longitude from degrees to radians
    lat1 = math.radians(lat1)
    lon1 = math.radians(lon1)
    lat2 = math.radians(lat2)
    lon2 = math.radians(lon2)

    # Radius of the Earth in kilometers
    radius: float = 6371.0  # Earth's mean radius

    # Haversine formula
    dlat: float = lat2 - lat1
    dlon: float = lon2 - lon1

    a: float = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
    c: float = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    distance: float = radius * c

    return distance

def linearly_decreasing_weight(distance: float, max_distance: float) -> float:
    """
    Calculate a linearly decreasing weight based on the given distance
    and maximum distance.

    Args:
        distance (float): The distance at which you want to calculate the weight.
        max_distance (float): The maximum distance at which the weight becomes 0.

    Returns:
        float: The linearly decreasing weight, ranging from 1 to 0.
    """
    # Ensure that distance is within the valid range [0, max_distance]
    distance: float = max(0, min(distance, max_distance))

    # Calculate the weight as a linear interpolation
    weight: float = 1.0 - (distance / max_distance)
    
    return weight
