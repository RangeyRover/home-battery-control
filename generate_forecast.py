import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone


def parse_isoformat(dt_str):
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def parse_input_history(input_file):
    try:
        with open(input_file, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"Error: Could not find {input_file}")
        return []

    valid_data = []

    if isinstance(data, list) and len(data) > 0 and isinstance(data[0], list):
        entries = data[0]
    elif isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
        entries = data
    elif isinstance(data, dict) and "raw_states" in data:
        entries = data["raw_states"]
    else:
        print("Error: Unknown JSON structure.")
        return []

    for entry in entries:
        state = entry.get("state")
        if state not in ("unavailable", "unknown", None, ""):
            try:
                dt = parse_isoformat(entry["last_changed"])
                val = float(state)
                valid_data.append({"time": dt.timestamp(), "value": val})
            except (ValueError, TypeError, KeyError):
                continue

    if len(valid_data) < 2:
        print("Error: Not enough valid data points to interpolate.")
        return []

    valid_data.sort(key=lambda x: x["time"])

    start_time = valid_data[0]["time"]
    end_time = valid_data[-1]["time"]

    remainder = start_time % 300
    aligned_start = start_time + (300 - remainder) if remainder != 0 else start_time
    total_seconds = end_time - aligned_start
    intervals = int(total_seconds // 300)

    def interpolate(target_t):
        if target_t <= valid_data[0]["time"]:
            return valid_data[0]["value"]
        if target_t >= valid_data[-1]["time"]:
            return valid_data[-1]["value"]
        for i in range(len(valid_data) - 1):
            t1, v1 = valid_data[i]["time"], valid_data[i]["value"]
            t2, v2 = valid_data[i + 1]["time"], valid_data[i + 1]["value"]
            if t1 <= target_t <= t2:
                if t2 == t1:
                    return v1
                return v1 + (target_t - t1) * (v2 - v1) / (t2 - t1)

    records = []
    current_t = aligned_start
    prev_value = interpolate(current_t)

    for _ in range(intervals):
        next_t = current_t + 300
        next_value = interpolate(next_t)

        start_dt_utc = datetime.fromtimestamp(current_t, tz=timezone.utc)
        start_dt_local = start_dt_utc.astimezone()

        usage = next_value - prev_value
        if usage < 0:
            usage = records[-1]["kwh_usage"] if records else 0.05

        records.append({"start_time": start_dt_local.isoformat(), "kwh_usage": round(usage, 4)})

        current_t = next_t
        prev_value = next_value

    return records


def generate_average_forecast(input_file, output_json, output_csv):
    records = parse_input_history(input_file)
    if not records:
        return

    time_slots = defaultdict(list)

    for row in records:
        dt = datetime.fromisoformat(row["start_time"])
        local_dt = dt.astimezone()
        time_key = local_dt.strftime("%H:%M")

        if row["kwh_usage"] >= 0:
            time_slots[time_key].append(row["kwh_usage"])

    forecast = []

    for hour in range(24):
        for minute in range(0, 60, 5):
            time_key = f"{hour:02d}:{minute:02d}"
            usages = time_slots.get(time_key, [])
            avg_usage = sum(usages) / len(usages) if usages else 0.0

            forecast.append(
                {
                    "time_slot": time_key,
                    "avg_kwh_usage": round(avg_usage, 4),
                    "days_sampled": len(usages),
                }
            )

    print(json.dumps(forecast, indent=2))

    with open(output_json, "w") as f:
        json.dump(forecast, f, indent=2)

    with open(output_csv, "w", newline="") as f:
        fieldnames = ["time_slot", "avg_kwh_usage", "days_sampled"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(forecast)

    print("Successfully generated 24hr forecast profile (288 x 5-minute averages).")
    print(f"Exported to {output_json} and {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Generate 24-hour average forecast directly from Home Assistant history."
    )
    parser.add_argument(
        "--input",
        default="load_history.json",
        help="Path to input JSON file (default: load_history.json)",
    )
    parser.add_argument(
        "--out-json",
        default="average_24hr_forecast.json",
        help="Path to output JSON file (default: average_24hr_forecast.json)",
    )
    parser.add_argument(
        "--out-csv",
        default="average_24hr_forecast.csv",
        help="Path to output CSV file (default: average_24hr_forecast.csv)",
    )

    args = parser.parse_args()

    generate_average_forecast(args.input, args.out_json, args.out_csv)
