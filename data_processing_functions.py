import pandas as pd
import numpy as np


def read_excel_with_tables(df):
    """
    Read a single Excel sheet with multiple tables separated by an empty row.
    Each table is identified by the word "table" in a cell, and its name is in the next cell.

    Parameters:
    - file_path: str, path to the Excel file
    - sheet_name: str, name of the sheet in the Excel file

    Returns:
    - Dictionary of DataFrames, where keys are table names and values are corresponding DataFrames
    """

    # Initialize variables
    tables = {}
    current_table_name = None
    current_table_start_row = None

    # Iterate through rows
    for index, row in df.iterrows():
        if "table" in str(row.values).lower():
            # Save the current table if it exists
            if current_table_name is not None:
                data_table = df.iloc[current_table_start_row:index - 1, :].reset_index(drop=True)
                # Set the column names to be the values in the first row
                data_table.columns = data_table.iloc[0]
                # Drop the first row, which is now redundant as column headers
                data_table = data_table[1:]
                # Drop columns without names
                data_table = data_table.dropna(axis=1, how='all')
                # Now df contains your data with only columns that have column names
                tables[current_table_name] = data_table

            # Update variables for the new table
            current_table_name = str(row[1]) # this takes the value from the cell next to the cell that says "table"
            current_table_start_row = index + 1  # Assuming the next row is empty
            
    # Add the last table
    if current_table_name is not None:
        data_table = df.iloc[current_table_start_row:index + 1, :].reset_index(drop=True)
        # Set the column names to be the values in the first row
        data_table.columns = data_table.iloc[0]
        # Drop the first row, which is now redundant as column headers
        data_table = data_table[1:]
        # Drop columns without names
        data_table = data_table.dropna(axis=1, how='all')
        # Now df contains your data with only columns that have column names
        tables[current_table_name] = data_table
        
    return tables



def remove_whitespaces_from_df(df):
    """
    Remove leading and trailing whitespaces from column headers of a DataFrame.
    This insures we can index all input dataframes correctly (Excel dataframes often have trailing white spaces).

    Parameters:
    - df (pd.DataFrame): The input DataFrame.

    Returns:
    - pd.DataFrame: The DataFrame with cleaned column headers.
    """
    # Remove leading and trailing whitespaces from column headers
    df.columns = df.columns.str.strip()

    return df
    
    

def stack_dataframes(dfs, print_warnings=True):
    """
    Stack a list of DataFrames vertically, ensuring they have the same columns.

    Parameters:
    - dfs (list): List of DataFrames to be stacked.
    - print_warnings (bool, optional): Whether to print warnings about missing columns. Default is True.

    Returns:
    - pd.DataFrame: Vertically stacked DataFrame.
    """
    
    # Find the DataFrame with the most columns
    max_columns_df = max(dfs, key=lambda x: len(x.columns))

    # Find the union of all columns
    all_columns = set(max_columns_df.columns)

    # Print a message about missing columns for each DataFrame
    if print_warnings == True:
        df_names = [f"df{i}" for i in range(1, len(dfs) + 1)]
        for df_name, df in zip(df_names, dfs):
            missing_columns = all_columns - set(df.columns)
            if missing_columns:
                missing_columns_as_strings = {str(value) for value in missing_columns}
                print(f"{df_name} is missing columns: {', '.join(missing_columns_as_strings)}")

    # Ensure that all DataFrames have the same columns
    dfs = [df.reindex(columns=all_columns) for df in dfs]

    # Concatenate the DataFrames vertically
    concatenated_df = pd.concat(dfs)
    
    # Replace NaN values with None (to make it clear we are missing values rather than have compromised data)
    concatenated_df.replace({np.nan: None}, inplace=True)
   
    return(concatenated_df)