import pandas as pd
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.preprocessing import preprocess_data
from src.physics import estimate_burner_power, calculate_energies
from src.analysis import detect_steady_state
from src.plotting import save_plots
from src.config import Cols
from src.influx_client import fetch_temp_data

def main():
    print("1. Loading Real Data from data/data-1m.csv...")
    file_path = "data/data-1m.csv"
    try:
        df = pd.read_csv(file_path, parse_dates=['_time'], index_col='_time')
    except FileNotFoundError:
        print(f"Error: The data file was not found at {file_path}")
        return

    print("2. Renaming columns to match internal convention...")
    column_mapping = {
        'vl_kessel_total': Cols.BOILER_FLOW_TEMP,
        'rl_kessel_total': Cols.BOILER_RETURN_TEMP,
        'flow_ww_total': Cols.DHW_PUMP_FLOW_RATE,
        'vl_hkww_total': Cols.DHW_FLOW_TEMP_TO_TANK,
        'rl_ww_total': Cols.DHW_RETURN_TEMP_COMBINED,
        'flow_hk_total': Cols.RADIATOR_FLOW_RATE,
        'rl_hk_total': Cols.RADIATOR_RETURN_TEMP_COMBINED,
        'vl_fb_total': Cols.UNDERFLOOR_FLOW_TEMP_MIXED,
        'rl_fb_total': Cols.UNDERFLOOR_RETURN_TEMP,
    }
    df.rename(columns=column_mapping, inplace=True)
    
    # Drop original columns that were not mapped to avoid confusion
    # This assumes we only want to work with the columns defined in `Cols`
    mapped_cols = list(column_mapping.values())
    # cols_to_keep = mapped_cols + [col for col in df.columns if col not in column_mapping.keys()]
    # df = df[cols_to_keep]


    print("3. Fetching Outside and Room Temperatures from InfluxDB...")
    start_date = df.index.min()
    end_date = df.index.max()
    
    if pd.isna(start_date) or pd.isna(end_date):
        print("Error: Could not determine the date range from the data file.")
        return
    
    temp_df = fetch_temp_data(start_date, end_date)

    if not temp_df.empty:
        # Merge the temperature data into the main DataFrame
        df = pd.merge(df, temp_df, left_index=True, right_index=True, how='left')
        print("   Successfully merged temperature data.")
    else:
        print("   Warning: Failed to fetch temperature data. Continuing without it.")

    # Ensure temperature columns exist before filling, even if fetch failed or returned no data for them
    if Cols.OUTSIDE_TEMP not in df.columns:
        df[Cols.OUTSIDE_TEMP] = pd.NA
    if Cols.ROOM_TEMP_AVG not in df.columns:
        df[Cols.ROOM_TEMP_AVG] = pd.NA
        
    # We might need to fill NaNs if the merge creates them
    # First, ensure the columns are of a numeric type, coercing errors
    df[Cols.OUTSIDE_TEMP] = pd.to_numeric(df[Cols.OUTSIDE_TEMP], errors='coerce')
    df[Cols.ROOM_TEMP_AVG] = pd.to_numeric(df[Cols.ROOM_TEMP_AVG], errors='coerce')

    # Now interpolate and fill
    df[[Cols.OUTSIDE_TEMP, Cols.ROOM_TEMP_AVG]] = df[[Cols.OUTSIDE_TEMP, Cols.ROOM_TEMP_AVG]].interpolate(method='linear').fillna(method='bfill').fillna(method='ffill')
    print("   Filled any gaps in temperature data.")


    print("4. Preprocessing & Status Inference...")
    df = preprocess_data(df)

    print("5. Calibrating Burner Power (Summer Mode)...")
    burner_power_kw = estimate_burner_power(df)
    print(f"   Estimated Burner Power: {burner_power_kw:.2f} kW")

    print("6. Calculating Energies...")
    df = calculate_energies(df, burner_power_kw)

    print("7. Detecting Steady States...")
    df = detect_steady_state(df)

    print("8. Generating Reports...")
    save_plots(df)

    print("Done. Check 'output/' for results.")

if __name__ == "__main__":
    main()
