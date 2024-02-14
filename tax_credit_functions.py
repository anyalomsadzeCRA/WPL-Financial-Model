import pandas as pd
import numpy as np
from datetime import date

from data_processing_functions import stack_dataframes

def calculate_ptc(inflation_vector, financial_inputs_tables):
    
    # PTC_Price_Kossuth calculation
    PTC_Price_Kossuth = (inflation_vector * 25).astype(float).round().to_frame(name='PTC Price Kossuth').T

    # H2_PTC calculation
    H2_PTC = (inflation_vector * 3).astype(float).round().to_frame(name='H2 PTC').T

    # PTC_and_45Q_Tax_Credit DataFrame
    PTC_and_45Q_Tax_Credit = financial_inputs_tables['PTC and 45Q Tax Credit'].set_index('Year')

    # PTC_Price calculation
    PTC_Price = PTC_and_45Q_Tax_Credit.loc['PTC Price'].to_frame(name='PTC Price').T

    # Tax_Credit_45Q calculation
    Tax_Credit_45Q = PTC_and_45Q_Tax_Credit.loc['45Q tax credit'].to_frame(name='45Q Tax Credit').T

    # Stack DataFrames
    PTC_df = stack_dataframes([PTC_Price_Kossuth, PTC_Price, H2_PTC, Tax_Credit_45Q], print_warnings=False)

    return PTC_df


def calculate_generation(ptcs_and_itcs_tables, aurora_portfolio_resource, aurora_condition, aurora_iteration, 
                         aurora_portfolio_ID, hydrogen_island_inputs, cumulative_installed_capacity_MW_df, 
                         iteration, CCS_inputs_tables):
    
    # Wind Generation
    wind_ptcs = ptcs_and_itcs_tables['Wind PTC']
    wind_ptcs = wind_ptcs[wind_ptcs.Iteration == iteration]
    wind_ptcs = wind_ptcs.drop(columns='Iteration').set_index('Year')
    wind_generation = wind_ptcs.rename(index={'Wind Generation * PTC': 'Qualifying New Wind'})
    
    # Solar Generation
    solar_ptcs = ptcs_and_itcs_tables['Solar PTC']
    solar_ptcs = solar_ptcs[solar_ptcs.Iteration == iteration]
    solar_ptcs = solar_ptcs.drop(columns='Iteration').set_index('Year')
    solar_generation_postCA1CA2 = solar_ptcs.loc[['Future Solar (post-CA1 and CA2) Generation * PTC']]
    solar_generation_postCA1CA2 = solar_generation_postCA1CA2.rename(index={'Future Solar (post-CA1 and CA2) Generation * PTC': 'Qualifying New Solar (Post-CA1/CA2)'})
    solar_generation_CA1 = solar_ptcs.loc[['CA1 Generation * PTC']]
    solar_generation_CA1 = solar_generation_CA1.rename(index={'CA1 Generation * PTC': 'CA1 Solar'})
    solar_generation_CA2 = solar_ptcs.loc[['CA2 Generation * PTC']]
    solar_generation_CA2 = solar_generation_CA2.rename(index={'CA2 Generation * PTC': 'CA2 Solar'})

     # Filter the Auroura portfolio resource data to get Kossoth info
    condition_mask = aurora_portfolio_resource['Condition'] == aurora_condition
    run_id_mask = aurora_portfolio_resource['Run_ID'] == aurora_iteration
    portfolio_id_mask = aurora_portfolio_resource['Portfolio_ID'] == aurora_portfolio_ID
    resource_name_mask = aurora_portfolio_resource['Resource_Name'] == "Kossuth"
    aurora_resource_summary_filtered = aurora_portfolio_resource[condition_mask & run_id_mask & portfolio_id_mask & resource_name_mask]
    aurora_resource_summary_filtered = aurora_resource_summary_filtered.rename(columns={'Time_Period': 'Year'})
    aurora_resource_summary_filtered = aurora_resource_summary_filtered.set_index('Year').sort_index()
    kossuth = aurora_resource_summary_filtered[['Output_MWH']].T
    kossuth = kossuth.rename(index={'Output_MWH': 'Kossuth'})
    
    # hydrogen equals to installed capapcity * production in kg for the given iteration.
    # we then also zero out any hydrogen less than the 'hydrogen date' or 10 years more than the hydrogen date
    h2_production_by_scenario = hydrogen_island_inputs['H2 Production (kg/MW-yr)'].set_index('Scenario')
    h2_production = h2_production_by_scenario[iteration].values[0]
    hydrogen = cumulative_installed_capacity_MW_df.loc[['H2 Island']] * h2_production
    hydrogen = hydrogen.rename(index={'H2 Island': 'Hydrogen'})
    hydrogen_date = date(2035, 1, 1)
    hydrogen = hydrogen.apply(lambda col: col if int(col.name) < hydrogen_date.year or int(col.name) < hydrogen_date.year + 10 else 0)

    CCS_CO2 = CCS_inputs_tables['CO2 Tons'][CCS_inputs_tables['CO2 Tons'].Aurora_Iteration == aurora_iteration]
    CCS_CO2 = CCS_CO2.reset_index().drop(columns=['Aurora_Iteration', 'index'])
    CCS_CO2 = CCS_CO2.rename(index={0: 'Gas CCGT with CCS'})
    CCS_date = date(2033, 11, 1)
    CCS_CO2 = CCS_CO2.apply(lambda col: col if int(col.name) < CCS_date.year or int(col.name) < CCS_date.year + 12 else 0)

    # Stack DataFrames
    generation_df = stack_dataframes([wind_generation, solar_generation_postCA1CA2, solar_generation_CA1, 
                                  solar_generation_CA2, kossuth, hydrogen, CCS_CO2], print_warnings=False)
    
    # Replace all None values with 0 to ensure we can do multiplications later on
    generation_df = generation_df.replace({None: 0})
    
    return generation_df


