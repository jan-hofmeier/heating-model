import pandas as pd
import numpy as np
from src.config import (
    Cols, C_WATER_J_KG_K, RHO_WATER_KG_M3,
    BOILER_VOLUME_L, BOILER_MASS_KG
)

def calculate_circuit_power_kw(flow_rate_l_h, temp_in, temp_out):
    """
    Calculates instantaneous power in kW.
    P = m_dot * Cp * dT
    """
    # Flow L/h -> m3/s
    # 1 L = 0.001 m3
    # 1 h = 3600 s
    flow_m3_s = (flow_rate_l_h / 1000.0) / 3600.0

    # Mass flow kg/s
    m_dot_kg_s = flow_m3_s * RHO_WATER_KG_M3

    # Delta T
    dt = temp_in - temp_out

    # Power J/s (Watts)
    power_w = m_dot_kg_s * C_WATER_J_KG_K * dt

    # kW
    return power_w / 1000.0

def estimate_burner_power(df: pd.DataFrame) -> float:
    """
    Derives the Burner Power (kW) by looking at Summer Mode (DHW only).
    Strategy:
    1. Identify continuous 'Summer' periods (e.g. whole days where Radiator Flow is ~0).
    2. Sum the Total Energy Output (DHW) over this whole period.
    3. Sum the Total Burner Run Time over this whole period.
    4. Account for Net Change in Boiler Internal Energy (Start vs End of period).
    5. Burner Power = (Total Output + Delta Storage) / Total Run Time.
    """
    # Filter for Summer Mode days
    # We'll resample to Daily to find days with 0 Radiator Flow
    daily_rad_flow = df[Cols.RADIATOR_FLOW_RATE].resample('D').max()
    summer_days = daily_rad_flow[daily_rad_flow < 1.0].index

    if len(summer_days) == 0:
        # Fallback to finding ANY period where radiator is off
        mask = df[Cols.RADIATOR_FLOW_RATE] < 1.0
        # If we just take the whole dataframe if it's all summer?
        if mask.all():
            subset = df
        else:
            # Just take the first large block?
            # Let's stick to the original plan: find valid summer blocks.
            return 20.0 # Fallback
    else:
        # Filter DF to only include these days
        # We need the full resolution data for these days
        # Construct a boolean mask matching the days
        mask = pd.Series(False, index=df.index)
        for day in summer_days:
            day_str = str(day.date())
            mask.loc[day_str] = True
        subset = df[mask]

    if subset.empty:
        return 20.0

    # 1. Total Run Time (s)
    # Each row is a sample. If Burner Status is True, we add dt.
    dt_seconds = subset.index.to_series().diff().dt.total_seconds().fillna(10.0)

    # We need to align dt with the status.
    total_run_time_s = (subset[Cols.BURNER_STATUS] * dt_seconds).sum()

    if total_run_time_s < 60:
        return 20.0

    # 2. Total Energy Output (kJ)
    # DHW Power (kW) at each step * dt
    p_dhw_kw = calculate_circuit_power_kw(
        subset[Cols.DHW_PUMP_FLOW_RATE],
        subset[Cols.DHW_FLOW_TEMP_TO_TANK],
        subset[Cols.DHW_RETURN_TEMP_COMBINED]
    )
    total_energy_dhw_kj = (p_dhw_kw * dt_seconds).sum()

    # 3. Delta Storage (kJ)
    # Start vs End of the entire period
    t_start = subset[Cols.BOILER_FLOW_TEMP].iloc[0]
    t_end = subset[Cols.BOILER_FLOW_TEMP].iloc[-1]
    delta_storage_kj = BOILER_MASS_KG * (C_WATER_J_KG_K/1000.0) * (t_end - t_start)

    # 4. Burner Power
    # Total Energy Input = Burner Power * Run Time
    # Total Energy Input = Total Energy Output + Delta Storage
    # (Assuming losses are negligible or part of the "Load")

    burner_power_kw = (total_energy_dhw_kj + delta_storage_kj) / total_run_time_s

    return burner_power_kw

def calculate_energies(df: pd.DataFrame, burner_power_kw: float) -> pd.DataFrame:
    """
    Calculates energy flow for all circuits and total.
    Returns DataFrame with new Energy columns (accumulated or rate).
    We will return rate (Power kW) columns.
    """
    df = df.copy()

    # 1. DHW Power
    df['power_dhw_kw'] = calculate_circuit_power_kw(
        df[Cols.DHW_PUMP_FLOW_RATE],
        df[Cols.DHW_FLOW_TEMP_TO_TANK],
        df[Cols.DHW_RETURN_TEMP_COMBINED]
    )

    # 2. Radiator Power
    df['power_rad_kw'] = calculate_circuit_power_kw(
        df[Cols.RADIATOR_FLOW_RATE],
        df[Cols.BOILER_FLOW_TEMP], # Assuming flow temp for rads is boiler flow
        df[Cols.RADIATOR_RETURN_TEMP_COMBINED]
    )

    # 3. Total Generated Power (Burner)
    df['power_generated_kw'] = np.where(df[Cols.BURNER_STATUS], burner_power_kw, 0.0)

    # 4. Underfloor (Residual)
    # Energy Balance: Generated = DHW + Rad + Underfloor + d(Stored)/dt
    # So: Underfloor = Generated - DHW - Rad - d(Stored)/dt

    # Calculate d(Stored)/dt
    # Boiler Thermal Power = M * C * dT/dt
    # Calculate gradient of Boiler Temp
    dt_seconds = df.index.to_series().diff().dt.total_seconds().fillna(10.0)
    temp_diff = df[Cols.BOILER_FLOW_TEMP].diff().fillna(0.0)

    # Power Stored (kW) = (kg * J/kgK * K) / s / 1000
    df['power_stored_kw'] = (BOILER_MASS_KG * C_WATER_J_KG_K * temp_diff) / dt_seconds / 1000.0

    # Residual
    df['power_underfloor_kw'] = df['power_generated_kw'] - df['power_dhw_kw'] - df['power_rad_kw'] - df['power_stored_kw']

    # Smooth Underfloor to remove noise from derivative
    df['power_underfloor_kw'] = df['power_underfloor_kw'].rolling(window=12, center=True).mean().fillna(0.0)

    return df
