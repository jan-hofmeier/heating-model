import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import os
from heating_model.src.config import Cols

def save_plots(df: pd.DataFrame, output_dir='heating_model/output'):
    """
    Generates and saves the required plots.
    1. Energy vs Outside Temp (Total + per circuit).
    2. Flow Temp vs Outside Temp (Steady State).
    """
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    # --- 1. Aggregation for Energy Charts ---
    # We need Total Energy per Day (or Hour) vs Average Outside Temp for that period.

    # Resample to Daily
    daily = df.resample('D').agg({
        Cols.OUTSIDE_TEMP: 'mean',
        'power_dhw_kw': 'sum', # Power(kW) * samples -> Energy (kJ) if we multiply by dt
        'power_rad_kw': 'sum',
        'power_underfloor_kw': 'sum',
        'power_generated_kw': 'sum'
    })

    # Convert Sum of Instant Power to Energy (kWh)
    # Each sample is 10s. Power is kW (kJ/s).
    # Energy (kJ) = Power * 10.
    # Energy (kWh) = Energy (kJ) / 3600.

    samples_per_day = 24 * 60 * 6 # 10s freq
    # Actually, resample('D').sum() just adds the values.
    # We need to know the freq.
    # Better: Resample using mean power (kW) then multiply by 24h.

    daily_mean_kw = df.resample('D').mean()

    daily_energy_kwh = pd.DataFrame()
    daily_energy_kwh['Outside Temp'] = daily_mean_kw[Cols.OUTSIDE_TEMP]
    daily_energy_kwh['DHW'] = daily_mean_kw['power_dhw_kw'] * 24
    daily_energy_kwh['Radiator'] = daily_mean_kw['power_rad_kw'] * 24
    daily_energy_kwh['Underfloor'] = daily_mean_kw['power_underfloor_kw'] * 24
    daily_energy_kwh['Total'] = daily_mean_kw['power_generated_kw'] * 24

    # Save Data
    daily_energy_kwh.to_csv(os.path.join(output_dir, 'daily_energy.csv'))

    # Plot 1: Energy vs Outside Temp
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=daily_energy_kwh, x='Outside Temp', y='Total', label='Total')
    sns.scatterplot(data=daily_energy_kwh, x='Outside Temp', y='DHW', label='DHW')
    sns.scatterplot(data=daily_energy_kwh, x='Outside Temp', y='Radiator', label='Radiator')
    sns.scatterplot(data=daily_energy_kwh, x='Outside Temp', y='Underfloor', label='Underfloor')

    plt.title("Daily Energy Consumption vs Outside Temperature")
    plt.xlabel("Outside Temperature (°C)")
    plt.ylabel("Energy (kWh)")
    plt.legend()
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'energy_vs_temp_daily.png'))
    plt.close()

    # Hourly Aggregation
    hourly_mean_kw = df.resample('h').mean()
    hourly_energy_kwh = pd.DataFrame()
    hourly_energy_kwh['Outside Temp'] = hourly_mean_kw[Cols.OUTSIDE_TEMP]
    hourly_energy_kwh['Total'] = hourly_mean_kw['power_generated_kw'] # avg kW * 1h = kWh

    # Plot 2: Hourly Energy
    plt.figure(figsize=(10, 6))
    sns.scatterplot(data=hourly_energy_kwh, x='Outside Temp', y='Total', alpha=0.5)
    plt.title("Hourly Energy Consumption vs Outside Temperature")
    plt.xlabel("Outside Temperature (°C)")
    plt.ylabel("Energy (kWh)")
    plt.grid(True)
    plt.savefig(os.path.join(output_dir, 'energy_vs_temp_hourly.png'))
    plt.close()

    # --- 2. Steady State Flow Temp ---
    # Filter steady state
    steady = df[df['is_steady_state'] == True]

    if not steady.empty:
        # We want points: Outside Temp vs Flow Temp
        # Downsample to avoid millions of dots (e.g. 1 min avg)
        steady_1min = steady.resample('1min').mean().dropna()

        # Save Data
        steady_1min[[Cols.OUTSIDE_TEMP, Cols.BOILER_FLOW_TEMP]].to_csv(os.path.join(output_dir, 'steady_state_flow.csv'))

        plt.figure(figsize=(10, 6))
        sns.scatterplot(data=steady_1min, x=Cols.OUTSIDE_TEMP, y=Cols.BOILER_FLOW_TEMP, alpha=0.3)
        plt.title("Steady State Flow Temperature vs Outside Temperature")
        plt.xlabel("Outside Temperature (°C)")
        plt.ylabel("Flow Temperature (°C)")
        plt.grid(True)
        plt.savefig(os.path.join(output_dir, 'steady_state_flow_curve.png'))
        plt.close()
    else:
        print("No steady state periods detected.")