def calculate_old_tax_policy_PTC_generated(PTC_df, generation_df, financial_inputs_tables, use_IRA, financial_scalars_inputs):
    """
    Calculate PTC generated under the old tax policy.

    Parameters:
    - PTC_df: DataFrame containing PTC-related information.
    - generation_df: DataFrame containing generation information.
    - financial_inputs_tables: Dictionary containing financial inputs tables.
    - use_IRA: Boolean indicating whether to use IRA.
    - financial_scalars_inputs: DataFrame containing financial scalar inputs.

    Returns:
    - DataFrame containing old tax policy PTC generated.
    """

    ### Qualifying New Wind
    ptc_price_series = PTC_df.loc['PTC Price'] 
    qualifying_new_wind_series = generation_df.loc['Qualifying New Wind']
    # Align series so we multiply matching years
    ptc_price_series, qualifying_new_wind_series = ptc_price_series.align(qualifying_new_wind_series, fill_value=0)
    qualifying_new_wind_old_ptc = qualifying_new_wind_series * ptc_price_series
    qualifying_new_wind_old_ptc = qualifying_new_wind_old_ptc.to_frame().T
    qualifying_new_wind_old_ptc = qualifying_new_wind_old_ptc.rename(index={0: 'Qualifying New Wind'})
    if use_IRA == True:
        qualifying_new_wind_old_ptc.loc['Qualifying New Wind'] = 0

    ### Captured CO2
    tax_credit_45Q_series = PTC_df.loc['45Q Tax Credit'] 
    gas_ccgt_series = generation_df.loc['Gas CCGT with CCS']
    # Align series so we multiply matching years
    tax_credit_45Q_series, gas_ccgt_series = tax_credit_45Q_series.align(gas_ccgt_series, fill_value=0)
    captured_co2_old_ptc = tax_credit_45Q_series * gas_ccgt_series
    captured_co2_old_ptc = captured_co2_old_ptc.to_frame().T
    captured_co2_old_ptc = captured_co2_old_ptc.rename(index={0: 'Captured CO2'})

    ### Kossuth
    WPL_Owned_Wind = financial_inputs_tables['WPL Owned Wind'].set_index('WPL Owned Wind')
    kossuth_date = date(2020, 10, 1)
    kossuth_old_ptc = captured_co2_old_ptc.copy()
    kossuth_old_ptc = kossuth_old_ptc.rename(index={'Captured CO2': 'Kossuth'})
    kossuth_old_ptc.loc['Kossuth'] = 0
    ptc_eligibility = WPL_Owned_Wind.loc[['Kossuth']]['PTC Eligibility'].values[0]

    for year in kossuth_old_ptc.columns:
        if year > kossuth_date.year + 10:
            kossuth_old_ptc.loc['Kossuth', year] = 0
        elif year == kossuth_date.year + 10:
            kossuth_generation_val = generation_df.loc[['Kossuth']].get(year, pd.Series([0])).values[0]
            kossuth_old_ptc_val = PTC_df.loc[['PTC Price Kossuth'], year].fillna(0).values[0]
            kossuth_old_ptc.loc['Kossuth', year] = kossuth_old_ptc_val * ptc_eligibility * kossuth_generation_val * ((kossuth_date.month - 1) / 12)
        else:
            kossuth_generation_val = generation_df.loc[['Kossuth']].get(year, pd.Series([0])).values[0]
            kossuth_old_ptc_val = PTC_df.loc[['PTC Price Kossuth'], year].fillna(0).values[0]
            kossuth_old_ptc.loc['Kossuth', year] = kossuth_old_ptc_val * ptc_eligibility * kossuth_generation_val

    ### Grossed Up PTC
    old_tax_policy_PTC_generated = stack_dataframes([kossuth_old_ptc, qualifying_new_wind_old_ptc, captured_co2_old_ptc], print_warnings=False)
    old_tax_policy_PTC_generated.loc['Grossed Up PTC'] = old_tax_policy_PTC_generated.sum()
    # Divide the "Grossed Up PTC" row by (1 - Income Tax Rate)
    old_tax_policy_PTC_generated.loc['Grossed Up PTC'] = old_tax_policy_PTC_generated.loc['Grossed Up PTC'] / (1 - financial_scalars_inputs.loc['Income Tax Rate'].values[0])
    
    return old_tax_policy_PTC_generated


