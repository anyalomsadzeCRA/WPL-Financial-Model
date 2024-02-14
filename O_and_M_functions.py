import pandas as pd
import numpy as np

from data_processing_functions import convert_capacity_table_to_cost_table


def calc_VOM(run_variables_dict, 
             aurora_portfolio_summary,
             capacity_payments,
             end_effects=False,
             solar_extension=False,
             inflation_rate=0.021):
    
    """
    Calculates Variable O&M costs.

    Parameters:
    - run_variables_dict (dictionary): Countains parameter information about which Aurora run to use.
    - aurora_portfolio_summary (pd.Dataframe): Aurora portflio output
    - capacity_payments (pd.Dataframe): Capacity payment information
    
    Returns:
    - pd.DataFrame: Dataframe containing VOM costs by year.
    """
    
    # Unpack run variables we need to index the data
    aurora_portfolio_ID = run_variables_dict['aurora_portfolio_ID']
    aurora_condition = run_variables_dict['aurora_condition']
    iteration = run_variables_dict['iteration']
    aurora_iteration = run_variables_dict['aurora_iteration']
    case_name = run_variables_dict['case_name']

    # Filter the data
    condition_mask = aurora_portfolio_summary['Condition'] == aurora_condition
    aurora_iteration_mask = aurora_portfolio_summary['Run_ID'] == aurora_iteration
    portfolio_id_mask = aurora_portfolio_summary['Portfolio_ID'] == aurora_portfolio_ID
    aurora_portfolio_summary_filtered = aurora_portfolio_summary[condition_mask & aurora_iteration_mask & portfolio_id_mask]

    capacity_payments_filtered = capacity_payments[(capacity_payments.Scenarios == iteration) & 
                                                   (capacity_payments['Case Name'] == case_name)]

    aurora_years = np.sort(aurora_portfolio_summary.Time_Period.unique())
        
    # Create a dictionary to store yearly data
    yearly_data = {
        'Total Owned Cost': [],
        'Market Purchases (Energy)': [],
        'Market Sales (Energy)': [],
        'Contract Cost': [],
        'Contract Sales': [],
        'High Load Capacity Payment': []
    }

    for year in aurora_years:
        # select row for current year
        curr_year_data = aurora_portfolio_summary_filtered.loc[(aurora_portfolio_summary_filtered['Time_Period'] == year)]
        curr_year_capacity_payments = capacity_payments_filtered[year]
        
        # extract data and apply multiplier
        yearly_data['Total Owned Cost'].append(curr_year_data["Resource_Cost_Total"].sum() * 1000)
        yearly_data['Market Purchases (Energy)'].append(curr_year_data['Market_Purchases_Cost_Total'].sum() * 1000)
        yearly_data['Market Sales (Energy)'].append(curr_year_data['Market_Sales_Cost_Total'].sum() * 1000)
        yearly_data['Contract Cost'].append(curr_year_data['Contract_Purchases_Cost_Total'].sum() * 1000)
        yearly_data['Contract Sales'].append(curr_year_data['Contract_Sales_Cost_Total'].sum() * 1000)
        yearly_data['High Load Capacity Payment'].append(curr_year_capacity_payments.sum())

     # Net market purchases = Purchases + Sales
    yearly_data['Net Market Purchases'] = [sum(costs) for costs in zip(yearly_data['Market Purchases (Energy)'], yearly_data['Market Sales (Energy)'])]
   
    years = list(aurora_years)
    
    # Account for extension periods
    end_year = run_variables_dict['rev_req_end_year']
    if end_effects:
        end_year = run_variables_dict['end_effects_end_year']
    if solar_extension:
        end_year = run_variables_dict['solar_extension_end_year']
    if end_effects or solar_extension:
        # add 0s for any years that don't exist between the end of our aurora data and the start of extension
        if run_variables_dict['rev_req_end_year'] - aurora_years[-1] > 0:
            for year in range(aurora_years[-1]+1, run_variables_dict['rev_req_end_year']+1):
                # Add the missing year and set values to 0
                for variable in yearly_data.keys():
                    yearly_data[variable].append(0)
                years.append(years[-1]+1)

        # add extension data
        variables_to_extend = ['Total Owned Cost', 'Contract Cost', 'Contract Sales', 'High Load Capacity Payment', 'Net Market Purchases']
        for year in range(run_variables_dict['rev_req_end_year']+1, end_year + 1):
            # Extend variables
            for variable in variables_to_extend:
                yearly_data[variable].append(yearly_data[variable][-1] * (1 + inflation_rate))
            for variable in ['Market Purchases (Energy)', 'Market Sales (Energy)']:
                yearly_data[variable].append(0)
            years.append(years[-1]+1)

    # Summarize the data into yearly lists
    yearly_data['Total Portfolio Cost'] = [sum(costs) for costs in zip(
        yearly_data['Total Owned Cost'], yearly_data['Net Market Purchases'],
        yearly_data['Contract Cost'], yearly_data['Contract Sales']
    )]

    # Create dataframe of our new data
    VOM_portfolio_cost_df = pd.DataFrame(yearly_data, index=years).T

    return(VOM_portfolio_cost_df)


