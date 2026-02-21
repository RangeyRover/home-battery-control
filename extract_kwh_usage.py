import argparse
import csv
import json
from datetime import datetime, timezone


def parse_isoformat(dt_str):
    return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))

def process_ha_history(input_file, output_json, output_csv):
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {input_file}")
        return

    # Check if this is the Home Assistant nested array format: [[{state...}, ...]]
    valid_data = []

    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
        entries = data[0]  # The first entity's history list
    elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        entries = data # In case it's a flat list of dicts directly
    elif isinstance(data, dict) and 'raw_states' in data:
        entries = data['raw_states'] # Legacy raw format fallback
    else:
        print("Error: Unknown JSON structure.")
        return

    # Parse and filter numerical readings
    for entry in entries:
        state = entry.get('state')
        if state not in ('unavailable', 'unknown', None, ''):
            try:
                dt = parse_isoformat(entry['last_changed'])
                val = float(state)
                valid_data.append({
                    'time': dt.timestamp(),
                    'value': val
                })
            except (ValueError, TypeError, KeyError):
                continue

    if len(valid_data) < 2:
        print("Error: Not enough valid data points to interpolate.")
        return

    # Sort sequentially by timestamp
    valid_data.sort(key=lambda x: x['time'])

    # Calculate span to know how many 5-minute chunks to create
    start_time = valid_data[0]['time']
    end_time = valid_data[-1]['time']

    remainder = start_time % 300
    aligned_start = start_time + (300 - remainder) if remainder != 0 else start_time

    total_seconds = end_time - aligned_start
    intervals = int(total_seconds // 300)

    print(f"Data spans {total_seconds / 86400:.2f} days. Generating {intervals} x 5-minute intervals.")

    # Linear interpolation function
    def interpolate(target_t):
        if target_t <= valid_data[0]['time']:
            return valid_data[0]['value']
        if target_t >= valid_data[-1]['time']:
            return valid_data[-1]['value']

        for i in range(len(valid_data) - 1):
            t1 = valid_data[i]['time']
            v1 = valid_data[i]['value']
            t2 = valid_data[i+1]['time']
            v2 = valid_data[i+1]['value']

            if t1 <= target_t <= t2:
                if t2 == t1: return v1
                return v1 + (target_t - t1) * (v2 - v1) / (t2 - t1)

    records = []
    current_t = aligned_start
    prev_value = interpolate(current_t)

    for _ in range(intervals):
        next_t = current_t + 300
        next_value = interpolate(next_t)

        start_dt_utc = datetime.fromtimestamp(current_t, tz=timezone.utc)
        end_dt_utc = datetime.fromtimestamp(next_t, tz=timezone.utc)

        # Convert to local time explicitly when deciding the boundary
        start_dt_local = start_dt_utc.astimezone()
        end_dt_local = end_dt_utc.astimezone()

        usage = next_value - prev_value
        if usage < 0:
            # The sensor resets to 0.0 at midnight.
            # Because of this massive jump to 0 between raw data points, the linear
            # interpolator creates a massive negative artifact (e.g. going from 78 to 14 to 0).
            # The most accurate representation of usage during this anomalous gap
            # is to simply assume it was the same as the previous 5-minute interval:
            usage = records[-1]['kwh_usage'] if records else 0.05

        records.append({
            'start_time': start_dt_local.isoformat(),
            'end_time': end_dt_local.isoformat(),
            'kwh_usage': round(usage, 4),
            'cumulative_kwh': round(next_value, 4)
        })

        current_t = next_t
        prev_value = next_value

    # Write aggregated metrics to output files
    with open(output_json, 'w') as f:
        json.dump(records, f, indent=2)

    with open(output_csv, 'w', newline='') as f:
        fieldnames = ['start_time', 'end_time', 'kwh_usage', 'cumulative_kwh']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(records)

    print(f"Successfully processed to {output_json} and {output_csv}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Extract and interpolate kWh usage from Home Assistant history.")
    parser.add_argument("--input", default="load_history.json", help="Path to input JSON file (default: load_history.json)")
    parser.add_argument("--out-json", default="7_day_kwh_usage.json", help="Path to output JSON file (default: 7_day_kwh_usage.json)")
    parser.add_argument("--out-csv", default="7_day_kwh_usage.csv", help="Path to output CSV file (default: 7_day_kwh_usage.csv)")

    args = parser.parse_args()

    process_ha_history(args.input, args.out_json, args.out_csv)
