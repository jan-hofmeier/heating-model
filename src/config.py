
# Physical Constants for Water
# Specific Heat Capacity of Water (approx constant for heating range) in J/(kg*K)
C_WATER_J_KG_K = 4186.0
# Density of Water (approx) in kg/m3
RHO_WATER_KG_M3 = 997.0

# System Constants
BOILER_VOLUME_L = 30.0  # Liters
BOILER_MASS_KG = BOILER_VOLUME_L * (RHO_WATER_KG_M3 / 1000.0)

# Delays (in seconds) - As measured/estimated
# These will be applied to shift temperature readings relative to the actuator (burner/pump)
DELAY_BURNER_START_S = 60
DELAY_BURNER_STOP_S = 120
DELAY_TEMP_RESPONSE_S = 30 # General transport delay for circuits

# Data Column Mapping
# This allows us to easily change the column names if the real data differs
class Cols:
    TIMESTAMP = 'timestamp'

    # Boiler / Burner
    BOILER_FLOW_TEMP = 'boiler_flow_temp'
    BOILER_RETURN_TEMP = 'boiler_return_temp'
    # Inferred/Calculated Status
    BURNER_STATUS = 'burner_status'

    # DHW (Domestic Hot Water) Tank
    DHW_PUMP_FLOW_RATE = 'dhw_pump_flow_rate_l_h' # L/h
    DHW_PUMP_PRESSURE = 'dhw_pump_pressure'
    DHW_FLOW_TEMP_TO_TANK = 'dhw_flow_temp_to_tank'
    DHW_RETURN_TEMP_TOP = 'dhw_return_temp_top'
    DHW_RETURN_TEMP_BOTTOM = 'dhw_return_temp_bottom'
    DHW_RETURN_TEMP_COMBINED = 'dhw_return_temp_combined'
    DHW_TANK_TEMP_MID = 'dhw_tank_temp_mid'

    # Potable Water Side
    POTABLE_FLOW_COLD_IN = 'potable_flow_cold_in_temp'
    POTABLE_FLOW_HOT_OUT = 'potable_flow_hot_out_temp'
    POTABLE_RETURN_CIRCULATION = 'potable_return_circulation_temp'

    # Radiators
    RADIATOR_FLOW_RATE = 'radiator_flow_rate_l_h' # L/h
    RADIATOR_RETURN_TEMP_1 = 'radiator_return_temp_1'
    RADIATOR_RETURN_TEMP_2 = 'radiator_return_temp_2'
    RADIATOR_RETURN_TEMP_COMBINED = 'radiator_return_temp_combined'

    # Underfloor
    UNDERFLOOR_FLOW_TEMP_MIXED = 'underfloor_flow_temp_mixed'
    UNDERFLOOR_RETURN_TEMP = 'underfloor_return_temp'

    # Environment
    OUTSIDE_TEMP = 'outside_temp'
    ROOM_TEMP_AVG = 'room_temp_avg' # Used for steady state checks

# Analysis Parameters
STEADY_STATE_TEMP_VARIANCE = 1.0 # degrees C
STEADY_STATE_MIN_DURATION_MINS = 60