def calc_FOM(run_variables_dict,
             scenario_financials_tables, 
             FOM_years, 
             financial_scalars_inputs,
             end_effects=True,
             solar_extension=True,
             inflation_rate=0.021):
    
    """
    Calculates Fixed O&M costs, not including individual new unit FOM.

    Parameters:
    - scenario_financials_tables (dictionary): Countains parameter information about which Aurora run to use.
    - FOM_years (array): Array for the years for which to calculate FOM.
    - financial_scalars_inputs (pd.Dataframe): Contains financial information.
    
    Returns:
    - pd.DataFrame: Dataframe containing FOM costs by year.
    """
    
    # Create an empty dictionary to store general, non-resource dependent FOM information
    FOM_yearly_general_dict = {}

    # Add the 'Year' key and assign the years we have for FOM as its value
    FOM_yearly_general_dict['Year'] = FOM_years

    # Preprocess data for calculations and extra data
    ongoing_capex_by_plant_df = scenario_financials_tables['Ongoing CapEx by Plant Summary']
    FOM_yearly = ongoing_capex_by_plant_df[ongoing_capex_by_plant_df['Category'] == 'FOM']
    FOM_yearly = FOM_yearly.loc[:, FOM_yearly.columns.isin(FOM_years)].values[0]
    Transmission_Upgrade_OpEx_yearly = ongoing_capex_by_plant_df[ongoing_capex_by_plant_df['Category'] == 'Transmission Upgrade OpEx']
    Transmission_Upgrade_OpEx_yearly = Transmission_Upgrade_OpEx_yearly.loc[:, Transmission_Upgrade_OpEx_yearly.columns.isin(FOM_years)].values[0]
    DSM_Costs_yearly = ongoing_capex_by_plant_df[ongoing_capex_by_plant_df['Category'] == 'DSM Costs']
    DSM_Costs_yearly = DSM_Costs_yearly.loc[:, DSM_Costs_yearly.columns.isin(FOM_years)].values[0]
    PTC_or_ITC = financial_scalars_inputs.loc['Long-term solar projects ITCs or PTCs?'].values[0]
    if PTC_or_ITC == "ITC":
        tax_equity_costs_df = scenario_financials_tables['Tax Equity Costs']
        tax_equity_costs_CA1_CA2_yearly = tax_equity_costs_df[tax_equity_costs_df.Category == 'Cash Distributions/OpEx for TE - CA1 & CA2']
        tax_equity_costs_CA1_CA2_yearly = tax_equity_costs_CA1_CA2_yearly.loc[:, tax_equity_costs_CA1_CA2_yearly.columns.isin(FOM_years)].values[0]
        tax_equity_costs_longterm_solar_yearly = tax_equity_costs_df[tax_equity_costs_df.Category == 'Cash Distributions/OpEx for TE- Long-Term Solar']
        tax_equity_costs_longterm_solar_yearly = tax_equity_costs_longterm_solar_yearly.loc[:, tax_equity_costs_longterm_solar_yearly.columns.isin(FOM_years)].values[0]
    else:
        tax_equity_costs_CA1_CA2_yearly = [0] * len(FOM_years)
        tax_equity_costs_longterm_solar_yearly = [0] * len(FOM_years)

    # Save data into dictionary
    FOM_yearly_general_dict['FOM'] = FOM_yearly.tolist()
    FOM_yearly_general_dict['Transmission Upgrade OpEx'] = Transmission_Upgrade_OpEx_yearly.tolist()
    FOM_yearly_general_dict['DSM Costs'] = DSM_Costs_yearly.tolist()
    FOM_yearly_general_dict['Tax Equity Costs - CA1 & CA2'] = tax_equity_costs_CA1_CA2_yearly
    FOM_yearly_general_dict['Tax Equity Costs - Long-Term Solar'] = tax_equity_costs_longterm_solar_yearly

    # Account for extension periods
    end_year = FOM_years[-1]
    if end_effects:
        end_year = run_variables_dict['end_effects_end_year']
    if solar_extension:
        end_year = run_variables_dict['solar_extension_end_year']
    if end_effects or solar_extension:
        variables_to_extend = list(FOM_yearly_general_dict.keys())
        variables_to_extend.remove('Year')
        for year in range(run_variables_dict['rev_req_end_year']+1, end_year + 1):
            # Extend variables
            for variable in variables_to_extend:
                FOM_yearly_general_dict[variable].append(FOM_yearly_general_dict[variable][-1] * (1 + inflation_rate))
     
    years = list(FOM_years) + list(range(run_variables_dict['rev_req_end_year']+1, end_year+1))
    FOM_yearly_general_dict['Year'] = years
    
    # Create a DataFrame from the dictionary
    FOM_yearly_general_df = pd.DataFrame(FOM_yearly_general_dict)

    # Set 'Year' as the index and transpose the DataFrame
    FOM_yearly_general_df.set_index('Year', inplace=True)
    FOM_yearly_general_df = FOM_yearly_general_df.T
    
    return(FOM_yearly_general_df)


