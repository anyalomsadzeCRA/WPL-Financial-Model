import pandas as pd
import numpy as np


def get_resource_FOM(name_of_resource, cumulative_installed_capacity_MW_df, FOM_2021_kw_year_df, inflation_vector):
    """
    Calculates the yearly total FOM for a given resource.

    Parameters:
    - name_of_resource (string): Name of the resource to be studied.
    - cumulative_installed_capacity_MW_df (pd.DataFrame): Resource capacity table.
    - FOM_2021_kw_year_df (pd.DataFrame): Resource FOM rates table.
    - inflation_vector (pd.Series): Inflaction vector relative to 2021.

    Returns:
    - pd.DataFrame: Dataframe containing a row for the year and row for the FOM of that year.
    """
    
    # Retrieve resource capacity and FOM
    resource_capacity_yearly = cumulative_installed_capacity_MW_df[name_of_resource]
    resource_capacity_yearly = resource_capacity_yearly * 1000 # convert MWs to KWs
    resource_FOM_yearly = FOM_2021_kw_year_df[name_of_resource]
    
    # Merge DataFrames on the 'Year' column
    resource_yearly_df = pd.merge(resource_capacity_yearly, resource_FOM_yearly, on='Year')
    resource_yearly_df = pd.merge(resource_yearly_df, inflation_vector, on='Year')
    resource_yearly_df.columns = ['Capacity','FOM', 'Inflation Scalar']
    
    # Multiply corresponding values for total FOM
    resource_yearly_df['Total FOM'] =  resource_yearly_df['Capacity'] * resource_yearly_df['FOM'] * resource_yearly_df['Inflation Scalar']
    resource_total_FOM_yearly = resource_yearly_df['Total FOM'] 
    resource_total_FOM_yearly = resource_total_FOM_yearly.to_frame().T

    return(resource_total_FOM_yearly)

def get_resource_AS_RT(name_of_resource, cumulative_installed_capacity_MW_df, AS_RT_inputs):
    """
    Calculates the yearly total Ancillary Revenue for a given resource.

    Parameters:
    - name_of_resource (string): Name of the resource to be studied.
    - cumulative_installed_capacity_MW_df (pd.DataFrame): Resource capacity table.
    - AS_RT_inputs (pd.DataFrame): Resource AS_RT rates table.

    Returns:
    - pd.DataFrame: Dataframe containing a row for the year and row for the Ancillary Revenue of that year.
    """
    
    # Retrieve resource capacity and AS / RT rates
    resource_capacity_yearly = cumulative_installed_capacity_MW_df[name_of_resource]
    resource_capacity_yearly = resource_capacity_yearly * 1000 # convert MWs to KWs
    resource_AS_RT_yearly = AS_RT_inputs[name_of_resource]
    
    # Merge DataFrames on the 'Year' column
    resource_yearly_df = pd.merge(resource_capacity_yearly, resource_AS_RT_yearly, on='Year')
    resource_yearly_df.columns = ['Capacity','AS_RT']
    
    # Multiply corresponding values for AS_RT total revenue & make it negative
    resource_yearly_df['Total AS_RT'] = - resource_yearly_df['Capacity'] * resource_yearly_df['AS_RT']
    resource_total_AS_RT_yearly = resource_yearly_df['Total AS_RT']
    resource_total_AS_RT_yearly = resource_total_AS_RT_yearly.to_frame().T

    return(resource_total_AS_RT_yearly)