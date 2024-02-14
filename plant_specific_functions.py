import pandas as pd
import numpy as np

from data_processing_functions import stack_dataframes

def calc_existing_plant_summary(run_variables_dict,
                                scenario_financials_tables, 
                                financial_scalars_inputs,
                                end_effects=True,
                                solar_extension=True,
                                inflation_rate=0.021):
    
    """
    Calculates Existing Plants' NPV and Depreciation. Finds yearly additions to book value. 

    Parameters:
    - scenario_financials_tables (dictionary): Countains parameter information about which Aurora run to use.
    - financial_scalars_inputs (pd.Dataframe): Contains financial information.
    
    Returns:
    - pd.DataFrame: Dataframe containing Existing Plant summary by year.
    """
    
    ### 1. Set up existing resource NPV at BOY and EOY. Calculate Depreciation using these values.

    # Import NPV - BOY
    existing_plant_NPV_BOY = scenario_financials_tables['Existing Capital -  Net Book Value BOY'].set_index('Plant Name')

    # Import NPV - EOY
    existing_plant_NPV_EOY = scenario_financials_tables['Existing Capital -  Net Book Value EOY'].set_index('Plant Name')

    # Add a logical check to make sure we the number of plants is correct in both dataframes
    if len(existing_plant_NPV_BOY) != len(existing_plant_NPV_EOY):
        print('Error: The number of plants in the NPV BOY dataframe is not equal to the ones in the NPV EOY dataframe.')

    # Check if the DataFrames have the same sorting by row
    if not existing_plant_NPV_BOY.equals(existing_plant_NPV_EOY.sort_index(axis=1)):
        # If not, sort one of the DataFrames to match the other
        existing_plant_NPV_EOY = existing_plant_NPV_EOY.sort_index(axis=1)

    ### Account for extension periods if needed
    
    # Handle extension period
    def add_new_years(df, start_year, end_year, inflation_rate): 
        # Create a range of new years
        new_years = range(start_year, end_year + 1)
        # Create a new DataFrame with zeros
        new_data = pd.DataFrame(0, columns=new_years, index=df.index)
        # Update the "New Unit FOM" row with cumulative inflation rates
        variables_to_extend = list(existing_plant_NPV_BOY.index)
        for variable in variables_to_extend:
            last_value = df.loc[variable].iloc[-1]
            for year in new_years:
                last_value *= (1 + inflation_rate)
                new_data.at[variable, year] = last_value
        # Concatenate the existing DataFrame with the new DataFrame
        result_df = pd.concat([df, new_data], axis=1)
        return result_df   
    
    end_year = run_variables_dict['rev_req_end_year']
    if end_effects:
        end_year = run_variables_dict['end_effects_end_year']
    if solar_extension:
        end_year = run_variables_dict['solar_extension_end_year']
    if end_effects or solar_extension:
        existing_plant_NPV_BOY = add_new_years(existing_plant_NPV_BOY, run_variables_dict['rev_req_end_year']+1, end_year, inflation_rate)
        existing_plant_NPV_EOY = add_new_years(existing_plant_NPV_EOY, run_variables_dict['rev_req_end_year']+1, end_year, inflation_rate)

    ### Add totals
    existing_plant_NPV_BOY.loc['Total NPV BOY']= existing_plant_NPV_BOY.sum()
    existing_plant_NPV_EOY.loc['Total NPV EOY']= existing_plant_NPV_EOY.sum()
    
    ### Calculate Depreciation
    existing_plant_depreciation = existing_plant_NPV_BOY - existing_plant_NPV_EOY
    # replace negative values with 0
    existing_plant_depreciation[existing_plant_depreciation < 0] = 0
    # calculate sum
    existing_plant_depreciation = existing_plant_depreciation.drop(index=['Total NPV EOY', 'Total NPV BOY'])
    existing_plant_depreciation.loc['Total Depreciation'] = existing_plant_depreciation.sum()

    # Stack the dataframes
    existing_plant_summary = stack_dataframes([existing_plant_NPV_BOY, existing_plant_NPV_EOY, existing_plant_depreciation])


    ### 2.  Calculate Additions to existing dataframe
    
    # This is equal to Additions, not depreciation, to existing plant
    additions_to_existing_book = []
    existing_plant_years = existing_plant_NPV_EOY.columns

    for year in existing_plant_years:
        # if current year is prior to the financial input start year, additions to book is 0
        if year < financial_scalars_inputs.loc['Start Year'].values[0]:
            additions_to_existing_book.append(0)
        # if there are no prior years, use the existing year's total NPV BOY
        elif len(existing_plant_years) == 0:
            additions_to_existing_book.append(existing_plant_summary[year]['Total NPV BOY'])
        # otherwise, use (current year's NPV BOY - last year's current year's NPV BPY + last year's depreciation)
        else:
            additions_to_existing_book.append(existing_plant_summary[year]['Total NPV BOY'] - 
                                              existing_plant_summary[year - 1]['Total NPV BOY'] + 
                                              existing_plant_summary[year - 1]['Total Depreciation'])

    # Add new row to dataframe
    existing_plant_summary.loc['Additions to Existing Book'] = additions_to_existing_book


    ### 3. Calculate Depreciation "Credit Back"
    
    # Related to sale of existing plants - comes out of RB but will not be charged as depreciation

    depreciation_credit_back_df = scenario_financials_tables['Depreciation "Credit Back"'].set_index('Year')
    depreciation_credit_back_df

    # Stack the dataframes
    total_existing_plant_summary = stack_dataframes([existing_plant_summary, depreciation_credit_back_df])
    
    return existing_plant_NPV_BOY, existing_plant_NPV_EOY, existing_plant_depreciation, total_existing_plant_summary