def calc_new_resource_FOM(run_variables_dict,
                          FOM_years,
                          cumulative_installed_capacity_MW_df, 
                          FOM_2021_kw_year_df, 
                          inflation_vector,
                          CCS_inputs_tables,
                          hydrogen_island_inputs,
                          end_effects=True,
                          solar_extension=True,
                          inflation_rate=0.021):

    """
    Calculates Fixed O&M costs for individual new resource units by resource type.

    Parameters:
    - run_variables_dict (dictionary): Contains parameter information about which Aurora run to use.
    - FOM_years (array): Array for the years for which to calculate FOM.
    - cumulative_installed_capacity_MW_df (pd.Dataframe): Contains capacity buildout for new resources.
    - FOM_2021_kw_year_df (pd.Dataframe): Contains FOM per kW info for different resource types.
    - inflation_vector (series): Contains inflation scalar for each year.
    - CCS_inputs_tables, hydrogen_island_inputs (pd.Dataframe): Contain input information for supporting calculations.

    Returns:
    - pd.DataFrame: Dataframe containing FOM costs by year.
    """
    
    # Unpack run variables we need to index the data
    aurora_portfolio_ID = run_variables_dict['aurora_portfolio_ID']
    iteration = run_variables_dict['iteration']
    aurora_iteration = run_variables_dict['aurora_iteration']
    og_end_year = run_variables_dict['rev_req_end_year'] 
    
    # Create an empty dictionary to store yearly FOM costs by resource
    FOM_yearly_by_resource_dict = {'Year': FOM_years}

    # Create yearly FOM Table (calculates as FOM * capacity * inflation)
    FOM_yearly_by_resource_df = convert_capacity_table_to_cost_table(cumulative_installed_capacity_MW_df,
                                                                    FOM_2021_kw_year_df, 
                                                                    inflation_vector,
                                                                    name_adjuster='FOM -')

    # Deal with outliers (which need to be calculated a little bit differently)
    FOM_yearly_by_resource_df = handle_outliers_for_new_resource_FOM(FOM_yearly_by_resource_df, 
                                                                     CCS_inputs_tables, 
                                                                     aurora_iteration, 
                                                                     cumulative_installed_capacity_MW_df,
                                                                     hydrogen_island_inputs,
                                                                     iteration)

    # Calculate the total O&M and add it as a new row in the DataFrame
    new_unit_FOM_yearly_sum = FOM_yearly_by_resource_df.sum(axis=0, skipna=True)
    FOM_yearly_by_resource_df = pd.concat([pd.DataFrame([new_unit_FOM_yearly_sum], index=['New Unit FOM']), FOM_yearly_by_resource_df])

    # Handle extension period
    def add_new_years(df, start_year, end_year, inflation_rate): 
        # Create a range of new years
        new_years = range(start_year, end_year + 1)
        # Create a new DataFrame with zeros
        new_data = pd.DataFrame(0, columns=new_years, index=df.index)
        # Update the "New Unit FOM" row with cumulative inflation rates
        last_value = df.loc['New Unit FOM'].iloc[-1]
        for year in new_years:
            last_value *= (1 + inflation_rate)
            new_data.at['New Unit FOM', year] = last_value
        # Concatenate the existing DataFrame with the new DataFrame
        result_df = pd.concat([df, new_data], axis=1)
        return result_df    
    
    if end_effects:
        end_year = run_variables_dict['end_effects_end_year']
    if solar_extension:
        end_year = run_variables_dict['solar_extension_end_year']

    if end_effects or solar_extension:
        FOM_yearly_by_resource_df = add_new_years(FOM_yearly_by_resource_df, og_end_year+1, end_year, inflation_rate)
        
    return FOM_yearly_by_resource_df


