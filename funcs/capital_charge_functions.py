import pandas as pd
import numpy as np
from datetime import date

def calculate_capital_charge(financial_scalars_inputs, 
                             rate_base_df,
                             end_effects=True, 
                             solar_extension=True,
                             inflation_rate=0.021):
   
    capital_charge_df = rate_base_df.loc[['Ending Rate Base']].copy()

    ## Extract values from financial_scalars_inputs
    starting_equity = financial_scalars_inputs.loc['Starting Equity ($)', 'Value']
    starting_debt = financial_scalars_inputs.loc['Starting Debt ($)', 'Value']
    equity_rate_base = financial_scalars_inputs.loc['Equity % Rate Base', 'Value']
    debt_rate_base = financial_scalars_inputs.loc['Debt % Rate Base', 'Value']
    existing_equity_cost = financial_scalars_inputs.loc['Return on Equity (Existing)', 'Value']
    existing_debt_cost = financial_scalars_inputs.loc['Cost of Debt (Existing)', 'Value']
    new_equity_cost = financial_scalars_inputs.loc['Return on Equity (New)', 'Value']
    new_debt_cost = financial_scalars_inputs.loc['Cost of Debt (New)', 'Value']

    ## Calculate intermediate values
    new_capex_cumsum = rate_base_df.loc['CapEx'].cumsum()
    new_equity = new_capex_cumsum * equity_rate_base
    new_debt = new_capex_cumsum * debt_rate_base

    return_on_WACC = (
        (starting_equity / (starting_equity + starting_debt + new_equity + new_debt) * existing_equity_cost)
        + (starting_debt / (starting_equity + starting_debt + new_equity + new_debt) * existing_debt_cost)
        + (new_equity / (starting_equity + starting_debt + new_equity + new_debt) * new_equity_cost)
        + (new_debt / (starting_equity + starting_debt + new_equity + new_debt) * new_debt_cost)
    )

    return_on_ratebase = []
    for year in capital_charge_df.columns:
        if year == financial_scalars_inputs.loc['Start Year', 'Value'] - 1:
            return_on_ratebase.append(capital_charge_df[year]['Ending Rate Base'] * return_on_WACC[year])
        else:
            return_on_ratebase.append(
                np.mean([capital_charge_df[year]['Ending Rate Base'], capital_charge_df[year-1]['Ending Rate Base']])
                * return_on_WACC[year]
            )
    return_on_ratebase = pd.Series(return_on_ratebase, index=capital_charge_df.columns)
    
    equity_percent_ratebase = ((starting_equity + new_equity) / (starting_equity + new_equity + starting_debt + new_debt))

    ROE = []
    for year in capital_charge_df.columns:
        if year == financial_scalars_inputs.loc['Start Year', 'Value'] - 1:
            ROE.append(capital_charge_df[year]['Ending Rate Base'])
        else:
            ROE.append(
                np.mean([capital_charge_df[year]['Ending Rate Base'], capital_charge_df[year-1]['Ending Rate Base']])
                * equity_percent_ratebase[year]
                * ((existing_equity_cost * starting_equity) / (starting_equity + new_equity[year])
                + (new_equity_cost * new_equity[year]) / (starting_equity + new_equity[year]))
            )
    ROE = pd.Series(ROE, index=capital_charge_df.columns)

    debt_check = []
    for year in capital_charge_df.columns:
        if year == financial_scalars_inputs.loc['Start Year', 'Value'] - 1:
            debt_check.append(capital_charge_df[year]['Ending Rate Base'])
        else:
            debt_check.append(
                np.mean([capital_charge_df[year]['Ending Rate Base'], capital_charge_df[year-1]['Ending Rate Base']])
                * (1 - equity_percent_ratebase[year])
                * ((existing_debt_cost * starting_debt) / (starting_debt + new_debt[year])
                + (new_debt_cost * new_debt[year]) / (starting_debt + new_debt[year]))
            )
    debt_check = pd.Series(debt_check, index=capital_charge_df.columns)
        
        
    ## Assign values to capital_charge_df
    capital_charge_df.loc['Starting Equity ($)'] = starting_equity
    capital_charge_df.loc['Starting Debt ($)'] = starting_debt
    capital_charge_df.loc['New CapEx ($)'] = new_capex_cumsum
    capital_charge_df.loc['New Equity ($)'] = new_equity
    capital_charge_df.loc['New Debt ($)'] = new_debt
    capital_charge_df.loc['Existing Equity Cost'] = "{:.2f}%".format((existing_equity_cost * 100))
    capital_charge_df.loc['Existing Debt Cost'] = "{:.2f}%".format((existing_debt_cost * 100))
    capital_charge_df.loc['New Equity Cost'] = "{:.2f}%".format((new_equity_cost * 100))
    capital_charge_df.loc['New Debt Cost'] = "{:.2f}%".format((new_debt_cost * 100))
    capital_charge_df.loc['Return on (WACC)'] = return_on_WACC.apply(lambda x: "{:.2%}".format(x))
    capital_charge_df.loc['Return on Ratebase'] = return_on_ratebase
    capital_charge_df.loc['Equity % Ratebase'] = equity_percent_ratebase.apply(lambda x: "{:.2%}".format(x))
    capital_charge_df.loc['ROE'] = ROE
    capital_charge_df.loc['Debt Check'] = debt_check
    
    # Handle weird change for capital charge that starts at 2055
    def add_new_years_for_capital_charge(df, start_year, end_year, inflation_rate, row_name): 
        last_value = df.loc[row_name][start_year-1]
        years = range(start_year, end_year+1)
        for year in years:
            last_value *= (1 + inflation_rate)
            df.at[row_name, year] = last_value
        return df    
    
    if end_effects or solar_extension:
        capital_charge_df = add_new_years_for_capital_charge(capital_charge_df, 
                                          2055, 
                                          capital_charge_df.columns[-1], 
                                          inflation_rate,
                                          'Return on Ratebase')
        capital_charge_df = add_new_years_for_capital_charge(capital_charge_df, 
                                          2055, 
                                          capital_charge_df.columns[-1], 
                                          inflation_rate,
                                          'ROE')
        capital_charge_df = add_new_years_for_capital_charge(capital_charge_df, 
                                          2055, 
                                          capital_charge_df.columns[-1], 
                                          inflation_rate,
                                          'Debt Check')
    return capital_charge_df
