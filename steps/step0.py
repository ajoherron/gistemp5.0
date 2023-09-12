'''
Step 0: Downloading Data

Combining diverse inputs into a single dataset

Inputs include:
    - GHCN v4 data
    - ERRST v5 data (later on?)
'''

# Standard library imports
import requests
import sys
import os

# 3rd-party library imports
import pandas as pd
import numpy as np

# Add the parent folder to sys.path
parent_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Local imports
from parameters.data import GHCN_temp_url, GHCN_meta_url


def get_GHCN_data(temp_url, meta_url):

    '''
    Retrieves and formats temperature data from the Global Historical Climatology Network (GHCN) dataset.

    Args:
    temp_url (str): The URL to the temperature data file in GHCN format.
    meta_url (str): The URL to the metadata file containing station information.

    Returns:
    pd.DataFrame: A Pandas DataFrame containing temperature data with station metadata.
    
    This function sends an HTTP GET request to the temperature data URL, processes the data to create
    a formatted DataFrame, replaces missing values with NaN, converts temperature values to degrees Celsius,
    and merges the data with station metadata based on station IDs. The resulting DataFrame includes
    columns for station latitude, longitude, and name, and is indexed by station IDs.
    '''

    try:
        # Send an HTTP GET request to the URL
        response = requests.get(temp_url)

        # Check if the request was successful
        if response.status_code == 200:
            
            # Get the content of the response
            file_data = response.content.decode("utf-8")

            # Create a list to store formatted data
            formatted_data = []

            # Loop through file data
            for line in file_data.split('\n'):
                
                # Check if line is not empty
                if line.strip():
                    
                    # Extract relevant data
                    # (Using code from GHCNV4Reader())
                    station_id = line[:11]
                    year = int(line[11:15])
                    values = [int(line[i:i+5]) for i in range(19, 115, 8)]
                    
                    # Append data to list
                    formatted_data.append([station_id, year] + values)

            # Create DataFrame from formatted data
            column_names = ['Station_ID', 'Year'] + [f'Month_{i}' for i in range(1, 13)]
            df_GHCN = pd.DataFrame(formatted_data, columns=column_names)
            
            # Replace -9999 with NaN
            df_GHCN.replace(-9999, np.nan, inplace=True)
            
            # Format data - convert to degrees C
            month_columns = [f'Month_{i}' for i in range(1, 13)]
            df_GHCN[month_columns] = df_GHCN[month_columns].divide(100)

        else:
            print("Failed to download the file. Status code:", response.status_code)

    except Exception as e:
        print("An error occurred:", str(e))

    # Define the column widths, create meta data dataframe
    column_widths = [11, 9, 10, 7, 3, 31]
    df_meta = pd.read_fwf(meta_url, widths=column_widths, header=None,
                          names=['Station_ID', 'Latitude', 'Longitude', 'Elevation', 'State', 'Name'])
    # Merge on station ID, set index
    df = pd.merge(df_GHCN, df_meta[['Station_ID', 'Latitude', 'Longitude', 'Name']], on='Station_ID', how='left')
    df = df.set_index('Station_ID')

    return df


def step0():
    '''
    Performs the initial data processing steps for the GHCN temperature dataset.

    Returns:
    pd.DataFrame: A Pandas DataFrame containing filtered and formatted temperature data.
    
    This function retrieves temperature data from the Global Historical Climatology Network (GHCN) dataset,
    processes and formats the data, and returns a DataFrame. The data is first fetched using specified URLs,
    and is returned for further analysis.
    '''
    df_GHCN = get_GHCN_data(GHCN_temp_url, GHCN_meta_url)
    return df_GHCN
