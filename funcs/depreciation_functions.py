import pandas as pd
import numpy as np


def create_book_depreciation_schedule(cost_vector, depreciation_length, fixed_start_year = None):

    # Extract years during which depreciations will come in from the column names of the cost_vector DataFrame
    depreciation_start_years = cost_vector.loc[:, (cost_vector != 0).any(axis=0)].columns.astype(int)
    
    # If we have a set start year we want to use for depreciation, clip the depreciation years to start with that year
    if fixed_start_year is not None:
        # Find the index of the start_year in the array
        start_index = np.argmax(depreciation_start_years >= fixed_start_year)
        # Return the filtered array from the start_year onwards
        depreciation_start_years = depreciation_start_years[start_index:]

    # Make a vector of years during which depreciation will occur
    # To do, we take the last year we have depreciation come in and extend that by the depreciation length
    depreciation_years = np.concatenate((depreciation_start_years, 
                                         np.arange(depreciation_start_years[-1] + 1, depreciation_start_years[-1] + depreciation_length, 1))) 

    # Initialize an empty DataFrame
    depreciation_schedule = pd.DataFrame(index=depreciation_start_years, columns=depreciation_years)
    
    # Fill in the depreciation values for each year
    for year in depreciation_start_years:
        # Calculate the amount we depreciate by each year (total depreciation / depreciation period)
        depreciation_value = (cost_vector[year] / depreciation_length).values 
        # Fill in each year's line
        for i in range(year, year + depreciation_length):
            depreciation_schedule.at[year, i] = depreciation_value
            
    # Reindex to include missing years, fill NaN values with 0, and sort annually
    full_range_of_years = np.arange(depreciation_years.min(), depreciation_years.max() + 1)
    depreciation_schedule = depreciation_schedule.reindex(index=full_range_of_years, columns=full_range_of_years, fill_value=0)
    depreciation_schedule = depreciation_schedule[depreciation_schedule.columns.sort_values()]
    
    # Insert a new column "Annual CapEx" at the start
    depreciation_schedule.insert(0, "Annual CapEx", cost_vector.squeeze())
    
    # Fill NaN values with 0
    depreciation_schedule = depreciation_schedule.fillna(0)
    
    # Add a row at the bottom that sums every column
    depreciation_schedule.loc["Annual Book Depreciation"] = depreciation_schedule.sum()

    return(depreciation_schedule)


def create_tax_depreciation_schedule(cost_vector, depreciation_length, tax_depreciation_schedules, fixed_start_year = None):

    # Find the correct tax depreciation schedule
    curr_tax_depreciation_schedule = tax_depreciation_schedules[tax_depreciation_schedules['Depreciation Schedule'].str.contains(str(depreciation_length))]
    curr_tax_depreciation_schedule = curr_tax_depreciation_schedule.drop(columns='Depreciation Schedule')
    curr_tax_depreciation_schedule = curr_tax_depreciation_schedule.values[0]

    # Extract years during which depreciations will come in from the column names of the cost_vector DataFrame
    depreciation_start_years = cost_vector.loc[:, (cost_vector != 0).any(axis=0)].columns.astype(int)

    # If we have a set start year we want to use for depreciation, clip the depreciation years to start with that year
    if fixed_start_year is not None:
        # Find the index of the start_year in the array
        start_index = np.argmax(depreciation_start_years >= fixed_start_year)
        # Return the filtered array from the start_year onwards
        depreciation_start_years = depreciation_start_years[start_index:]

    # Make a vector of years during which depreciation will occur
    # To do, we take the last year we have depreciation come in and extend that by the depreciation length
    depreciation_years = np.arange(min(depreciation_start_years), max(depreciation_start_years) + depreciation_length + 1, 1)
   
    # Initialize an empty DataFrame
    depreciation_schedule = pd.DataFrame(index=depreciation_start_years, columns=depreciation_years)

    # Fill in the depreciation values for each year
    for year in depreciation_start_years:

        # Calculate the amount we depreciate by each year (total depreciation * MACRS percent for each year)
        depreciation_values = cost_vector[year].values * curr_tax_depreciation_schedule
        # Put the values in a format we can insert into the depreciation table
        data_to_insert = np.trim_zeros(depreciation_values)
        data_to_insert = np.array([data_to_insert]).astype('f')

        # Specify the first column name and the row name where you want to insert the array
        first_col_name_to_insert = year  # Adjust as needed
        row_name_to_insert = year  # Adjust as needed

        # Get the index of the first column to determine the insertion location
        col_index_to_insert = depreciation_schedule.columns.get_loc(first_col_name_to_insert)

        # Insert the array into the DataFrame at the specified location
        depreciation_schedule.loc[row_name_to_insert, depreciation_schedule.columns[col_index_to_insert]:depreciation_schedule.columns[col_index_to_insert + data_to_insert.shape[1] - 1]] = data_to_insert
       
    # Reindex to include missing years, fill NaN values with 0, and sort annually
    full_range_of_years = np.arange(depreciation_years.min(), depreciation_years.max() + 1)
    depreciation_schedule = depreciation_schedule.reindex(index=full_range_of_years, columns=full_range_of_years, fill_value=0)
    depreciation_schedule = depreciation_schedule[depreciation_schedule.columns.sort_values()]

    # Fill NaN values with 0
    depreciation_schedule = depreciation_schedule.fillna(0)
    
    # Insert a new column "Annual CapEx" at the start
    depreciation_schedule.insert(0, "Annual CapEx", cost_vector.squeeze())

    # Add a row at the bottom that sums every column
    depreciation_schedule.loc["Annual Tax Depreciation"] = depreciation_schedule.sum()

    return(depreciation_schedule)
