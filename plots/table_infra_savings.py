# SPDX-FileCopyrightText:  Open Energy Transition gGmbH
#
# SPDX-License-Identifier: AGPL-3.0-or-later

import os
import sys
sys.path.append("../submodules/pypsa-eur")
import pypsa
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import warnings
warnings.filterwarnings("ignore")
from _helpers import mock_snakemake, update_config_from_wildcards, load_network, \
                     change_path_to_pypsa_eur, change_path_to_base, \
                     LINE_LIMITS, CO2L_LIMITS, BAU_HORIZON, LAND_FOR_WIND, LAND_FOR_SOLAR
                     
from plot_total_costs import compute_costs


if __name__ == "__main__":
    if "snakemake" not in globals():
        snakemake = mock_snakemake(
            "get_infra_savings", 
            clusters="48",
        )
    # update config based on wildcards
    config = update_config_from_wildcards(snakemake.config, snakemake.wildcards)


    # move to submodules/pypsa-eur
    change_path_to_pypsa_eur()
    # network parameters
    co2l_limits = CO2L_LIMITS
    line_limits = LINE_LIMITS
    clusters = config["plotting"]["clusters"]
    planning_horizons = config["plotting"]["planning_horizon"]
    planning_horizons = [str(x) for x in planning_horizons if not str(x) == BAU_HORIZON]
    opts = config["plotting"]["sector_opts"]

    # define scenario namings
    scenarios = {"flexible": "Widespread Renovation",
                 "retro_tes": "Widespread Renovation and Electrification",
                 "flexible-moderate": "Limited Renovation",
                 "rigid": "Business as Usual and Electrification"
                 }

    # define dataframe to store infra savings
    cost_savings = pd.DataFrame(
        index=list(scenarios.values()),
        columns=[
            ("2030", "wind"), ("2030", "solar"), ("2030", "gas"),
            ("2040", "wind"), ("2040", "solar"), ("2040", "gas"),
            ("2050", "wind"), ("2050", "solar"), ("2050", "gas")
        ]
    )
    df_savings = pd.DataFrame(
        index=list(scenarios.values()),
        columns=[
            ("2030", "wind"), ("2030", "solar"), ("2030", "gas"),
            ("2040", "wind"), ("2040", "solar"), ("2040", "gas"),
            ("2050", "wind"), ("2050", "solar"), ("2050", "gas")
        ]
    )
    land_usage = df_savings.copy()
    df_savings.columns = pd.MultiIndex.from_tuples(df_savings.columns, names=['horizon','Installed capacity [GW]'])
    cost_savings.columns = pd.MultiIndex.from_tuples(cost_savings.columns, names=['horizon','Capital cost [BEur]'])
    land_usage.columns = pd.MultiIndex.from_tuples(land_usage.columns, names=['horizon','Land usage [km2]'])

    for planning_horizon in planning_horizons:
        lineex = line_limits[planning_horizon]
        sector_opts = f"Co2L{co2l_limits[planning_horizon]}-{opts}"

        # benchmark network
        b = load_network(lineex, clusters, sector_opts, planning_horizon, "rigid")
        b_costs = compute_costs(b, "rigid", "Capital")
        for scenario, nice_name in scenarios.items():
            # load networks
            n = load_network(lineex, clusters, sector_opts, planning_horizon, scenario)

            if n is None:
                # Skip further computation for this scenario if network is not loaded
                print(f"Network is not found for scenario '{scenario}', planning year '{planning_horizon}'. Skipping...")
                continue

            # estimate upper and lower limits of congestion of grid
            solar_carriers = ["solar", "solar rooftop"]
            solar = n.generators.query("carrier in @solar_carriers").p_nom_opt.sum() / 1e3
            wind_carriers = ["onwind", "offwind-ac", "offwind-dc"]
            wind = n.generators.query("carrier in @wind_carriers").p_nom_opt.sum() / 1e3
            CCGT_carriers = ["CCGT"]
            gas = n.links.query("carrier in @CCGT_carriers").p_nom_opt.multiply(n.links.efficiency).sum() / 1e3

            df_savings.loc[nice_name, (planning_horizon, "solar")] = solar.round(2)
            df_savings.loc[nice_name, (planning_horizon, "wind")] = wind.round(2)
            df_savings.loc[nice_name, (planning_horizon, "gas")] = gas.round(2)

            cap_costs = compute_costs(n, nice_name, "Capital")
            wind_costs_carriers = ["Generator:Offshore Wind (AC)", "Generator:Offshore Wind (DC)", "Generator:Onshore Wind"]
            cost_savings.loc[nice_name, (planning_horizon, "wind")] = (cap_costs.loc[wind_costs_carriers].sum()[0] / 1e9).round(2)
            solar_costs_carriers = ["Generator:Solar", "Generator:solar rooftop"]
            cost_savings.loc[nice_name, (planning_horizon, "solar")] = (cap_costs.loc[solar_costs_carriers].sum()[0] / 1e9).round(2)
            gas_costs_carriers = ["Store:gas", "Link:Open-Cycle Gas"]
            cost_savings.loc[nice_name, (planning_horizon, "gas")] = (cap_costs.loc[gas_costs_carriers].sum()[0] / 1e9).round(2)

            # land usage in thousand km^2
            land_usage.loc[nice_name, (planning_horizon, "solar")] = (solar * LAND_FOR_SOLAR).round(2)
            land_usage.loc[nice_name, (planning_horizon, "wind")] = (wind * LAND_FOR_WIND).round(2)

    # add name for columns
    df_savings.index.name = "Scenario [GW]"

    # move to base directory
    change_path_to_base()

    # save the heat pumps data in Excel format
    df_savings.index = ["Limited Renovation/Limited Renovation & Electrification" if s == "Limited Renovation" else s for s in df_savings.index]
    df_savings.to_csv(snakemake.output.table_cap)
    cost_savings.index = ["Limited Renovation/Limited Renovation & Electrification" if s == "Limited Renovation" else s for s in cost_savings.index]
    cost_savings.to_csv(snakemake.output.table_costs)
    land_usage.index = ["Limited Renovation/Limited Renovation & Electrification" if s == "Limited Renovation" else s for s in land_usage.index]
    land_usage.to_csv(snakemake.output.table_land)