def process_retired_plants(run_variables_dict,
                           datacenter_scenario_financials_tables, 
                           ongoing_capex_df, 
                           existing_plant_NPV_EOY, 
                           financial_scalars_inputs,
                           end_effects=True,
                           solar_extension=True,
                           inflation_rate=0.021):
    
    ### 1. Process retired plant information and summarize 
    
    # Extract retired plants data from the financial tables
    retired_plants_df = datacenter_scenario_financials_tables['Retired'].set_index('Plant Name')

    # Replace "No" values with 0 in the retired_plants_df
    retired_plants_df = retired_plants_df.replace("No", 0)

    # Identify indices where the value is 'Yes' in the retired_plants_df
    yes_indices = retired_plants_df[retired_plants_df == 'Yes'].stack().index

    # Create a temporary copy of the ongoing capital expenditure dataframe and modify the index
    ongoing_capex_temp_df = ongoing_capex_df.copy()
    ongoing_capex_temp_df.index = ongoing_capex_temp_df.index.str.replace('Ongoing CapEx - ', '')

    # Iterate through the 'Yes' indices to update retired_plants_df with NPV_EOY and ongoing_capex for each plant and year
    for yes_index in yes_indices:
        plant = yes_index[0]
        year = yes_index[1]

        # Extract NPV_EOY and ongoing_capex for the specific plant and year
        NPV_EOY_for_plant_year = existing_plant_NPV_EOY.loc[yes_index]
        ongoing_capex_for_plant_year = ongoing_capex_temp_df.loc[yes_index]

        # There is an exception for how Neenah CT is calculated
        if plant == "Neenah CT":
            ongoing_capex_for_plant_year = 0

        # Update retired_plants_df with the sum of NPV_EOY and ongoing_capex
        retired_plants_df.loc[yes_index] = NPV_EOY_for_plant_year + ongoing_capex_for_plant_year
        
    ### Account for extension periods if needed
    def add_new_years(df, start_year, end_year, inflation_rate): 
        # Create a range of new years
        new_years = range(start_year, end_year + 1)
        # Create a new DataFrame with zeros
        new_data = pd.DataFrame(0, columns=new_years, index=df.index)
        # Update the "New Unit FOM" row with cumulative inflation rates
        variables_to_extend = list(retired_plants_df.index)
        for variable in variables_to_extend:
            last_value = df.loc[variable].iloc[-1]
            for year in new_years:
                last_value *= (1 + inflation_rate)
                new_data.at[variable, year] = last_value
        # Concatenate the existing DataFrame with the new DataFrame
        result_df = pd.concat([df, new_data], axis=1)
        return result_df   
    
    end_year = run_variables_dict['rev_req_end_year']
    if end_effects:
        end_year = run_variables_dict['end_effects_end_year']
    if solar_extension:
        end_year = run_variables_dict['solar_extension_end_year']
    if end_effects or solar_extension:
        retired_plants_df = add_new_years(retired_plants_df, retired_plants_df.columns[-1]+1, end_year, inflation_rate)

    # Calculate the total sum row
    retired_plants_df.loc['Total'] = retired_plants_df.sum(numeric_only=True)

    ### 2. Additional Calculations for tax and return information

    # Get financial scalar values needed for calculations
    start_year = financial_scalars_inputs.loc['Start Year'][0]
    property_tax_rate = financial_scalars_inputs.loc['Property Tax Rate'][0]
    income_tax_rate = financial_scalars_inputs.loc['Income Tax Rate'][0]
    equity_percent_rate_base = financial_scalars_inputs.loc['Equity % Rate Base'][0]
    ROE_existing = financial_scalars_inputs.loc['Return on Equity (Existing)'][0]

    # Income tax - Estimate of Income Tax associated with retired plants
    retired_plants_df.loc['Income Tax'] = 0
    if financial_scalars_inputs.loc['Income Tax Credit Back?'][0] == 'Yes':
        for year in retired_plants_df.columns:
            if year == start_year:
                retired_plants_df.loc['Income Tax', year] = (
                    retired_plants_df.loc['Total', year] * equity_percent_rate_base * ROE_existing
                ) / (1 - income_tax_rate) * income_tax_rate
            elif year < start_year:
                retired_plants_df.loc['Income Tax', year] = 0
            else:
                average_value = retired_plants_df.loc['Total', [year, year - 1]].mean()
                retired_plants_df.loc['Income Tax', year] = average_value * equity_percent_rate_base * ROE_existing / (1 - income_tax_rate) * income_tax_rate

    # Property tax - Estimate of property tax associated with retired plants
    retired_plants_df.loc['Property Tax'] = 0
    if financial_scalars_inputs.loc['Property Tax Credit Back?'][0] == 'Yes':
        for year in retired_plants_df.columns:
            if year == start_year:
                retired_plants_df.loc['Property Tax', year] = retired_plants_df.loc['Total', year] * property_tax_rate
            elif year < start_year:
                retired_plants_df.loc['Property Tax', year] = 0
            else:
                average_value = retired_plants_df.loc['Total', [year, year - 1]].mean()
                retired_plants_df.loc['Property Tax', year] = average_value * property_tax_rate

    # Earn return on? - From Inputs
    retired_plants_df.loc['Earn Return on ?'] = financial_scalars_inputs.loc['Retired Units Earn Return On?'][0]

    # Return on % - From Inputs
    retired_plants_df.loc['Return on %'] = 0

    # Return on $ - If = No, then calculate return, mid-year convention
    retired_plants_df.loc['Earn Return on $'] = 0
    if financial_scalars_inputs.loc['Income Tax Credit Back?'][0] == 'Yes':
        for year in retired_plants_df.columns:
            if year == start_year:
                retired_plants_df.loc['Earn Return on $', year] = (
                    retired_plants_df.loc['Total', year] * retired_plants_df.loc['Return on %', year]
                )
            elif year < start_year:
                retired_plants_df.loc['Earn Return on $', year] = 0
            else:
                average_value = retired_plants_df.loc['Total', [year, year - 1]].mean()
                retired_plants_df.loc['Earn Return on $', year] = average_value * retired_plants_df.loc['Return on %', year]

    return retired_plants_df


