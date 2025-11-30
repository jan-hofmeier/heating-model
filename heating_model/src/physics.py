import pandas as pd
import numpy as np
from heating_model.src.config import (
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
    1. Identify continuous burner run periods in Summer.
    2. For each run:
       Energy_Input = Burner_Power * Run_Time
       Energy_Output = (Energy into DHW) + (Energy stored in Boiler Water)
       Burner_Power = Energy_Output / Run_Time
    3. Return average Burner_Power.
    """
    # Filter for Summer Mode: Radiator Flow == 0 (and Underfloor inactive, assumed if Rad is off in summer)
    # We use a heuristic: if radiator flow is zero for the whole surrounding period.
    # For now, just check instant flow.
    summer_mask = (df[Cols.RADIATOR_FLOW_RATE] < 1.0) & (df[Cols.BURNER_STATUS] == True)

    if summer_mask.sum() == 0:
        return 0.0 # No calibration data found

    # We need to group by "Burner Run Event" to integrate properly.
    # Identify change points
    df = df.copy()
    df['run_id'] = (df[Cols.BURNER_STATUS] != df[Cols.BURNER_STATUS].shift()).cumsum()

    # Filter only the TRUE runs
    runs = df[df[Cols.BURNER_STATUS] == True]

    # Only keep runs that are "Summer" (Rad flow 0)
    # Group by run_id
    valid_power_estimates = []

    for run_id, group in runs.groupby('run_id'):
        if group[Cols.RADIATOR_FLOW_RATE].max() > 1.0:
            continue # Skip mixed runs

        # 1. Run Time (seconds)
        # Assumes constant freq, or sum dt
        dt_seconds = group.index.to_series().diff().dt.total_seconds().fillna(10.0) # Assume 10s for first
        run_time_s = dt_seconds.sum()

        if run_time_s < 60:
            continue # Skip very short runs

        # 2. Energy Output to DHW
        # P_dhw at each step
        p_dhw_kw = calculate_circuit_power_kw(
            group[Cols.DHW_PUMP_FLOW_RATE],
            group[Cols.DHW_FLOW_TEMP_TO_TANK], # Flow
            group[Cols.DHW_RETURN_TEMP_COMBINED] # Return
        )
        # Energy (kJ) = Power(kW) * dt(s)
        e_dhw_kj = (p_dhw_kw * dt_seconds).sum()

        # 3. Energy Stored in Boiler
        # Change in boiler internal temp from Start to End of run
        # We need the temp just before start and at end
        # Or just delta over the group
        t_start = group[Cols.BOILER_FLOW_TEMP].iloc[0]
        t_end = group[Cols.BOILER_FLOW_TEMP].iloc[-1]

        # E = m * c * dT
        e_stored_kj = BOILER_MASS_KG * (C_WATER_J_KG_K/1000.0) * (t_end - t_start)

        # Total Output
        total_e_out_kj = e_dhw_kj + e_stored_kj

        # 4. Burner Power
        p_burner_kw = total_e_out_kj / run_time_s

        valid_power_estimates.append(p_burner_kw)

    if not valid_power_estimates:
        return 20.0 # Default fallback

    # Remove outliers?
    return np.median(valid_power_estimates)

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
    # Note: If burner is OFF, Generated is 0.
    # Stored power will be negative (cooling).
    # 0 = Out + (-Cooling) -> Out = Cooling.
    # So the equation holds.

    df['power_underfloor_kw'] = df['power_generated_kw'] - df['power_dhw_kw'] - df['power_rad_kw'] - df['power_stored_kw']

    # Smooth Underfloor to remove noise from derivative
    df['power_underfloor_kw'] = df['power_underfloor_kw'].rolling(window=12, center=True).mean().fillna(0.0)

    # Clip negative values?
    # Underfloor can't generate power. But sensor noise might cause it.
    # Realistically, valid range is >= 0.
    # But during transient states (burner start/stop delay mismatches), residual might be wild.

    return df
