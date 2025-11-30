# Heating System Model

This project models a heating system to calculate energy consumption based on sensor data.
It infers burner status from temperature gradients, calibrates burner power using Summer mode data, and calculates energy distribution across DHW, Radiator, and Underfloor circuits.

## Structure

*   `src/config.py`: Configuration of system constants (Delays, Physics) and Column mappings.
*   `src/mock_data.py`: Generates synthetic data for testing.
*   `src/preprocessing.py`: Infers burner status and aligns signals.
*   `src/physics.py`: Core calculations for Power and Energy.
*   `src/analysis.py`: Steady state detection.
*   `src/plotting.py`: Generates charts and CSV outputs.
*   `main.py`: Main execution script.

## Usage

1.  Install dependencies:
    ```bash
    pip install pandas numpy matplotlib seaborn
    ```

2.  Run the model:
    ```bash
    python3 heating_model/main.py
    ```

3.  Check output:
    *   Results are saved in `heating_model/output/`.
    *   `daily_energy.csv`: aggregated energy data.
    *   `*.png`: Charts.

## Configuration

Modify `src/config.py` to adjust physical constants or sensor column names to match your InfluxDB schema.
