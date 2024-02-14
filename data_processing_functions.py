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
                # Remove trailing or leading white spaces
                data_table = remove_whitespaces_from_df(data_table)
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
        # Remove trailing or leading white spaces
        data_table = remove_whitespaces_from_df(data_table)
        # Now df contains your data with only columns that have column names
        tables[current_table_name] = data_table
        
    return tables


def remove_whitespaces_from_df_old(df):
    """
    Remove leading and trailing whitespaces from column headers and index values of a DataFrame.
    This insures we can index all input dataframes correctly (Excel dataframes often have trailing white spaces).

    Parameters:
    - df (pd.DataFrame): The input DataFrame.

    Returns:
    - pd.DataFrame: The DataFrame with cleaned column headers.
    """
    
    # Check if the column name values are strings, then strip whitespaces
    if all(isinstance(columns, str) for columns in df.columns):
        # Remove leading and trailing whitespaces from column headers row labels
        df.columns = df.columns.str.strip()
        
    # Check if the index values are strings, then strip whitespaces
    if all(isinstance(index, str) for index in df.index):
        df.index = df.index.str.strip()

    return df


def remove_whitespaces_from_df(df):
    """
    Remove leading and trailing whitespaces from all values, column headers, and index values of a DataFrame.
    This ensures we can handle whitespaces in all parts of the DataFrame.

    Parameters:
    - df (pd.DataFrame): The input DataFrame.

    Returns:
    - pd.DataFrame: The DataFrame with cleaned values, column headers, and index values.
    """
    
    # Remove leading and trailing whitespaces from all values
    df = df.applymap(lambda x: x.strip() if isinstance(x, str) else x)

    # Check if the column name values are strings, then strip whitespaces
    if all(isinstance(columns, str) for columns in df.columns):
        # Remove leading and trailing whitespaces from column headers
        df.columns = df.columns.str.strip()
        
    # Check if the index values are strings, then strip whitespaces
    if all(isinstance(index, str) for index in df.index):
        df.index = df.index.str.strip()

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
    concatenated_df = pd.concat(dfs)[sorted(list(all_columns))]
    
    # Replace NaN values with None (to make it clear we are missing values rather than have compromised data)
    concatenated_df.replace({np.nan: None}, inplace=True)
   
    return(concatenated_df)



def convert_capacity_table_to_cost_table(capacity_df, 
                                         cost_per_kw_df, 
                                         inflation_vector = None, 
                                         name_adjuster = None):
    
    # Before we can multiply the capacity and cost tables, we need to ensure they have the same years
        # In this function, the input dataframes have years as the column names
        # So, we will filter by common column names

    # Extract common column names
    common_columns = capacity_df.columns.intersection(cost_per_kw_df.columns)

    # Filter dataframes based on common columns
    capacity_df = capacity_df[common_columns]
    cost_per_kw_df = cost_per_kw_df[common_columns]

    # Reindex to retain the original order of rows in capacity_df
    cost_per_kw_df = cost_per_kw_df.reindex(capacity_df.index)

    # Multiply cost dataframe ($/kw/year) by Capacity and convert to MW by multiplying by 1,000 
    total_cost_df = cost_per_kw_df * capacity_df * 1000

    # If you are adding inflation, multipy your cost dataframe by the infaltion vector
    if inflation_vector is not None:
        
        # Filter the Inflation Vector to include only values that exist in DataFrame columns
        filtered_inflation_vector = inflation_vector[inflation_vector.index.isin(total_cost_df.columns)]
        
        # Multiply each row of the DataFrame by the inflation vector 
        total_cost_df = total_cost_df * filtered_inflation_vector
        total_cost_df = total_cost_df.fillna(0)

    # Add a string to the existing index names
    if name_adjuster is not None:
        new_index_names = [f'{name_adjuster} {index}' for index in total_cost_df.index]
        total_cost_df.rename(index=dict(zip(total_cost_df.index, new_index_names)), inplace=True)
    
    return(total_cost_df)