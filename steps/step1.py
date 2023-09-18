'''
Step 1: Removal of bad data

Drop or adjust certain records (or parts of records).
This includes outliers / out of range reports.
Determined using configuration file.
    <TO-DO> Figure out if this method is ideal.
'''

import pandas as pd
import os
import re
import sys

# Add the parent folder to sys.path
parent_dir: str = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, parent_dir)

# Local imports
from parameters.data import drop_rules

def filter_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters a DataFrame based on latitude and longitude conditions.

    Args:
    df (pd.DataFrame): The input DataFrame with 'Latitude' and 'Longitude' columns.

    Returns:
    pd.DataFrame: The filtered DataFrame with rows where latitude is between -90 and 90,
    and longitude is between -180 and 180.
    """
    
    # Define latitude and longitude range conditions
    lat_condition = (df['Latitude'] >= -90) & (df['Latitude'] <= 90)
    lon_condition = (df['Longitude'] >= -180) & (df['Longitude'] <= 180)

    # Apply the conditions to filter the DataFrame
    df_filtered = df[lat_condition & lon_condition]
    
    # Calculate number of rows filtered
    num_filtered = len(df) - len(df_filtered)
    print(f'Number of rows with invalid coordinates (removed): {num_filtered}')

    return df_filtered

def filter_stations_by_rules(dataframe: pd.DataFrame, rules_text: str) -> pd.DataFrame:
    """
    Filters a DataFrame of climate station data based on exclusion rules specified in a text format.

    Parameters:
        dataframe (pd.DataFrame): The input DataFrame containing climate station data.
        rules_text (str): A string containing exclusion rules for specific stations and years.

    Returns:
        pd.DataFrame: A filtered DataFrame with stations omitted based on the provided rules.

    Rules Format:
        The 'rules_text' should be formatted as follows:
        - Each rule is represented as a single line in the text.
        - Each line should start with the station ID followed by exclusion rules.
        - Exclusion rules consist of 'omit:' followed by the years to exclude, e.g., 'omit: 2000-2010'.
        - Years can be specified as a single year (e.g., 'omit: 2000') or as a range (e.g., 'omit: 2000-2010').
        - Year ranges can also be specified using '/' (e.g., 'omit: 2000/2002').

    Example:
        rules_text = '''
            CHM00052836  omit: 0-1948
            CHXLT909860  omit: 0-1950
            BL000085365  omit: 0-1930
            ...
        '''

    This function takes the provided rules and applies them to the input DataFrame,
    resulting in a new DataFrame with stations excluded based on the specified rules.
    """

    # Parse the rules from the provided text
    rules = {}
    for line in rules_text.split('\n'):
        if line.strip():
            match = re.match(r'([A-Z0-9]+)\s+omit:\s+(\S+)', line)
            if match:
                station_id, year_rule = match.groups()
                rules[station_id] = year_rule

    # Create a mask to identify rows to omit
    mask = pd.Series(True, index=dataframe.index)

    for station_id, year_rule in rules.items():
        try:
            # Split the year_rule into start and end years
            start_year, end_year = map(int, year_rule.split('-'))
        except ValueError:
            # Handle cases like '2011/12' or '2012-9999'
            if '/' in year_rule:
                start_year = int(year_rule.split('/')[0])
                end_year = start_year
            elif '-' in year_rule:
                start_year = int(year_rule.split('-')[0])
                end_year = int(year_rule.split('-')[1])
            else:
                continue

        # Update the mask to False for the specified range of years for the station_id
        mask &= ~((dataframe['Year'] >= start_year) & (dataframe['Year'] <= end_year) & (dataframe.index == station_id))

    # Apply the mask to filter the DataFrame
    filtered_dataframe = dataframe[mask]

    # Calculate number of rows filtered
    num_filtered = len(dataframe) - len(filtered_dataframe)
    print(f'Number of rows removed according to station exclusion rules: {num_filtered}')

    return filtered_dataframe

def step1(step0_output: pd.DataFrame) -> pd.DataFrame:
    """
    Applies data filtering and cleaning operations to the input DataFrame.

    Parameters:
        step0_output (pd.DataFrame): The initial DataFrame containing climate station data.

    Returns:
        pd.DataFrame: A cleaned and filtered DataFrame ready for further analysis.

    This function serves as a data processing step by applying two essential filtering operations:
    1. `filter_coordinates`: Filters the DataFrame based on geographical coordinates, retaining relevant stations.
    2. `filter_stations_by_rules`: Filters the DataFrame based on exclusion rules, omitting specified stations and years.

    The resulting DataFrame is cleaned of irrelevant stations and years according to specified rules
    and is ready for subsequent data analysis or visualization.
    """
        
    df_filtered = filter_coordinates(step0_output)
    df_clean = filter_stations_by_rules(df_filtered, drop_rules)
    return df_clean
