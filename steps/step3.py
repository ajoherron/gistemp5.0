'''
Step 3: Gridding of cells

There are 8000 cells across the globe.
Each cell's values are computed using station records within a 1200km radius.
    - Contributions are weighted according to distance to cell center
    (linearly decreasing to 0 at distance 1200km)
'''

import math
from typing import Tuple

import numpy as np
import pandas as pd
from pandas import Series


def calculate_area(row: Series) -> float:
    earth_radius_km: float = 6371.0
    delta_longitude: float = np.radians(row['Eastern'] - row['Western'])
    southern_latitude: float = np.radians(row['Southern'])
    northern_latitude: float = np.radians(row['Northern'])
    area: float = (earth_radius_km ** 2) * delta_longitude * (np.sin(northern_latitude) - np.sin(southern_latitude))
    return area


def calculate_center_coordinates(row: pd.Series) -> Tuple[float, float]:
    """Calculate the center latitude and longitude for a given box.

    Args:
        row (pd.Series): A Pandas Series representing a row of the DataFrame with ('southern', 'northern', 'western', 'eastern') coordinates.

    Returns:
        Tuple[float, float]: A tuple containing the center latitude and longitude.
    """
    center_latitude = 0.5 * (math.sin(row['Southern'] * math.pi / 180) + math.sin(row['Northern'] * math.pi / 180))
    center_longitude = 0.5 * (row['Western'] + row['Eastern'])
    center_latitude = math.asin(center_latitude) * 180 / math.pi
    return center_latitude, center_longitude


def generate_80_cell_grid() -> pd.DataFrame:
    """Generate an 80-cell grid DataFrame with columns for southern, northern, western, eastern,
    center_latitude, and center_longitude coordinates.

    Returns:
        pd.DataFrame: The generated DataFrame.
    """
    grid_data = []
    
    # Number of horizontal boxes in each band
    # (proportional to the thickness of each band)
    band_boxes = [4, 8, 12, 16]
    
    # Sines of latitudes
    band_altitude = [1, 0.9, 0.7, 0.4, 0]

    # Generate the 40 cells in the northern hemisphere
    for band in range(len(band_boxes)):
        n = band_boxes[band]
        for i in range(n):
            lats = 180 / math.pi * math.asin(band_altitude[band + 1])
            latn = 180 / math.pi * math.asin(band_altitude[band])
            lonw = -180 + 360 * float(i) / n
            lone = -180 + 360 * float(i + 1) / n
            box = (lats, latn, lonw, lone)
            grid_data.append(box)

    # Generate the 40 cells in the southern hemisphere by reversing the northern hemisphere cells
    for box in grid_data[::-1]:
        grid_data.append((-box[1], -box[0], box[2], box[3]))

    # Create a DataFrame from the grid data
    df = pd.DataFrame(grid_data, columns=['Southern', 'Northern', 'Western', 'Eastern'])

    # Calculate center coordinates for each box and add them as new columns
    center_coords = df.apply(calculate_center_coordinates, axis=1)
    df[['Center_Latitude', 'Center_Longitude']] = pd.DataFrame(center_coords.tolist(), index=df.index)

    return df
    

def interpolate(x: float, y: float, p: float) -> float:
    return y * p + (1 - p) * x


def generate_8000_cell_grid(grid_80):

    # Initialize an empty list to store subboxes
    subbox_list = []

    for index, row in grid_80.iterrows():
        alts = math.sin(row['Southern'] * math.pi / 180)
        altn = math.sin(row['Northern'] * math.pi / 180)

        for y in range(10):
            s = 180 * math.asin(interpolate(alts, altn, y * 0.1)) / math.pi
            n = 180 * math.asin(interpolate(alts, altn, (y + 1) * 0.1)) / math.pi
            for x in range(10):
                w = interpolate(row['Western'], row['Eastern'], x * 0.1)
                e = interpolate(row['Western'], row['Eastern'], (x + 1) * 0.1)

                # Create a DataFrame for the subbox
                subbox_df = pd.DataFrame({'Southern': [s], 'Northern': [n], 'Western': [w], 'Eastern': [e]})

                # Append the subbox DataFrame to the list
                subbox_list.append(subbox_df)

    # Concatenate all subboxes into a single DataFrame
    grid_8000 = pd.concat(subbox_list, ignore_index=True)

    # Calculate center coordinates for each box and add them as new columns
    center_coords = grid_8000.apply(calculate_center_coordinates, axis=1)
    grid_8000[['Center_Latitude', 'Center_Longitude']] = pd.DataFrame(center_coords.tolist(), index=grid_8000.index)

    # Calculate area of all 8000 cells
    grid_8000['Area'] = grid_8000.apply(calculate_area, axis=1)

    # Print the resulting DataFrame
    return grid_8000

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

def nearby_stations(grid_df, station_df):

    # Initialize an empty list to store station IDs and weights as dictionaries
    station_weights_within_radius = []

    # Maximum distance for the weight calculation (e.g., 1200.0 km)
    max_distance = 1200.0

    # Use tqdm to track progress
    for index, row in tqdm(grid_df.iterrows(), total=len(grid_df), desc="Processing"):
        center_lat = row['Center_Latitude']
        center_lon = row['Center_Longitude']

        # Calculate distances for each station in station_df
        distances = station_df.apply(lambda x: haversine_distance(center_lat, center_lon, x['Latitude'], x['Longitude']), axis=1)

        # Find station IDs within the specified radius
        nearby_stations = station_df[distances <= max_distance]

        # Calculate weights for each nearby station
        weights = nearby_stations.apply(lambda x: linearly_decreasing_weight(distances[x.name], max_distance), axis=1)

        # Create a dictionary of station IDs and weights
        station_weights = dict(zip(nearby_stations['Station_ID'], weights))

        # Append the dictionary to the result list
        station_weights_within_radius.append(station_weights)

    # Add the list of station IDs and weights as a new column
    grid_df['Nearby_Stations'] = station_weights_within_radius

    # Set index name
    grid_df.index.name = 'Box_Number'
    
    return grid_df