def calculate_ira_ptc(generation_df, PTC_df, financial_scalars_inputs, use_IRA):
    """
    Calculate IRA PTC based on provided generation and PTC data.

    Parameters:
    - generation_df: DataFrame containing generation information.
    - PTC_df: DataFrame containing PTC-related information.
    - financial_scalars_inputs: DataFrame containing financial scalar inputs.

    Returns:
    - DataFrame containing IRA PTC calculations.
    """

    # Copy generation_df and initialize IRA_PTC_df with zeros
    IRA_PTC_df = generation_df.copy().drop(['Kossuth', 'Gas CCGT with CCS'])
    IRA_PTC_df.loc[:, :] = 0

    # Check if IRA is being used
    if use_IRA == True:
        
        # Qualifying New Wind
        ptc_price_series = PTC_df.loc['PTC Price'] 
        qualifying_new_wind_series = generation_df.loc['Qualifying New Wind']
        # Align series so we multiply matching years
        ptc_price_series, qualifying_new_wind_series = ptc_price_series.align(qualifying_new_wind_series, fill_value=0)
        IRA_PTC_df.loc['Qualifying New Wind'] = ptc_price_series * qualifying_new_wind_series
        
        # Hydrogen
        h2_ptc_price_series = PTC_df.loc['H2 PTC']
        hydrogen_series = generation_df.loc['Hydrogen']
        # Align series so we multiply matching years
        h2_ptc_price_series, hydrogen_series = h2_ptc_price_series.align(hydrogen_series, fill_value=0)
        IRA_PTC_df.loc['Hydrogen'] = h2_ptc_price_series * hydrogen_series

        # Check if long-term solar projects use PTC
        if financial_scalars_inputs.loc['Long-term solar projects ITCs or PTCs?'].values[0] == 'PTC':
            
            # CA1 Solar
            CA1_series = generation_df.loc['CA1 Solar']
            ptc_price_series, CA1_series = ptc_price_series.align(CA1_series, fill_value=0)
            IRA_PTC_df.loc['CA1 Solar'] = ptc_price_series * CA1_series
            
            # CA2 Solar
            CA2_series = generation_df.loc['CA2 Solar']
            ptc_price_series, CA2_series = ptc_price_series.align(CA2_series, fill_value=0)
            IRA_PTC_df.loc['CA2 Solar'] = ptc_price_series * CA2_series
            
            # Qualifying New Solar (Post-CA1/CA2)
            qualifying_new_solar_series = generation_df.loc['Qualifying New Solar (Post-CA1/CA2)']
            ptc_price_series, qualifying_new_solar_series = ptc_price_series.align(qualifying_new_solar_series, fill_value=0)
            IRA_PTC_df.loc['Qualifying New Solar (Post-CA1/CA2)'] = ptc_price_series * qualifying_new_solar_series

    # Grossed Up PTC
    IRA_PTC_df.loc['Grossed Up PTC'] = IRA_PTC_df.sum()
    # Divide the "Grossed Up PTC" row by (1 - Income Tax Rate)
    IRA_PTC_df.loc['Grossed Up PTC'] = IRA_PTC_df.loc['Grossed Up PTC'] / (1 - financial_scalars_inputs.loc['Income Tax Rate'].values[0])
    
    return IRA_PTC_df


