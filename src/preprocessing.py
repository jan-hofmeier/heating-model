import pandas as pd
import numpy as np
from src.config import Cols, DELAY_BURNER_START_S, DELAY_BURNER_STOP_S

def infer_burner_status(df: pd.DataFrame, gradient_threshold=0.01) -> pd.DataFrame:
    """
    Infers the burner status based on the gradient of the boiler flow temperature.
    User requirement: "We need to infer the burner status from the temprature gradients."

    Args:
        df: DataFrame with boiler_flow_temp
        gradient_threshold: Minimum positive temperature change per second to indicate heating.

    Returns:
        DataFrame with an added 'burner_status' boolean column.
    """
    df = df.copy()

    # Calculate gradient (dT/dt)
    # Assume index is datetime
    # Use diff() / diff_seconds
    dt_seconds = df.index.to_series().diff().dt.total_seconds()
    temp_diff = df[Cols.BOILER_FLOW_TEMP].diff()
    gradient = temp_diff / dt_seconds

    # Smooth the gradient to avoid noise triggering status flips
    # Rolling window of e.g. 60 seconds (6 samples at 10s freq)
    gradient_smoothed = gradient.rolling(window=6, center=True).mean()

    # Simple thresholding logic
    # If gradient is significantly positive, burner is likely ON.
    # Note: When DHW pump starts, temp might drop fast. When it stops, it might rise.
    # But generally, sustained rise = Burner ON.

    # However, just looking at gradient might be noisy.
    # Let's add a hysteresis or "latching" logic if needed.
    # For now, simple threshold.

    # Using a slightly higher threshold to avoid "cooling" drift being misinterpreted
    # though cooling is usually negative.

    df[Cols.BURNER_STATUS] = gradient_smoothed > gradient_threshold

    # Fill NaN from rolling
    df[Cols.BURNER_STATUS] = df[Cols.BURNER_STATUS].fillna(False)

    return df

def apply_delays(df: pd.DataFrame) -> pd.DataFrame:
    """
    Shifts temperature columns to align with actuator events.
    The user mentioned delays between burner start/stop and temp change.

    To make energy calculations easier (Input = Output), we can shift the
    result (Temperature) BACK in time to match the Cause (Burner/Pump).
    """
    df = df.copy()

    # Burner Delay
    # If burner starts at T=0, Temp rises at T=Delay.
    # So we want Temp at T=Delay to move to T=0.
    # Shift (-Delay).

    # Since start and stop delays are different, a simple shift is an approximation.
    # "The delay is different on the start and the stop."
    # If we strictly want to align signals for visual correlation, we might shift.
    # But for energy integration, if we integrate over a day, the shift matters less.
    # However, to calculate instantaneous power, alignment is key.

    # Let's try to shift by the average delay for the boiler temp
    avg_delay = (DELAY_BURNER_START_S + DELAY_BURNER_STOP_S) / 2.0
    freq_s = 10.0 # Standard frequency of our data
    periods = int(avg_delay / freq_s)

    # Shift Boiler Temp backwards (so the rise appears earlier, matching the burner start)
    df[Cols.BOILER_FLOW_TEMP] = df[Cols.BOILER_FLOW_TEMP].shift(-periods)

    # We might lose the last 'periods' data points (become NaN), which is fine.

    return df

def preprocess_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Full preprocessing pipeline.
    """
    # 1. Infer Status (on raw temp data, before shifting, because gradient causes the status)
    # Actually, if we shift temp back, the gradient happens earlier.
    # It's better to infer status from the raw physical signal, then align if needed.

    # Wait, if we use gradient to infer status, we are inferring the "Delayed Status".
    # e.g. Burner starts T=0. Temp rises T=60. Gradient > 0 at T=60. Inferred Status=ON at T=60.
    # So the Inferred Status is ALREADY delayed.
    # So if we want the "True Burner Status", we should shift the Inferred Status BACKWARDS?
    # No, the Inferred Status is derived from the Temp. So it aligns with the Temp.
    # If we want to align "Inferred Status" with "Real Time", we need to shift it backwards.

    df = infer_burner_status(df)

    # Shift the inferred status backwards to estimate "Real" burner start time
    # e.g. Gradient starts rising at T=60. Burner actually started at T=0.
    # So we shift status column by -Delay.
    avg_delay = (DELAY_BURNER_START_S + DELAY_BURNER_STOP_S) / 2.0
    freq_s = 10.0 # Assumed
    if len(df) > 1:
        freq_s = (df.index[1] - df.index[0]).total_seconds()

    periods = int(avg_delay / freq_s)

    # Shift Status backwards to align with "Reality"
    # df[Cols.BURNER_STATUS] = df[Cols.BURNER_STATUS].shift(-periods).fillna(False)

    # NOTE: The user said "We can measure the flow and return temprature... There is a delay...".
    # If we calculate energy based on Flow/Return DeltaT, that energy is delivered *when the temp changes*.
    # So for Energy calculation, we rely on the Temp timestamps.
    # Burner Power derivation relies on correlating "Burner ON duration" with "Energy Delivered".
    # If we shift the status back, we get the real run-time.
    # But the Energy output (from Temp) is delayed.
    # So: Burner Energy Input (at T=0) -> Delayed -> Water Energy Output (at T=60).
    # To equate Input = Output instantaneously, we should align them.
    # Let's shift the Burner Status backwards so it represents "Command",
    # AND shift the Temp backwards so it represents "Response aligned with Command"?
    # Or just leave Temp as is and know that Energy Output is delayed?

    # Decision: The User wants to calculate Energy.
    # Energy Output (Water) is calculated from Flow * DeltaT. This happened at T=60.
    # Burner Input (Oil) happened at T=0.
    # If we integrate over a whole day, it matches.
    # If we want to derive Burner Power (kW), we need to divide Total Energy / Total Burner Time.
    # Total Burner Time should be accurate.
    # If we infer status from Temp Gradient, the "Duration" of the gradient rise matches the "Duration" of the burner run (roughly).
    # The start and stop are just both shifted by Delay.
    # So `sum(Inferred_Status)` should be approx `sum(Real_Status)`.
    # So for Total Energy, shifting doesn't strictly matter.
    # But for the Charts (Energy vs Time), shifting aligns the spikes.

    # I will shift the inferred status backwards to represent the likely "Real" burner event.
    df[Cols.BURNER_STATUS] = df[Cols.BURNER_STATUS].shift(-periods).fillna(False)

    return df
