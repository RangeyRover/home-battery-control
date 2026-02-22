import logging
from datetime import datetime, timezone

_LOGGER = logging.getLogger(__name__)


def parse_isoformat(dt_str: str) -> datetime:
    """Safely parse HA history ISO format strings."""
    return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))


def extract_valid_data(historic_states_parsed: list) -> list:
    """Parse raw HA state dicts into a time-sorted list of floats."""
    valid_data = []
    for entry in historic_states_parsed:
        state = entry.get("state")
        if state not in ("unavailable", "unknown", None, ""):
            try:
                # Compatibility for both raw API dicts and mock dt objects
                time_str = entry.get("last_changed")
                if isinstance(time_str, datetime):
                    dt = time_str
                else:
                    dt = parse_isoformat(time_str)

                val = float(state)
                valid_data.append({"time": dt.timestamp(), "value": val})
            except (ValueError, TypeError, KeyError):
                continue

    if valid_data:
        valid_data.sort(key=lambda x: x["time"])
    return valid_data


def interpolate(target_t: float, valid_data: list) -> float:
    """Linear interpolation natively adapted from standalone script."""
    if not valid_data:
        return 0.0
    if len(valid_data) == 1:
        return valid_data[0]["value"]
    if target_t <= valid_data[0]["time"]:
        return valid_data[0]["value"]
    if target_t >= valid_data[-1]["time"]:
        return valid_data[-1]["value"]

    for i in range(len(valid_data) - 1):
        t1 = valid_data[i]["time"]
        v1 = valid_data[i]["value"]
        t2 = valid_data[i + 1]["time"]
        v2 = valid_data[i + 1]["value"]

        if t1 <= target_t <= t2:
            if t2 == t1:
                return v1
            return v1 + (target_t - t1) * (v2 - v1) / (t2 - t1)

    return 0.0


def build_historical_profile(
    valid_data: list, target_tz=None, is_energy_sensor: bool = True
) -> dict:
    """
    Chronologically iterate over all valid history data, compute 5-minute intervals,
    handle midnight reset gaps, and average the results into a 24-hour HH:MM dictionary
    matching the exact mathematical logic of `extract_kwh_usage.py`.
    """
    historical_profile: dict[str, float] = {}
    if not valid_data or len(valid_data) < 2:
        return historical_profile

    try:
        start_time = valid_data[0]["time"]
        end_time = valid_data[-1]["time"]

        remainder = start_time % 300
        aligned_start = start_time + (300 - remainder) if remainder != 0 else start_time

        total_seconds = end_time - aligned_start
        intervals = int(total_seconds // 300)

        slot_sums = {}
        slot_counts = {}

        current_t = aligned_start
        prev_value = interpolate(current_t, valid_data)

        # Track previous legitimate usage for midnight anomaly bridging
        hist_prev_usage = 0.05

        for _ in range(intervals):
            next_t = current_t + 300
            next_value = interpolate(next_t, valid_data)

            if is_energy_sensor:
                usage = next_value - prev_value
                if usage < 0:
                    usage = hist_prev_usage
                else:
                    hist_prev_usage = usage
            else:
                usage = next_value  # For power sensors

            # Convert to defined timezone, fallback to UTC
            start_dt_utc = datetime.fromtimestamp(current_t, tz=timezone.utc)
            if target_tz:
                start_dt_local = start_dt_utc.astimezone(target_tz)
            else:
                start_dt_local = start_dt_utc.astimezone()

            time_slot = start_dt_local.strftime("%H:%M")

            if time_slot not in slot_sums:
                slot_sums[time_slot] = 0.0
                slot_counts[time_slot] = 0

            slot_sums[time_slot] += usage
            slot_counts[time_slot] += 1

            current_t = next_t
            prev_value = next_value

        for slot, total in slot_sums.items():
            # Calculate the literal average
            historical_profile[slot] = total / slot_counts[slot]

    except Exception as e:
        _LOGGER.error(f"Error building historical load profile: {e}")

    return historical_profile
