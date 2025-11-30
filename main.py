import pandas as pd
import sys
import os

# Add project root to path
sys.path.append(os.getcwd())

from src.mock_data import generate_mock_data
from src.preprocessing import preprocess_data, apply_delays
from src.physics import estimate_burner_power, calculate_energies
from src.analysis import detect_steady_state
from src.plotting import save_plots

def main():
    print("1. Generating Mock Data...")
    df = generate_mock_data(days=5)

    print("2. Preprocessing & Status Inference...")
    # Infer burner status from raw gradients
    df = preprocess_data(df)

    # Apply delays to temp signals (for alignment)
    # df = apply_delays(df)
    # NOTE: As decided in planning, we shifted Status backwards in preprocess_data instead of Temp.
    # So we might skip apply_delays for Temp unless we want strictly aligned physics.
    # The user logic relies on "Flow * DeltaT" which physically happens later.
    # If we shift temp, we align it with burner start, but we might break the "Flow" timing (Pump starts, Temp rises later).
    # If Pump and Temp are both delayed physically, we should shift both?
    # For now, let's trust the timestamp of the sensors.

    print("3. Calibrating Burner Power (Summer Mode)...")
    burner_power_kw = estimate_burner_power(df)
    print(f"   Estimated Burner Power: {burner_power_kw:.2f} kW")

    print("4. Calculating Energies...")
    df = calculate_energies(df, burner_power_kw)

    print("5. Detecting Steady States...")
    df = detect_steady_state(df)

    print("6. Generating Reports...")
    save_plots(df)

    print("Done. Check 'output/' for results.")

if __name__ == "__main__":
    main()
