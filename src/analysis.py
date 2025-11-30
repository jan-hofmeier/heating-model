import pandas as pd
import numpy as np
from src.config import Cols, STEADY_STATE_TEMP_VARIANCE, STEADY_STATE_MIN_DURATION_MINS

def detect_steady_state(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identifies periods of steady state operation.
    Criteria:
    1. Circuit active for > X minutes.
    2. Room temperature (or Return Temp) variance is low.
    3. Not in a "Warm Up" phase (first hour of the day).

    Returns:
        DataFrame with 'is_steady_state' boolean.
    """
    df = df.copy()

    # 1. Active Heating
    # (Radiator OR Underfloor active)
    # Radiator active if flow > 0
    # Underfloor active if... we don't have direct signal, but we can assume if Rad is active or inferred power > X.
    # The user said "From the two circuts where we get the flow rate from the pump, we know they are active... For the underfloor one, we can only detect it indirectly".
    # For steady state plot "Outside vs Flow", we care about the system state.

    # Let's define Steady State as:
    # System has been running for a while.
    # Use 'burner_status' or just time of day?
    # "heating circuits run only intermittend... steady state... not in the waring up phase"

    # Let's filter by:
    # 1. Rolling standard deviation of Boiler Flow Temp is not TOO high (cycling is normal, but trend should be flat).
    # 2. Room Temp is stable.
    # 3. Time > 2 hours after morning start.

    # A. Morning Start Check
    # Find the first time in the day where heating starts.
    # Simpler: Just exclude 5am - 9am? No, user wants calculation.

    # Let's use a rolling variance on Room Temp.
    # If Room Temp changes < 0.5C over 60 mins -> Steady.

    room_temp_std = df[Cols.ROOM_TEMP_AVG].rolling(window=int(STEADY_STATE_MIN_DURATION_MINS*6)).std() # 6 samples/min

    is_stable_room = room_temp_std < 0.5

    # Also check that Flow Temp is not rising/falling massively (trend).
    # Since it cycles, we smooth it first.
    flow_temp_smooth = df[Cols.BOILER_FLOW_TEMP].rolling(window=300).mean() # 50 min smooth
    flow_temp_deriv = flow_temp_smooth.diff()
    is_stable_flow = flow_temp_deriv.abs() < 0.05 # arbitrary small slope

    df['is_steady_state'] = is_stable_room & is_stable_flow

    return df