def calculate_AFUDC_schedule(year, plant, new_capex_df, new_unit_spend_schedule_df):
    
    # Exception for the third-to-last column
    if year == new_capex_df.columns[-3]:
        year2_val = new_capex_df.loc[plant, year + 2] * new_unit_spend_schedule_df.loc[2, plant] 
        year1_val = new_capex_df.loc[plant, year + 1] * new_unit_spend_schedule_df.loc[3, plant]
        AFUDC_sched_val = year1_val + year2_val 
        
    # Exception for the second-to-last column
    elif year == new_capex_df.columns[-2]:
        AFUDC_sched_val = new_capex_df.loc[plant, year + 1] * new_unit_spend_schedule_df.loc[3, plant]
    
    # Exception for the last column
    elif year == new_capex_df.columns[-1]:
        AFUDC_sched_val = 0
        
    else:
        # Normal Calculations
        year3_val = new_capex_df.loc[plant, year + 3] * new_unit_spend_schedule_df.loc[1, plant] 
        year2_val = new_capex_df.loc[plant, year + 2] * new_unit_spend_schedule_df.loc[2, plant] 
        year1_val = new_capex_df.loc[plant, year + 1] * new_unit_spend_schedule_df.loc[3, plant]
        
        AFUDC_sched_val = year1_val + year2_val + year3_val

    return AFUDC_sched_val


def calculate_AFUDC_with_rate(year, plant, new_capex_df, new_unit_spend_schedule_with_metadata_df):
   
    capex = new_capex_df.loc[plant, year]
    AFUDC_increase_to_cap_cost = new_unit_spend_schedule_with_metadata_df.loc['AFUDC Increase to Capital Cost', plant]

    return capex * AFUDC_increase_to_cap_cost