def calculate_ITC(NOL, financial_inputs_tables, financial_scalars_inputs, ptcs_and_itcs_tables, run_variables_dict):
    """
    Calculate ITC (Investment Tax Credit) and related metrics.

    Parameters:
    - NOL: DataFrame containing information about Net Operating Loss.
    - financial_inputs_tables: Dictionary containing financial inputs tables.
    - financial_scalars_inputs: DataFrame containing financial scalar inputs.
    - ptcs_and_itcs_tables: DataFrame containing PTCS (Production Tax Credit and Investment Tax Credit) and ITCS (Investment Tax Credit) information.
    - run_variables_dict: Dictionary containing run details
    
    Returns:
    - DataFrame containing calculated ITC metrics.
    """

    # Extract ITC percentages and initialize ITC DataFrame
    ITC = financial_inputs_tables['ITC %'].set_index('Year').T
    ITC.loc['ITC Generated'] = 0
    ITC.loc['Accumulated Deferred ITC'] = 0

    # Update Accumulated Deferred ITC for years with projected NOL
    for year in ITC.columns:
        if year in NOL.columns and NOL.loc['Alliant Projected NOL?', year] == 'Yes':
            ITC.loc['Accumulated Deferred ITC', year] = ITC.loc['ITC Generated', year]

    # Copy Accumulated Deferred ITC to Deferred ITC Asset
    ITC.loc['Deferred ITC Asset'] = ITC.loc['Accumulated Deferred ITC']
    ITC.loc['Monetized ITC'] = 0

    # Update Monetized ITC for years without projected NOL
    for year in ITC.columns:
        if year in NOL.columns and NOL.loc['Alliant Projected NOL?', year] == 'No':
            ITC.loc['Monetized ITC', year] = ITC.loc['ITC Generated', year]

    # Normalized ITC calculations
    depreciation_years = int(financial_inputs_tables['Tax Credit Normalization']['Normalization Period (Years)'])
    capex_stream = ITC.loc['ITC Generated'].to_frame().T

    # Check if there is capex to depreciate
    if capex_stream.sum().sum() == 0:
        ITC.loc['Normalized ITC'] = 0
    else:
        # Create book depreciation schedule and drop unnecessary columns
        normalized_ITC_depreciation = create_book_depreciation_schedule(capex_stream, int(depreciation_years))
        normalized_ITC_depreciation = normalized_ITC_depreciation.drop(columns='Annual CapEx')
        ITC.loc['Normalized ITC'] = normalized_ITC_depreciation.loc[['Annual Book Depreciation']]

    # Calculate Grossed Up ITC
    ITC.loc['Grossed Up ITC'] = ITC.loc['Normalized ITC'] / (1 - financial_scalars_inputs.loc['Income Tax Rate'].values[0])

    # Calculate Accumulated ITC and Accumulated Normalized ITC
    ITC.loc['Accumulated ITC'] = ITC.loc['ITC Generated'].cumsum()
    ITC.loc['Accumulated Normalized ITC'] = ITC.loc['Normalized ITC'].cumsum()

    # Calculate Deferred Tax Liability - Normalization
    ITC.loc['Deferred Tax Liability - Normalization'] = ITC.loc['Accumulated ITC'] - ITC.loc['Accumulated Normalized ITC']

    # Calculate Net ITC Deferred Tax Liability
    ITC.loc['Net ITC Deferred Tax Liability'] = ITC.loc['Deferred Tax Liability - Normalization'] - ITC.loc['Deferred ITC Asset']

    # Calculate Change in Net Deferred Tax - ITC
    ITC.loc['Change in Net Deferred Tax - ITC'] = ITC.loc['Net ITC Deferred Tax Liability'].copy() - ITC.loc['Net ITC Deferred Tax Liability'].shift(fill_value=0)

    # Extract Storage ITC and update Total IRA ITC Benefit
    storage_ITC = ptcs_and_itcs_tables['Storage ITC']
    storage_ITC = storage_ITC[storage_ITC.Portfolio == run_variables_dict['case_name']]
    storage_ITC = storage_ITC[storage_ITC.Iteration == run_variables_dict['iteration']]
    storage_ITC = storage_ITC.drop(columns=['Portfolio', 'Iteration'])      
    storage_ITC = storage_ITC.set_index('Year')
    ITC.loc['Total IRA ITC Benefit'] = 0

    # Update Total IRA ITC Benefit for years with Storage ITC information
    for year in storage_ITC.columns:
        if year in ITC.columns:
            ITC.loc['Total IRA ITC Benefit', year] = storage_ITC.loc['TOTAL ITC', year]

    # Calculate Total Grossed Up IRA ITC Benefit
    ITC.loc['Total Grossed Up IRA ITC Benefit'] = ITC.loc['Total IRA ITC Benefit'] / (1 - financial_scalars_inputs.loc['Income Tax Rate'].values[0])

    return ITC