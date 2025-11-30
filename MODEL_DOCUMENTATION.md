# Heating Model Documentation

## Overview
This project models a heating system consisting of a Boiler (Oil Burner), Domestic Hot Water (DHW) tank, Radiator circuit, and Underfloor heating circuit. It processes time-series sensor data to calculate energy consumption and system efficiency.

## Assumptions & Methods

### 1. Burner Status Inference
*   **Method:** The burner status is inferred from the gradient of the Boiler Flow Temperature.
*   **Logic:** A sustained positive temperature gradient ($dT/dt > Threshold$) indicates the burner is active.
*   **Correction:** The inferred status is shifted backwards in time to account for the physical delay between the burner starting and the water temperature rising.

### 2. Burner Power Calibration
*   **Problem:** The burner's power output (kW) is unknown.
*   **Solution:** We calibrate the power using "Summer Mode" data, where only the DHW circuit is active.
*   **Calculation:**

$$
P_{burner} = \frac{\int P_{DHW} dt + \Delta E_{stored}}{\int Status_{burner} dt}
$$

    *   $P_{DHW}$: Power delivered to the DHW tank (calculated from flow & $\Delta T$).
    *   $\Delta E_{stored}$: Change in energy stored in the boiler's internal water volume ($30L$) over the period.
    *   This is calculated over long continuous periods (e.g., full days) to minimize errors from signal delays.

### 3. Circuit Energy Calculations
*   **Direct Calculation (DHW, Radiators):**
    For circuits with Flow Rate ($F$) and Return Temperature sensors:

$$
P = \dot{m} \cdot c_p \cdot (T_{in} - T_{out})
$$

    *   $\dot{m}$: Mass flow rate ($kg/s$), derived from Volumetric Flow ($L/h$) and Density ($\rho \approx 997 kg/m^3$).
    *   $c_p$: Specific heat capacity of water ($\approx 4186 J/kgK$).

*   **Residual Calculation (Underfloor):**
    The Underfloor circuit lacks a flow sensor. Its energy is calculated as the residual of the system energy balance:

$$
P_{underfloor} = P_{generated} - P_{DHW} - P_{Radiator} - P_{stored\_change}
$$

    *   $P_{generated}$: $P_{burner}$ when Burner is ON.
    *   $P_{stored\_change}$: Rate of change of internal boiler energy ($MC \cdot dT/dt$).

### 4. Steady State Detection
*   Steady state is defined as periods where:
    1.  Room temperature is stable (low variance).
    2.  Flow temperature trend is flat (low derivative).
*   This allows for plotting the "Steady State Flow Curve" (Outside Temp vs Flow Temp) without transient warm-up data.

## Configuration
Physical constants and column mappings are defined in `src/config.py`.
