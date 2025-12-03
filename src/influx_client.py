import configparser
from datetime import timedelta
import pandas as pd
from influxdb_client import InfluxDBClient
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_influx_credentials():
    """Reads InfluxDB credentials from config.ini."""
    config = configparser.ConfigParser()
    config.read('config.ini')
    
    if 'influxdb' not in config:
        raise ValueError("Missing 'influxdb' section in config.ini")
        
    credentials = {
        'org': config['influxdb'].get('org'),
        'token': config['influxdb'].get('token'),
        'url': config['influxdb'].get('url'),
        'bucket': config['influxdb'].get('bucket'),
    }
    
    if not all(credentials.values()):
        raise ValueError("One or more InfluxDB credentials are missing in config.ini")
        
    return credentials

def fetch_temp_data(start_date, end_date):
    """
    Fetches outside and room temperature data from InfluxDB for a given date range.

    Args:
        start_date (pd.Timestamp): The start of the date range.
        end_date (pd.Timestamp): The end of the date range.

    Returns:
        pd.DataFrame: A DataFrame with 'OUTSIDE_TEMP' and 'ROOM_TEMP_AVG' columns,
                      indexed by timestamp. Returns an empty DataFrame on error.
    """
    try:
        credentials = get_influx_credentials()
        org = credentials['org']
        token = credentials['token']
        url = credentials['url']
        bucket = credentials['bucket']
    except (ValueError, configparser.Error) as e:
        logging.error(f"Configuration error: {e}")
        return pd.DataFrame()

    all_temps_df = pd.DataFrame()

    try:
        with InfluxDBClient(url=url, token=token, org=org, timeout=60_000) as client:
            query_api = client.query_api()

            # Iterate through the date range day by day to keep queries small
            current_date = start_date.normalize()
            while current_date <= end_date.normalize():
                range_start = current_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                range_stop = (current_date + timedelta(days=1)).strftime('%Y-%m-%dT%H:%M:%SZ')

                query = f'''
                from(bucket: "{bucket}")
                  |> range(start: {range_start}, stop: {range_stop})
                  |> filter(fn: (r) => r._measurement == "climate" and r._field == "temp")
                  |> pivot(rowKey:["_time"], columnKey: ["floor", "room"], valueColumn: "_value")
                '''
                
                try:
                    result = query_api.query_data_frame(query)

                    # query_data_frame can return a list of frames, or a single frame
                    if isinstance(result, list):
                        if not result: # Empty list
                            current_date += timedelta(days=1)
                            continue
                        df = pd.concat(result, ignore_index=True)
                    else: # Is a single DataFrame
                        df = result

                    if df.empty:
                        current_date += timedelta(days=1)
                        continue
                    
                    # The result is a single DataFrame, process it
                    df = df.copy()
                    if '_time' not in df.columns:
                        logging.warning(f"No '_time' column in data for {current_date.date()}, skipping.")
                        current_date += timedelta(days=1)
                        continue

                    df.rename(columns={'_time': 'timestamp'}, inplace=True)
                    df.set_index('timestamp', inplace=True)

                    # Separate outside temp from room temps
                    outside_cols = [col for col in df.columns if 'outside' in col]
                    room_cols = [col for col in df.columns if 'outside' not in col and col not in ['result', '_start', '_stop', '_measurement', 'topic']]
                    
                    # Create a temporary DataFrame for the day
                    temp_df = pd.DataFrame(index=df.index)
                    temp_df['OUTSIDE_TEMP'] = pd.NA
                    temp_df['ROOM_TEMP_AVG'] = pd.NA

                    try:
                        if outside_cols:
                            # Coerce to numeric, turning non-numeric into NaNs
                            numeric_outside = df[outside_cols].apply(pd.to_numeric, errors='coerce')
                            temp_df['OUTSIDE_TEMP'] = numeric_outside.mean(axis=1)

                        if room_cols:
                            # Coerce to numeric, turning non-numeric into NaNs
                            numeric_room = df[room_cols].apply(pd.to_numeric, errors='coerce')
                            temp_df['ROOM_TEMP_AVG'] = numeric_room.mean(axis=1)
                    except Exception as calc_e:
                        logging.error(f"Error during temperature calculation for {current_date.date()}: {calc_e}")

                    # Append to the main DataFrame
                    if not temp_df.empty:
                        all_temps_df = pd.concat([all_temps_df, temp_df])

                except Exception as e:
                    logging.error(f"Error processing data for {current_date.date()}: {e}")
                
                current_date += timedelta(days=1)

            # Resample to a consistent frequency, e.g., 1 minute, to align with main data
            if not all_temps_df.empty:
                all_temps_df = all_temps_df.resample('1T').mean().interpolate(method='linear')

            return all_temps_df

    except Exception as e:
        logging.error(f"Failed to connect or query InfluxDB: {e}")
        return pd.DataFrame()

if __name__ == '__main__':
    # Example usage:
    start = pd.to_datetime('2022-10-01')
    end = pd.to_datetime('2022-10-05')
    temp_data = fetch_temp_data(start, end)
    if not temp_data.empty:
        print("Successfully fetched temperature data:")
        print(temp_data.head())
        print("\nMissing values check:")
        print(temp_data.isnull().sum())
    else:
        print("Failed to fetch temperature data.")