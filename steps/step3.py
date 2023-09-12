'''
Step 3: Gridding of cells

There are 8000 cells across the globe.
Each cell's values are computed using station records within a 1200km radius.
    - Contributions are weighted according to distance to cell center
    (linearly decreasing to 0 at distance 1200km)
'''

#################################
# Standard library imports
import sys
import os

# Add the parent folder to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Local imports
from steps import step0, step1

# Step 0
print('--- Running Step 0 ---')
step0_output = step0.step0()

# Step 1
print('--- Running Step 1 ---')
step1_output = step1.step1(step0_output)

################################################

import numpy as np
import pandas as pd
import math

def incircle(df, arc, lat, lon):
    '''
    Filters a DataFrame of stations and returns a new DataFrame with
    stations within a certain great circle arc distance from a specified
    point (given by lat and lon in degrees) and their associated weights.

    Args:
    df (pd.DataFrame): DataFrame containing station records.
    arc (float): Great circle arc distance in radians.
    lat (float): Latitude of the point of interest in degrees.
    lon (float): Longitude of the point of interest in degrees.

    Returns:
    pd.DataFrame: New DataFrame with station records and weights.
    
    This function filters the input DataFrame and returns a new DataFrame
    containing station records within the specified distance along with their
    associated weights. The weight is determined based on the chord length on
    a unit circle and is added as a new "Weight" column in the output DataFrame.
    '''

    # Convert lat, lon to radians
    lat_rad = np.radians(lat)
    lon_rad = np.radians(lon)

    # Calculate trig values for the point of interest
    cosarc = np.cos(arc)
    coslat = np.cos(lat_rad)
    sinlat = np.sin(lat_rad)
    #coslon = np.cos(lon_rad)
    #sinlon = np.sin(lon_rad)

    # Create an empty DataFrame to store filtered records and weights
    result_df = pd.DataFrame(columns=df.columns.tolist() + ['Weight'])

    for idx, row in df.iterrows():
        s_lat = np.radians(row['Latitude'])
        s_lon = np.radians(row['Longitude'])

        # Cosine of angle subtended by arc between 2 points on a unit sphere
        cosd = np.sin(s_lat) * sinlat + np.cos(s_lat) * coslat * (np.cos(s_lon - lon_rad))

        if cosd > cosarc:
            d = np.sqrt(2 * (1 - cosd))  # chord length on unit sphere
            weight = 1.0 - (d / arc)

            # Create a new row with the weight and append it to the result DataFrame
            new_row = row.tolist() + [weight]
            result_df = result_df.append(pd.Series(new_row, index=result_df.columns), ignore_index=True)

    return result_df

step3_output = incircle(step1_output)