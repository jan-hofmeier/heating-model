import pandas as pd
import numpy as np
import datetime
from src.config import Cols, DELAY_BURNER_START_S

def generate_mock_data(start_date='2023-01-01', days=5, freq='10s'):
    """
    Generates synthetic heating system data.
    days=5 allows us to simulate a mix of Summer (DHW only) and Winter (Heating) days.
    """
    dt_index = pd.date_range(start=start_date, periods=days*24*60*6, freq=freq)
    df = pd.DataFrame(index=dt_index)
    df[Cols.TIMESTAMP] = dt_index
    n = len(df)

    # --- 1. Outside Temperature ---
    # Simple sine wave for day/night cycle
    # Winter base: 0C, Summer base: 20C. Let's vary it over the "days".
    # Day 0-2: Summer (Avg 20C), Day 3-5: Winter (Avg 5C)
    day_fraction = df.index.dayofyear + df.index.hour/24.0

    # Create a mask for Summer vs Winter
    # We'll treat the first 2 days as Summer, rest as Winter
    is_summer = (df.index - df.index[0]).total_seconds() < (2 * 24 * 3600)

    base_temp = np.where(is_summer, 20.0, 5.0)
    # Daily variation amplitude 5 degrees
    daily_var = 5.0 * -np.cos(2 * np.pi * day_fraction)
    df[Cols.OUTSIDE_TEMP] = base_temp + daily_var + np.random.normal(0, 0.1, n)

    # --- 2. Boiler / Burner Logic (Simplified) ---
    # Burner turns on when boiler temp drops below Target (e.g., 60C) and off when > 75C.
    # But this is an output of the physical state. We need to simulate the state.

    boiler_temp = 60.0
    boiler_temps = []
    burner_state = False

    # DHW Demand Pattern (Morning/Evening)
    hour = df.index.hour
    dhw_active = ((hour >= 6) & (hour <= 8)) | ((hour >= 18) & (hour <= 20))

    # Radiator/Underfloor Demand (Winter only)
    heating_active = (~is_summer) & (hour >= 6) & (hour <= 22) # Night setback simulated by off

    # Arrays to store values
    dhw_flow_rate = np.zeros(n)
    rad_flow_rate = np.zeros(n)

    # Simulation loop (simple Euler integration for temp)
    # We iterate to allow state dependency
    current_boiler_temp = 65.0

    dhw_flows = []
    rad_flows = []
    burner_states_truth = [] # The "real" state, we will infer it later

    for i in range(n):
        ts = df.index[i]

        # Determine Demand
        # DHW
        is_dhw = dhw_active[i]
        # Radiator/Underfloor
        is_heating = heating_active[i]

        # Set Flow Rates (L/h)
        # DHW pump: 1000 L/h when active
        f_dhw = 1000.0 if is_dhw else 0.0
        # Radiator pump: 800 L/h when active
        f_rad = 800.0 if is_heating else 0.0

        # Burner Logic (Hysteresis)
        if current_boiler_temp < 50.0:
            burner_state = True
        elif current_boiler_temp > 75.0:
            burner_state = False

        burner_states_truth.append(burner_state)

        # Energy Balance for Boiler Water
        # Energy In: Burner (approx 20kW if on)
        power_in_kw = 25.0 if burner_state else 0.0

        # Energy Out: Circuits
        # For simplicity in generation, assume return temps are somewhat fixed relative to flow
        # This is a simplification; in reality return depends on load.

        # DHW Load
        # If DHW pump is running, we lose heat to the tank.
        # Assume Boiler Flow -> Tank -> Boiler Return
        # Delta T approx 10K for DHW loading
        power_out_dhw_kw = 0.0
        if f_dhw > 0:
            # P = Flow(kg/s) * C * dT
            # 1000 L/h = 0.277 kg/s
            m_dot_dhw = (f_dhw / 3600.0)
            dt_dhw = 10.0 # Heat drop across tank coils
            power_out_dhw_kw = m_dot_dhw * 4.186 * dt_dhw

        # Radiator Load
        power_out_rad_kw = 0.0
        if f_rad > 0:
            m_dot_rad = (f_rad / 3600.0)
            dt_rad = 10.0
            power_out_rad_kw = m_dot_rad * 4.186 * dt_rad

        # Underfloor Load (Passive simulation for now, just energy loss)
        # Assume it draws some heat if heating is active
        power_out_uf_kw = 0.0
        if is_heating:
             power_out_uf_kw = 3.0 # Constant 3kW load

        total_power_out = power_out_dhw_kw + power_out_rad_kw + power_out_uf_kw

        # Net Energy
        net_power = power_in_kw - total_power_out

        # Temp Change: dT/dt = NetPower / (Mass * C)
        # Mass = 30kg, C = 4.186 kJ/kgK -> MC = 125.58 kJ/K
        mc_boiler = 30.0 * 4.186 # kJ/K

        temp_change_per_sec = net_power / mc_boiler
        current_boiler_temp += temp_change_per_sec * 10.0 # 10s step

        # Decay to room temp if everything off (very slow)
        if not burner_state and total_power_out == 0:
            current_boiler_temp += (20.0 - current_boiler_temp) * 0.0001

        boiler_temps.append(current_boiler_temp)
        dhw_flows.append(f_dhw)
        rad_flows.append(f_rad)

    # Assign generated physical values
    df[Cols.BOILER_FLOW_TEMP] = boiler_temps
    # Add some noise
    df[Cols.BOILER_FLOW_TEMP] += np.random.normal(0, 0.2, n)

    # Boiler Return is Flow - DeltaT induced by loads
    # This is a rough approximation to make the numbers consistent
    # In reality return is a mix of circuit returns.
    # We will simulate the circuit returns specifically.

    df[Cols.DHW_PUMP_FLOW_RATE] = dhw_flows
    df[Cols.RADIATOR_FLOW_RATE] = rad_flows

    # DHW Temps
    # Flow to tank is close to Boiler Flow (maybe slight loss)
    df[Cols.DHW_FLOW_TEMP_TO_TANK] = df[Cols.BOILER_FLOW_TEMP] - 1.0
    # Return from tank: If pump on, it's Flow - 10, else it cools down to tank temp
    tank_temp = 50.0
    dhw_return = np.where(df[Cols.DHW_PUMP_FLOW_RATE]>0, df[Cols.DHW_FLOW_TEMP_TO_TANK]-10.0, tank_temp)
    df[Cols.DHW_RETURN_TEMP_COMBINED] = dhw_return
    # Add dummy top/bottom
    df[Cols.DHW_RETURN_TEMP_TOP] = dhw_return + 1.0
    df[Cols.DHW_RETURN_TEMP_BOTTOM] = dhw_return - 1.0

    # Radiator Temps
    # Return combined
    rad_return = np.where(df[Cols.RADIATOR_FLOW_RATE]>0, df[Cols.BOILER_FLOW_TEMP]-10.0, 20.0)
    df[Cols.RADIATOR_RETURN_TEMP_COMBINED] = rad_return

    # Underfloor Temps
    # Flow mixed is usually constant-ish, e.g., 35C
    df[Cols.UNDERFLOOR_FLOW_TEMP_MIXED] = np.where(is_heating, 35.0, 20.0)
    df[Cols.UNDERFLOOR_RETURN_TEMP] = np.where(is_heating, 30.0, 20.0)

    # Room Temp (for steady state)
    # 20C + noise
    df[Cols.ROOM_TEMP_AVG] = 20.0 + np.random.normal(0, 0.1, n)

    # Boiler Return Temp (Mix of returns)
    # Simple weighted average if flowing
    # If no flow, tracks flow temp (or whatever)
    # This is critical for the "Energy Check" but since we derive burner power from DHW (where we have DHW specific sensors),
    # the boiler return sensor itself is less critical for the *calculation* but good for consistency.
    # Actually, the user said "We can measure the flow and return temprature of the flow and return [of the boiler]".
    # Let's approximate it.
    df[Cols.BOILER_RETURN_TEMP] = df[Cols.BOILER_FLOW_TEMP] - 5.0 # Placeholder

    # Add Data Gaps
    # "periods without valid measurements"
    # Set a chunk to NaN
    gap_start = int(n * 0.4)
    gap_end = int(n * 0.42)
    df.iloc[gap_start:gap_end] = np.nan

    return df

if __name__ == "__main__":
    df = generate_mock_data()
    print(df.head())
    # df.to_csv("data/mock_data.csv")
    print("Mock data generated.")
