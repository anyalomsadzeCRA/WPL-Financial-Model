import pandas as pd
import numpy as np

from data_processing_functions import stack_dataframes

def sum_annual_depreciation(depreciation_dict):
    
    # List to store individual dataframes
    dfs = []

    # Get all unique columns across all dataframes
    all_columns = set()
    for df in depreciation_dict.values():
        if isinstance(df, pd.DataFrame):
            all_columns.update(df.columns)
    all_columns.remove('Annual CapEx')   

    # Iterate through the values in the dictionary
    for df in depreciation_dict.values():
        # Check if the value is a DataFrame
        if isinstance(df, pd.DataFrame):
            # Remove 'Annual CapEx' column if it exists
            df = df.drop('Annual CapEx', axis=1)

            # Extract the sum row that is the last row of each df
            depreciation_row = df.iloc[-1]
            
            # Append the row as a new DataFrame with all columns
            full_row = pd.Series(index=all_columns)
            full_row[depreciation_row.index] = depreciation_row
            dfs.append(full_row)
            
    # Concatenate all the individual dataframes along the columns
    concatenated_df = pd.concat(dfs, axis=1, ignore_index=True)

    # Take the sum of each column
    result_df = pd.DataFrame(concatenated_df.sum(axis=1), columns=['Sum Annual Depreciation']).transpose()

    # Convert column names to numeric and then sort
    result_df.columns = pd.to_numeric(result_df.columns, errors='coerce').astype('Int64')
    result_df = result_df.sort_index(axis=1)

    return result_df



def calc_deferred_taxes(tax_rate,
                        BOY_tax, 
                        EOY_tax,
                        book_depreciation_tables_dict,
                        tax_depreciation_tables_dict,
                        existing_plant_depreciation, 
                        total_existing_plant_summary, 
                        existing_plant_NPV_BOY,
                        blended_tax_rate = False, 
                        blended_deferred_tax_new_capital=None,
                        blended_deferred_tax_existing_capital=None,
                        blended_deferred_tax_liability=None):
    
    ### 1. Calculations 
    
    # New Capital Tax
    book_depreciation_new_capital = sum_annual_depreciation(book_depreciation_tables_dict)
    tax_depreciation_new_capital = sum_annual_depreciation(tax_depreciation_tables_dict)
    net_new_capital = tax_depreciation_new_capital - book_depreciation_new_capital 
        
    if blended_tax_rate is False:
        deferred_tax_new_capital = net_new_capital * tax_rate
    else:
        deferred_tax_new_capital = blended_deferred_tax_new_capital
    cumulative_deferred_income_taxes_new_capital = deferred_tax_new_capital.cumsum(axis=1)
    starting_deferred_tax_liability = pd.DataFrame(0, index=['total'], columns=deferred_tax_new_capital.columns)
    ending_deferred_tax_liability = pd.DataFrame(0, index=['total'], columns=deferred_tax_new_capital.columns)
    for year in deferred_tax_new_capital.columns[1:]:
        ending_deferred_tax_liability[year - 1] = starting_deferred_tax_liability[year - 1][0] + deferred_tax_new_capital[year - 1][0]
        starting_deferred_tax_liability[year] = ending_deferred_tax_liability[year - 1][0]

    # Existing Capital Tax Value
    tax_depreciation_existing = BOY_tax - EOY_tax

    # Deferred Tax Liability Existing 
    existing_plant_total_depreciation = existing_plant_depreciation.loc[['Total Depreciation']]
    existing_plant_total_depreciation.index.values[0] = 'Total'
    depreciation_credit_back = total_existing_plant_summary.loc[['Depreciation "Credit Back"']]
    depreciation_credit_back.index.values[0] = 'Total'
    book_depreciation_existing_capital = existing_plant_total_depreciation - depreciation_credit_back.fillna(0)
    deferred_tax_existing_capital = (tax_depreciation_existing - book_depreciation_existing_capital) * tax_rate
    if blended_tax_rate is True:
        deferred_tax_existing_capital = blended_deferred_tax_existing_capital
        
    # initialize deferred_tax_liability_existing's first year's value and fill in next years
    existing_plant_NPV_BOY_total = existing_plant_NPV_BOY.loc[['Total NPV BOY']]
    existing_plant_NPV_BOY_total.index.values[0] = 'Total'
    if blended_tax_rate is False:
        deferred_tax_liability_existing = pd.DataFrame(0, index=['total'], columns=BOY_tax.columns)
        earliest_year = existing_plant_NPV_BOY_total.columns.intersection(BOY_tax.columns)[0]
        deferred_tax_liability_existing.iloc[0,0] = (existing_plant_NPV_BOY_total.loc[:, earliest_year][0] - BOY_tax.loc[:, earliest_year][0]) * tax_rate
        for year in deferred_tax_liability_existing.columns[1:]:
            deferred_tax_liability_existing[year] = deferred_tax_liability_existing[year-1][0] + deferred_tax_existing_capital[year-1][0]
    else:
        deferred_tax_liability_existing = blended_deferred_tax_liability
        
    #### 2. Stack and return dfs
    index_names_list = [ 'Starting Deferred Tax Liability',
        'Deferred Tax - New Capital',
        'Ending Deferred Tax Liability',
        'Book Depreciation - New Capital',
        'Tax Depreciation - New Capital',
        'Net (T Less B) - New Capital',
        'Cumulative Deferred Income Taxes - New Capital',
        'Tax Value - BOY',
        'Tax Value - EOY',
        'Tax Depreciation - Existing',
        'Deferred Tax Liability - Existing',
        'Book Depreciation - Existing Capital',
        'Deferred Tax - Existing Capital']

    dfs = [starting_deferred_tax_liability,
            deferred_tax_new_capital,
            ending_deferred_tax_liability,
            book_depreciation_new_capital,
            tax_depreciation_new_capital,
            net_new_capital,
            cumulative_deferred_income_taxes_new_capital,
            BOY_tax,
            EOY_tax,
            tax_depreciation_existing,
            deferred_tax_liability_existing,
            book_depreciation_existing_capital,
            deferred_tax_existing_capital]

    deferred_tax_df = stack_dataframes(dfs, print_warnings=False)
    deferred_tax_df.index = index_names_list
    
    return deferred_tax_df