def handle_outliers_for_new_resource_FOM(FOM_yearly_by_resource_df, 
                                         CCS_inputs_tables, 
                                         aurora_iteration,
                                         cumulative_installed_capacity_MW_df,
                                         hydrogen_island_inputs,
                                         iteration):
    
    # Gas CCGT FOM is a bit more involved because we need to add in separate CSS FOM values. 
    # So, we calculate normal FOM and add CSS FOM values to it.
    # NOTE - CSS FOM starts a year before we actually have capacity. TBD on what to do here.
    # This is also currently incorrectly coded in the Excel model - CSS values offset by a year in the summation.

    # Load in CSS FOM data
    CCS_FOM_yearly = CCS_inputs_tables['$ FOM'][CCS_inputs_tables['$ FOM'].Aurora_Iteration == aurora_iteration].set_index('Aurora_Iteration').sum()
    # Take our current base FOM values for CSS
    Gas_CCGT_with_CCS_FOM_yearly = FOM_yearly_by_resource_df.loc['FOM - Gas CCGT with CCS']
    # Add the two together 
    Total_Gas_CCGT_with_CCS_FOM_yearly = pd.concat([Gas_CCGT_with_CCS_FOM_yearly, CCS_FOM_yearly], axis=1).sum(axis=1)
    # Update our dataframe, making sure we only add in the years that are included in the dataframe
    common_years = FOM_yearly_by_resource_df.columns.intersection(Total_Gas_CCGT_with_CCS_FOM_yearly.index)
    # Add only the common years from the Series to the DataFrame
    FOM_yearly_by_resource_df.loc['FOM - Gas CCGT with CCS'] = Total_Gas_CCGT_with_CCS_FOM_yearly[common_years]

    # Hydrogen Island is a bit more involved because we need to use a separate input that is nominal (so we don't use inflation vec)

    # Get hydrogen island capacity and convert MWs to KWs
    hydrogen_island_capacity_yearly = cumulative_installed_capacity_MW_df.loc['H2 Island'] * 1000
    # Load in hydrogen island assumptions
    hydrogen_island_FOM = hydrogen_island_inputs['FOM'].set_index('Year')
    # Select for current scenario
    hydrogen_island_FOM_yearly = hydrogen_island_FOM[iteration]
    # Concatenate hydrogen capacity and FOM by year and multiply columns to get yearly total FOM
    hydrogen_island_yearly_df = pd.concat([hydrogen_island_capacity_yearly, hydrogen_island_FOM_yearly], axis=1).sort_index()
    hydrogen_island_yearly_df.columns = ['Capacity','FOM']
    hydrogen_total_FOM_yearly =  hydrogen_island_yearly_df['Capacity'] * hydrogen_island_yearly_df['FOM']
    # Update our dataframe, making sure we only add in the years that are included in the dataframe
    common_years = FOM_yearly_by_resource_df.columns.intersection(hydrogen_total_FOM_yearly.index)
    # Add only the common years from the Series to the DataFrame
    FOM_yearly_by_resource_df.loc['FOM - H2 Island'] = hydrogen_total_FOM_yearly[common_years]

    return FOM_yearly_by_resource_df



def calc_new_resource_AS_RT(run_variables_dict,
                            FOM_years,
                            AS_RT_inputs,
                            cumulative_installed_capacity_MW_df,
                            end_effects=True,
                            solar_extension=True,
                            inflation_rate=0.021):
    
    """
    Calculates ancillary services costs for individual new resource units by resource type.

    Parameters:
    - FOM_years (array): Array for the years for which to calculate FOM.
    - cumulative_installed_capacity_MW_df (pd.Dataframe): Contains capacity buildout for new resources.
    - AS_RT_inputs (pd.DataFrame): Resource AS_RT rates table.
  
    Returns:
    - pd.DataFrame: Dataframe containing FOM costs by year.
    """
    
    # Create an empty dictionary to store yearly AS_RT costs by resource
    AS_RT_yearly_by_resource_dict = {}

    # Add the 'Year' key and assign the years we have for FOM as its value
    AS_RT_yearly_by_resource_dict['Year'] = FOM_years
    
    # Create yearly AS_RT Table (calculates as AS_RT $/kw * capacity * inflation)
    AS_RT_yearly_by_resource_df = convert_capacity_table_to_cost_table(cumulative_installed_capacity_MW_df,
                                            AS_RT_inputs, 
                                            name_adjuster = 'SH/AS Rev -')
    
    # Make all values negative since this is like income
    AS_RT_yearly_by_resource_df = - AS_RT_yearly_by_resource_df

    # Calculate the total O&M and add it as a new row in the DataFrame
    new_unit_AS_RT_yearly_sum = AS_RT_yearly_by_resource_df.sum(axis=0, skipna=True)
    AS_RT_yearly_by_resource_df = pd.concat([AS_RT_yearly_by_resource_df.iloc[:0], pd.DataFrame([new_unit_AS_RT_yearly_sum]), AS_RT_yearly_by_resource_df.iloc[0:]])
    AS_RT_yearly_by_resource_df.rename(index={AS_RT_yearly_by_resource_df.index[0]: 'New Unit Subhourly / Ancillary Revenue'}, inplace=True)
   
    # Handle extension period
    def add_new_years(df, start_year, end_year, inflation_rate): 
        # Create a range of new years
        new_years = range(start_year, end_year + 1)
        # Create a new DataFrame with zeros
        new_data = pd.DataFrame(0, columns=new_years, index=df.index)
        # Update the "New Unit FOM" row with cumulative inflation rates
        last_value = df.loc['New Unit Subhourly / Ancillary Revenue'].iloc[-1]
        for year in new_years:
            last_value *= (1 + inflation_rate)
            new_data.at['New Unit Subhourly / Ancillary Revenue', year] = last_value
        # Concatenate the existing DataFrame with the new DataFrame
        result_df = pd.concat([df, new_data], axis=1)
        return result_df    
    
    if end_effects:
        end_year = run_variables_dict['end_effects_end_year']
    if solar_extension:
        end_year = run_variables_dict['solar_extension_end_year']

    if end_effects or solar_extension:
        AS_RT_yearly_by_resource_df = add_new_years(AS_RT_yearly_by_resource_df, FOM_years[-1]+1, end_year, inflation_rate)
        
    return(AS_RT_yearly_by_resource_df)